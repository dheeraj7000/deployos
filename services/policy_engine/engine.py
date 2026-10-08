"""Deterministic Policy Engine Orchestrator."""

from datetime import datetime, timezone
from typing import Optional, Any
from packages.schemas.actions import (
    ActionProposal,
    PolicyDecision,
    DecisionType,
    ApprovalRequest,
    ApprovalStatus,
)
from packages.schemas.tools import RiskTier
from packages.telemetry.logger import logger
from packages.telemetry.metrics import metrics
from services.policy_engine.rules import (
    BasePolicyRule,
    StateFreshnessPolicy,
    TrustBoundaryPolicy,
    DuplicateActionPolicy,
    TransactionVerificationPolicy,
    RefundLimitPolicy,
)


class PolicyEngine:
    """Evaluates agent proposals deterministically before execution authority is granted."""

    def __init__(self, autonomous_refund_limit: float = 100.0):
        self.rules: list[BasePolicyRule] = [
            StateFreshnessPolicy(),
            TrustBoundaryPolicy(),
            DuplicateActionPolicy(),
            TransactionVerificationPolicy(),
            RefundLimitPolicy(autonomous_threshold=autonomous_refund_limit),
        ]
        self.approvals_db: dict[str, ApprovalRequest] = {}

    async def evaluate_proposal(self, proposal: ActionProposal, context: Optional[dict[str, Any]] = None) -> PolicyDecision:
        ctx = context or {}
        workflow_id = proposal.workflow_id
        run_id = proposal.run_id
        action_hash = proposal.compute_action_hash()

        logger.info(
            f"Evaluating action proposal: {proposal.action} on target {proposal.target}",
            workflow_id=workflow_id,
            run_id=run_id,
            agent=proposal.agent_id,
            event="policy_eval",
            action=proposal.action,
            risk_tier=proposal.risk_tier.value,
        )

        # Check for simulated service outage in context (Chaos engineering support)
        if ctx.get("simulate_service_unavailable"):
            decision = PolicyDecision(
                decision_id=f"dec_retry_{int(datetime.now(timezone.utc).timestamp())}",
                proposal_id=proposal.proposal_id,
                decision=DecisionType.RETRY,
                policy_name="SERVICE_AVAILABILITY",
                reason="Payment gateway returned transient 503 Service Unavailable. Scheduling durable retry.",
                action_hash=action_hash,
            )
            metrics.inc("policy_decisions_total", tags={"decision": "RETRY"})
            return decision

        # Run through deterministic policy rules
        for rule in self.rules:
            decision = await rule.evaluate(proposal, ctx)
            if decision:
                logger.info(
                    f"Policy rule '{rule.name}' triggered verdict: {decision.decision.value}",
                    workflow_id=workflow_id,
                    run_id=run_id,
                    rule=rule.name,
                    reason=decision.reason,
                )
                metrics.inc("policy_decisions_total", tags={"decision": decision.decision.value})
                if decision.decision in (DecisionType.REJECT, DecisionType.REVIEW):
                    metrics.inc("actions_blocked_total")
                if decision.decision == DecisionType.REVIEW:
                    metrics.inc("human_reviews_total")
                    # Create approval request ticket bound to the exact action_hash
                    self._create_approval_request(proposal, decision)
                return decision

        # Default: autonomous execution permitted
        decision = PolicyDecision(
            decision_id=f"dec_exec_{int(datetime.now(timezone.utc).timestamp())}",
            proposal_id=proposal.proposal_id,
            decision=DecisionType.EXECUTE,
            policy_name="DEFAULT_PERMIT",
            reason=f"Action '{proposal.action}' passed all deterministic policy constraints and verified.",
            action_hash=action_hash,
            evidence_verified=proposal.evidence_ids,
        )
        metrics.inc("policy_decisions_total", tags={"decision": "EXECUTE"})
        return decision

    def _create_approval_request(self, proposal: ActionProposal, decision: PolicyDecision) -> ApprovalRequest:
        approval_id = f"appr_{proposal.proposal_id}"
        req = ApprovalRequest(
            approval_id=approval_id,
            proposal_id=proposal.proposal_id,
            action_hash=decision.action_hash,
            workflow_id=proposal.workflow_id,
            run_id=proposal.run_id,
            organization_id=proposal.organization_id,
            agent_id=proposal.agent_id,
            action=proposal.action,
            target=proposal.target,
            summary=f"Agent '{proposal.agent_id}' requested {proposal.action} of ${proposal.parameters.get('amount', 0):.2f} on {proposal.target}",
            reason=decision.reason,
            evidence_items=[{"id": eid, "verified": True} for eid in proposal.evidence_ids],
            risk_tier=proposal.risk_tier,
            confidence=proposal.confidence,
            state_version=proposal.state_version,
            status=ApprovalStatus.PENDING,
        )
        self.approvals_db[approval_id] = req
        return req

    def resolve_approval(
        self,
        approval_id: str,
        status: ApprovalStatus,
        reviewer_id: str,
        comment: Optional[str] = None,
    ) -> ApprovalRequest:
        req = self.approvals_db.get(approval_id)
        if not req:
            raise KeyError(f"Approval request '{approval_id}' not found")
        req.status = status
        req.reviewer_id = reviewer_id
        req.reviewer_comment = comment
        req.resolved_at = datetime.now(timezone.utc)
        return req

    def verify_execution_authorization(self, proposal: ActionProposal, approval_id: Optional[str] = None) -> tuple[bool, str]:
        """Strict verification: checks that proposal parameters match the approved action_hash."""
        current_hash = proposal.compute_action_hash()

        if proposal.risk_tier == RiskTier.TIER_0_READ_ONLY:
            return True, "Tier 0 Read-only permitted autonomously"

        if not approval_id:
            # Check if this proposal required review
            amount = float(proposal.parameters.get("amount", 0.0))
            if proposal.action == "issue_refund" and amount > 100.0:
                return False, "Refund exceeds autonomous limit and requires an approved Human Review ticket"
            return True, "Action permitted without review"

        req = self.approvals_db.get(approval_id)
        if not req:
            return False, f"Approval request '{approval_id}' not found"

        if req.status != ApprovalStatus.APPROVED:
            return False, f"Approval request status is '{req.status.value}', not APPROVED"

        # Cryptographic binding check:
        if req.action_hash != current_hash:
            req.status = ApprovalStatus.INVALIDATED
            return False, (
                f"ACTION TAMPERING DETECTED: Proposed action hash '{current_hash}' does not match "
                f"approved hash '{req.action_hash}'. Human approval invalidated."
            )

        return True, "Human approval verified and bound to current action hash"


policy_engine = PolicyEngine()
