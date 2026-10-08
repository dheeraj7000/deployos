"""Unit Tests for Deterministic Policy Engine and Cryptographic Binding."""

import pytest
from datetime import datetime, timedelta, timezone
from packages.schemas.actions import ActionProposal, DecisionType, ApprovalStatus
from packages.schemas.tools import RiskTier
from packages.schemas.trust import TrustLevel
from packages.tools.store import enterprise_store
from services.policy_engine.engine import policy_engine


@pytest.fixture(autouse=True)
def reset_store():
    enterprise_store.reset()


@pytest.mark.asyncio
async def test_refund_limit_policy_autonomous_under_100():
    now = datetime.now(timezone.utc)
    proposal = ActionProposal(
        proposal_id="prop_test_sub100",
        workflow_id="wf_test_1",
        run_id="run_test_1",
        organization_id="org_acme",
        agent_id="refund_agent",
        action="issue_refund",
        target="txn_5521",
        parameters={"transaction_id": "txn_5521", "amount": 50.00},
        reason="Minor fee adjustment",
        confidence=0.98,
        evidence_ids=["inv_9281"],
        state_version=1,
        observed_at=now,
        expires_at=now + timedelta(minutes=15),
        trust_level=TrustLevel.INTERNAL_DATABASE,
        risk_tier=RiskTier.TIER_3_FINANCIAL_DESTRUCTIVE,
    )
    decision = await policy_engine.evaluate_proposal(proposal)
    assert decision.decision == DecisionType.EXECUTE


@pytest.mark.asyncio
async def test_refund_limit_policy_review_over_100():
    now = datetime.now(timezone.utc)
    proposal = ActionProposal(
        proposal_id="prop_test_over100",
        workflow_id="wf_test_2",
        run_id="run_test_2",
        organization_id="org_acme",
        agent_id="refund_agent",
        action="issue_refund",
        target="txn_5522",
        parameters={"transaction_id": "txn_5522", "amount": 249.00},
        reason="Duplicate billing",
        confidence=0.96,
        evidence_ids=["inv_9281", "txn_5521", "txn_5522"],
        state_version=1,
        observed_at=now,
        expires_at=now + timedelta(minutes=15),
        trust_level=TrustLevel.INTERNAL_DATABASE,
        risk_tier=RiskTier.TIER_3_FINANCIAL_DESTRUCTIVE,
    )
    decision = await policy_engine.evaluate_proposal(proposal)
    assert decision.decision == DecisionType.REVIEW
    assert "exceeds autonomous limit" in decision.reason
    assert decision.required_approver_role == "OPERATOR"


@pytest.mark.asyncio
async def test_unverified_transaction_rejection():
    now = datetime.now(timezone.utc)
    proposal = ActionProposal(
        proposal_id="prop_test_notfound",
        workflow_id="wf_test_3",
        run_id="run_test_3",
        organization_id="org_acme",
        agent_id="refund_agent",
        action="issue_refund",
        target="txn_nonexistent_999",
        parameters={"transaction_id": "txn_nonexistent_999", "amount": 249.00},
        reason="Duplicate billing",
        confidence=0.90,
        evidence_ids=[],
        state_version=1,
        observed_at=now,
        expires_at=now + timedelta(minutes=15),
        trust_level=TrustLevel.INTERNAL_DATABASE,
        risk_tier=RiskTier.TIER_3_FINANCIAL_DESTRUCTIVE,
    )
    decision = await policy_engine.evaluate_proposal(proposal)
    assert decision.decision == DecisionType.REJECT
    assert "does not exist" in decision.reason


@pytest.mark.asyncio
async def test_duplicate_refund_rejection():
    now = datetime.now(timezone.utc)
    enterprise_store.transactions["txn_5522"]["refunded"] = True
    enterprise_store.transactions["txn_5522"]["refund_id"] = "re_existing_123"

    proposal = ActionProposal(
        proposal_id="prop_test_dup",
        workflow_id="wf_test_4",
        run_id="run_test_4",
        organization_id="org_acme",
        agent_id="refund_agent",
        action="issue_refund",
        target="txn_5522",
        parameters={"transaction_id": "txn_5522", "amount": 249.00},
        reason="Duplicate billing attempt on already refunded txn",
        confidence=0.95,
        evidence_ids=["inv_9281"],
        state_version=1,
        observed_at=now,
        expires_at=now + timedelta(minutes=15),
        trust_level=TrustLevel.INTERNAL_DATABASE,
        risk_tier=RiskTier.TIER_3_FINANCIAL_DESTRUCTIVE,
    )
    decision = await policy_engine.evaluate_proposal(proposal)
    assert decision.decision == DecisionType.REJECT
    assert "already been refunded" in decision.reason


@pytest.mark.asyncio
async def test_stale_customer_version_rejection():
    now = datetime.now(timezone.utc)
    enterprise_store.customers["cus_acme_9281"]["state_version"] = 2  # Mutated concurrently

    proposal = ActionProposal(
        proposal_id="prop_test_stale",
        workflow_id="wf_test_5",
        run_id="run_test_5",
        organization_id="org_acme",
        agent_id="refund_agent",
        action="issue_refund",
        target="txn_5522",
        parameters={"customer_id": "cus_acme_9281", "amount": 50.00},
        reason="Stale state test",
        confidence=0.95,
        evidence_ids=[],
        state_version=1,  # Based on stale version 1!
        observed_at=now,
        expires_at=now + timedelta(minutes=15),
        trust_level=TrustLevel.INTERNAL_DATABASE,
        risk_tier=RiskTier.TIER_3_FINANCIAL_DESTRUCTIVE,
    )
    decision = await policy_engine.evaluate_proposal(proposal)
    assert decision.decision == DecisionType.REJECT
    assert "Stale state detected" in decision.reason


@pytest.mark.asyncio
async def test_tampered_action_hash_invalidation():
    now = datetime.now(timezone.utc)
    proposal_orig = ActionProposal(
        proposal_id="prop_test_tamper",
        workflow_id="wf_test_6",
        run_id="run_test_6",
        organization_id="org_acme",
        agent_id="refund_agent",
        action="issue_refund",
        target="txn_5522",
        parameters={"amount": 249.00},
        reason="Original proposal",
        confidence=0.96,
        evidence_ids=["inv_9281"],
        state_version=1,
        observed_at=now,
        expires_at=now + timedelta(minutes=15),
        trust_level=TrustLevel.INTERNAL_DATABASE,
        risk_tier=RiskTier.TIER_3_FINANCIAL_DESTRUCTIVE,
    )
    decision = await policy_engine.evaluate_proposal(proposal_orig)
    assert decision.decision == DecisionType.REVIEW

    approval_id = f"appr_{proposal_orig.proposal_id}"
    policy_engine.resolve_approval(approval_id, ApprovalStatus.APPROVED, reviewer_id="alice")

    # Now tamper with proposal parameters (change amount to $1,500.00)
    proposal_tampered = ActionProposal(
        proposal_id="prop_test_tamper",
        workflow_id="wf_test_6",
        run_id="run_test_6",
        organization_id="org_acme",
        agent_id="refund_agent",
        action="issue_refund",
        target="txn_5522",
        parameters={"amount": 1500.00},  # Tampered!
        reason="Original proposal",
        confidence=0.96,
        evidence_ids=["inv_9281"],
        state_version=1,
        observed_at=now,
        expires_at=now + timedelta(minutes=15),
        trust_level=TrustLevel.INTERNAL_DATABASE,
        risk_tier=RiskTier.TIER_3_FINANCIAL_DESTRUCTIVE,
    )

    is_auth, err = policy_engine.verify_execution_authorization(proposal_tampered, approval_id=approval_id)
    assert not is_auth
    assert "ACTION TAMPERING DETECTED" in err
