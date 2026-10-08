"""Data Access Repository Layer for Multi-Tenant Database Persistence."""

import uuid
from typing import Optional, Any
from sqlalchemy import select
from packages.schemas.database import async_session_factory
from packages.schemas import db_models as db
from packages.schemas.workflow import WorkflowRun as PydanticWorkflowRun, RunEvent as PydanticRunEvent
from packages.schemas.actions import (
    ActionProposal as PydanticActionProposal,
    PolicyDecision as PydanticPolicyDecision,
    ApprovalRequest as PydanticApprovalRequest,
)
from packages.schemas.chaos import Incident as PydanticIncident


class DatabaseRepository:
    """Async repository providing multi-tenant persistence for workflow runs, proposals, and approvals."""

    @staticmethod
    async def ensure_organization(org_id: str, name: str = "Acme Corporation", slug: Optional[str] = None) -> None:
        async with async_session_factory() as session:
            stmt = select(db.Organization).where(db.Organization.id == org_id)
            result = await session.execute(stmt)
            org = result.scalar_one_or_none()
            if not org:
                unique_slug = slug or f"slug_{org_id}"
                # Ensure slug uniqueness
                slug_check = await session.execute(select(db.Organization).where(db.Organization.slug == unique_slug))
                if slug_check.scalar_one_or_none():
                    unique_slug = f"{unique_slug}_{uuid.uuid4().hex[:4]}"

                org = db.Organization(id=org_id, name=name, slug=unique_slug)
                session.add(org)
                await session.commit()

    @staticmethod
    async def persist_workflow_run(run: PydanticWorkflowRun) -> None:
        await DatabaseRepository.ensure_organization(run.organization_id)

        async with async_session_factory() as session:
            wf_stmt = select(db.Workflow).where(db.Workflow.id == run.workflow_id)
            wf_res = await session.execute(wf_stmt)
            wf = wf_res.scalar_one_or_none()
            if not wf:
                wf = db.Workflow(
                    id=run.workflow_id,
                    organization_id=run.organization_id,
                    name=run.workflow_name,
                    description="Automated business operations workflow",
                )
                session.add(wf)

            # Insert or update run
            run_stmt = select(db.WorkflowRun).where(db.WorkflowRun.id == run.run_id)
            run_res = await session.execute(run_stmt)
            db_run = run_res.scalar_one_or_none()

            if not db_run:
                db_run = db.WorkflowRun(
                    id=run.run_id,
                    workflow_id=run.workflow_id,
                    organization_id=run.organization_id,
                    status=run.status.value,
                    input_payload=run.input_payload,
                    output_payload=run.output_payload,
                    model_name=run.model_name,
                    prompt_version=run.prompt_version,
                    policy_version=run.policy_version,
                    duration_ms=run.duration_ms,
                    error=run.error,
                    created_at=run.start_time,
                    finished_at=run.end_time,
                )
                session.add(db_run)
            else:
                db_run.status = run.status.value
                db_run.output_payload = run.output_payload
                db_run.duration_ms = run.duration_ms
                db_run.error = run.error
                db_run.finished_at = run.end_time

            await session.commit()

    @staticmethod
    async def persist_run_event(event: PydanticRunEvent) -> None:
        async with async_session_factory() as session:
            db_event = db.RunEvent(
                id=event.event_id,
                run_id=event.run_id,
                sequence=event.sequence,
                event_type=event.event_type.value,
                component=event.component,
                message=event.message,
                payload=event.payload,
                latency_ms=event.latency_ms,
                created_at=event.timestamp,
            )
            session.add(db_event)
            await session.commit()

    @staticmethod
    async def persist_action_proposal(proposal: PydanticActionProposal) -> None:
        async with async_session_factory() as session:
            db_prop = db.ActionProposal(
                id=proposal.proposal_id,
                run_id=proposal.run_id,
                organization_id=proposal.organization_id,
                agent_id=proposal.agent_id,
                action=proposal.action,
                target=proposal.target,
                parameters=proposal.parameters,
                reason=proposal.reason,
                confidence=proposal.confidence,
                evidence_ids=proposal.evidence_ids,
                state_version=proposal.state_version,
                action_hash=proposal.compute_action_hash(),
                expires_at=proposal.expires_at,
                trust_level=proposal.trust_level.value,
                risk_tier=proposal.risk_tier.value,
            )
            session.add(db_prop)
            await session.commit()

    @staticmethod
    async def persist_policy_decision(decision: PydanticPolicyDecision, proposal: PydanticActionProposal) -> None:
        async with async_session_factory() as session:
            db_dec = db.PolicyDecision(
                id=decision.decision_id,
                proposal_id=decision.proposal_id,
                organization_id=proposal.organization_id,
                decision=decision.decision.value,
                policy_name=decision.policy_name,
                reason=decision.reason,
                action_hash=decision.action_hash,
                required_approver_role=decision.required_approver_role,
            )
            session.add(db_dec)
            await session.commit()

    @staticmethod
    async def persist_approval_request(appr: PydanticApprovalRequest) -> None:
        async with async_session_factory() as session:
            db_appr = db.Approval(
                id=appr.approval_id,
                proposal_id=appr.proposal_id,
                organization_id=appr.organization_id,
                action_hash=appr.action_hash,
                status=appr.status.value,
                reviewer_id=appr.reviewer_id,
                reviewer_comment=appr.reviewer_comment,
                created_at=appr.created_at,
                resolved_at=appr.resolved_at,
            )
            session.add(db_appr)
            await session.commit()

    @staticmethod
    async def list_runs_by_tenant(organization_id: str) -> list[db.WorkflowRun]:
        async with async_session_factory() as session:
            stmt = select(db.WorkflowRun).where(db.WorkflowRun.organization_id == organization_id).order_by(db.WorkflowRun.created_at.desc())
            res = await session.execute(stmt)
            return list(res.scalars().all())


repository = DatabaseRepository()
