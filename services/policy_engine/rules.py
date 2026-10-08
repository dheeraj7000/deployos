"""Deterministic Policy Rules for Evaluating Action Proposals."""

import abc
from datetime import datetime, timezone
from typing import Optional
from packages.schemas.actions import ActionProposal, PolicyDecision, DecisionType
from packages.schemas.trust import TrustLevel
from packages.schemas.tools import RiskTier
from packages.tools.store import enterprise_store


class BasePolicyRule(abc.ABC):
    name: str

    @abc.abstractmethod
    async def evaluate(self, proposal: ActionProposal, context: dict) -> Optional[PolicyDecision]:
        """Returns PolicyDecision if rule applies, or None to continue chain."""
        pass


class StateFreshnessPolicy(BasePolicyRule):
    """Verifies that the agent's observation has not expired and entity version is not stale."""
    name = "STATE_FRESHNESS"

    async def evaluate(self, proposal: ActionProposal, context: dict) -> Optional[PolicyDecision]:
        now = datetime.now(timezone.utc)
        action_hash = proposal.compute_action_hash()

        # 1. Check expiration
        expires_at = proposal.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if now > expires_at:
            return PolicyDecision(
                decision_id=f"dec_fresh_{int(now.timestamp())}",
                proposal_id=proposal.proposal_id,
                decision=DecisionType.REJECT,
                policy_name=self.name,
                reason=f"Proposal expired at {expires_at.isoformat()} (current time: {now.isoformat()}). Re-observation required.",
                action_hash=action_hash,
            )

        # 2. Check customer state version in CRM if applicable
        customer_id = proposal.parameters.get("customer_id")
        if customer_id and customer_id in enterprise_store.customers:
            current_version = enterprise_store.customers[customer_id]["state_version"]
            if proposal.state_version != current_version:
                return PolicyDecision(
                    decision_id=f"dec_stale_{int(now.timestamp())}",
                    proposal_id=proposal.proposal_id,
                    decision=DecisionType.REJECT,
                    policy_name=self.name,
                    reason=(
                        f"Stale state detected: Customer record changed from version {proposal.state_version} "
                        f"to version {current_version} during workflow execution. Proposal rejected."
                    ),
                    action_hash=action_hash,
                )

        return None


class TrustBoundaryPolicy(BasePolicyRule):
    """Enforces that consequential actions cannot be authorized solely by untrusted sources."""
    name = "TRUST_BOUNDARY"

    async def evaluate(self, proposal: ActionProposal, context: dict) -> Optional[PolicyDecision]:
        action_hash = proposal.compute_action_hash()

        # Tier 3 actions require trusted database confirmation
        if proposal.risk_tier == RiskTier.TIER_3_FINANCIAL_DESTRUCTIVE:
            if proposal.trust_level in (TrustLevel.CUSTOMER_EMAIL, TrustLevel.UPLOADED_PDF, TrustLevel.PUBLIC_WEB):
                return PolicyDecision(
                    decision_id=f"dec_trust_{int(datetime.now(timezone.utc).timestamp())}",
                    proposal_id=proposal.proposal_id,
                    decision=DecisionType.REJECT,
                    policy_name=self.name,
                    reason=(
                        f"Trust boundary violation: Consequential action '{proposal.action}' was proposed "
                        f"with untrusted source level '{proposal.trust_level.value}'. "
                        "External inputs cannot dictate financial execution without verified internal database records."
                    ),
                    action_hash=action_hash,
                )

        return None


class DuplicateActionPolicy(BasePolicyRule):
    """Prevents double-refunding or duplicate execution."""
    name = "DUPLICATE_ACTION"

    async def evaluate(self, proposal: ActionProposal, context: dict) -> Optional[PolicyDecision]:
        action_hash = proposal.compute_action_hash()

        if proposal.action == "issue_refund":
            target_tid = proposal.target
            txn = enterprise_store.transactions.get(target_tid)
            if txn and txn.get("refunded"):
                return PolicyDecision(
                    decision_id=f"dec_dup_{int(datetime.now(timezone.utc).timestamp())}",
                    proposal_id=proposal.proposal_id,
                    decision=DecisionType.REJECT,
                    policy_name=self.name,
                    reason=f"Transaction '{target_tid}' has already been refunded (Refund ID: {txn.get('refund_id')}). Duplicate action blocked.",
                    action_hash=action_hash,
                )

        return None


class TransactionVerificationPolicy(BasePolicyRule):
    """Verifies that target transaction exists and matches proposal parameters."""
    name = "TRANSACTION_VERIFICATION"

    async def evaluate(self, proposal: ActionProposal, context: dict) -> Optional[PolicyDecision]:
        action_hash = proposal.compute_action_hash()

        if proposal.action == "issue_refund":
            target_tid = proposal.target
            txn = enterprise_store.transactions.get(target_tid)
            if not txn:
                return PolicyDecision(
                    decision_id=f"dec_txn_notfound_{int(datetime.now(timezone.utc).timestamp())}",
                    proposal_id=proposal.proposal_id,
                    decision=DecisionType.REJECT,
                    policy_name=self.name,
                    reason=f"Target transaction '{target_tid}' does not exist in Stripe transaction records. Execution rejected.",
                    action_hash=action_hash,
                )

            proposed_amount = float(proposal.parameters.get("amount", 0.0))
            if proposed_amount > txn["amount"]:
                return PolicyDecision(
                    decision_id=f"dec_txn_amount_{int(datetime.now(timezone.utc).timestamp())}",
                    proposal_id=proposal.proposal_id,
                    decision=DecisionType.REJECT,
                    policy_name=self.name,
                    reason=(
                        f"Proposed refund amount ${proposed_amount:.2f} exceeds original transaction "
                        f"charge of ${txn['amount']:.2f}. Execution rejected."
                    ),
                    action_hash=action_hash,
                )

        return None


class RefundLimitPolicy(BasePolicyRule):
    """Enforces financial thresholds. Over $100 requires human review."""
    name = "REFUND_LIMIT"

    def __init__(self, autonomous_threshold: float = 100.0):
        self.autonomous_threshold = autonomous_threshold

    async def evaluate(self, proposal: ActionProposal, context: dict) -> Optional[PolicyDecision]:
        action_hash = proposal.compute_action_hash()

        if proposal.action == "issue_refund":
            amount = float(proposal.parameters.get("amount", 0.0))
            if amount > self.autonomous_threshold:
                return PolicyDecision(
                    decision_id=f"dec_review_limit_{int(datetime.now(timezone.utc).timestamp())}",
                    proposal_id=proposal.proposal_id,
                    decision=DecisionType.REVIEW,
                    policy_name=self.name,
                    reason=(
                        f"Refund amount ${amount:.2f} exceeds autonomous limit of "
                        f"${self.autonomous_threshold:.2f} USD. Requires Human Review."
                    ),
                    action_hash=action_hash,
                    required_approver_role="OPERATOR",
                    evidence_verified=proposal.evidence_ids,
                )

        return None
