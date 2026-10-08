"""Unit and Integration Tests for PostgreSQL SQLAlchemy Database Persistence."""

import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from packages.schemas.database import init_db, async_session_factory
from packages.schemas import db_models as db
from packages.schemas.repository import repository
from packages.schemas.actions import ActionProposal, PolicyDecision, ApprovalRequest, DecisionType, ApprovalStatus
from packages.schemas.workflow import WorkflowRun, RunEvent, EventType, WorkflowState
from packages.schemas.trust import TrustLevel
from packages.schemas.tools import RiskTier


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_organization_and_user_creation():
    org_id = f"org_{uuid.uuid4().hex[:8]}"
    org_name = "Global Logistics Enterprise"
    slug = f"logistics_{uuid.uuid4().hex[:6]}"

    async with async_session_factory() as session:
        org = db.Organization(id=org_id, name=org_name, slug=slug, tier="ENTERPRISE")
        session.add(org)
        await session.commit()

        # Add user with RBAC role
        user = db.User(
            id=f"usr_{uuid.uuid4().hex[:8]}",
            organization_id=org_id,
            email=f"admin_{slug}@example.com",
            full_name="Operations Lead",
            role="OPERATOR",
        )
        session.add(user)
        await session.commit()

        # Query back with eager loading
        stmt = (
            select(db.Organization)
            .options(selectinload(db.Organization.users))
            .where(db.Organization.id == org_id)
        )
        result = await session.execute(stmt)
        fetched_org = result.scalar_one()

        assert fetched_org.name == org_name
        assert len(fetched_org.users) == 1
        assert fetched_org.users[0].role == "OPERATOR"


@pytest.mark.asyncio
async def test_workflow_run_and_event_persistence():
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    wf_id = f"wf_{uuid.uuid4().hex[:8]}"
    org_id = f"org_{uuid.uuid4().hex[:8]}"

    # Pydantic run model
    p_run = WorkflowRun(
        run_id=run_id,
        workflow_id=wf_id,
        workflow_name="b2b_refund_remediation",
        organization_id=org_id,
        status=WorkflowState.RUNNING,
        input_payload={"customer": "Acme", "amount": 249.00},
        model_name="mock-reliable-v1",
    )

    await repository.persist_workflow_run(p_run)

    # Persist event
    p_event = RunEvent(
        event_id=f"evt_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        workflow_id=wf_id,
        sequence=1,
        event_type=EventType.WORKFLOW_START,
        component="orchestrator",
        message="Workflow initialized",
        payload={"started": True},
        latency_ms=1.2,
    )
    await repository.persist_run_event(p_event)

    # Verify query by tenant
    tenant_runs = await repository.list_runs_by_tenant(org_id)
    assert len(tenant_runs) == 1
    assert tenant_runs[0].id == run_id
    assert tenant_runs[0].workflow_id == wf_id


@pytest.mark.asyncio
async def test_action_proposal_and_approval_binding_persistence():
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    wf_id = f"wf_{uuid.uuid4().hex[:8]}"
    org_id = f"org_{uuid.uuid4().hex[:8]}"

    p_run = WorkflowRun(
        run_id=run_id,
        workflow_id=wf_id,
        workflow_name="b2b_refund_remediation",
        organization_id=org_id,
        status=WorkflowState.SUSPENDED_APPROVAL,
    )
    await repository.persist_workflow_run(p_run)

    now = datetime.now(timezone.utc)
    proposal = ActionProposal(
        proposal_id=f"prop_{uuid.uuid4().hex[:8]}",
        workflow_id=wf_id,
        run_id=run_id,
        organization_id=org_id,
        agent_id="refund_agent",
        action="issue_refund",
        target="txn_5522",
        parameters={"amount": 249.00, "currency": "USD"},
        reason="Verified duplicate charge",
        confidence=0.96,
        evidence_ids=["inv_9281", "txn_5521", "txn_5522"],
        state_version=1,
        observed_at=now,
        expires_at=now + timedelta(minutes=15),
        trust_level=TrustLevel.INTERNAL_DATABASE,
        risk_tier=RiskTier.TIER_3_FINANCIAL_DESTRUCTIVE,
    )
    await repository.persist_action_proposal(proposal)

    decision = PolicyDecision(
        decision_id=f"dec_{uuid.uuid4().hex[:8]}",
        proposal_id=proposal.proposal_id,
        decision=DecisionType.REVIEW,
        policy_name="REFUND_LIMIT",
        reason="Refund amount exceeds $100.00 USD",
        action_hash=proposal.compute_action_hash(),
        required_approver_role="OPERATOR",
    )
    await repository.persist_policy_decision(decision, proposal)

    appr = ApprovalRequest(
        approval_id=f"appr_{proposal.proposal_id}",
        proposal_id=proposal.proposal_id,
        action_hash=decision.action_hash,
        workflow_id=wf_id,
        run_id=run_id,
        organization_id=org_id,
        agent_id="refund_agent",
        action=proposal.action,
        target=proposal.target,
        summary="Refund $249.00",
        reason=decision.reason,
        risk_tier=proposal.risk_tier,
        confidence=proposal.confidence,
        state_version=proposal.state_version,
        status=ApprovalStatus.PENDING,
    )
    await repository.persist_approval_request(appr)

    # Verify database records with selectinload
    async with async_session_factory() as session:
        stmt = (
            select(db.Approval)
            .options(selectinload(db.Approval.proposal))
            .where(db.Approval.id == appr.approval_id)
        )
        res = await session.execute(stmt)
        fetched_appr = res.scalar_one()

        assert fetched_appr.action_hash == proposal.compute_action_hash()
        assert fetched_appr.status == "PENDING"
        assert fetched_appr.proposal.target == "txn_5522"
