"""Durable Workflow Execution Engine."""

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Optional
from packages.schemas.actions import (
    ActionProposal,
    ApprovalStatus,
    DecisionType,
    PolicyDecision,
)
from packages.schemas.tools import RiskTier
from packages.schemas.workflow import EventType, RunEvent, WorkflowRun, WorkflowState
from packages.telemetry.logger import logger
from packages.telemetry.metrics import metrics
from packages.tools.registry import default_registry
from services.policy_engine.engine import policy_engine


class WorkflowExecutionError(Exception):
    pass


class DurableWorkflowEngine:
    """Provides resilient, checkpointed, durable execution for long-running workflows."""

    def __init__(self):
        self.runs: dict[str, WorkflowRun] = {}
        self.checkpoints: dict[str, dict[str, Any]] = {}

    def create_run(
        self,
        workflow_name: str,
        organization_id: str = "org_default",
        input_payload: Optional[dict[str, Any]] = None,
        model_name: str = "mock-reliable-v1",
        prompt_version: str = "v1",
        policy_version: str = "standard-2026",
    ) -> WorkflowRun:
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        workflow_id = f"wf_{uuid.uuid4().hex[:8]}"

        run = WorkflowRun(
            run_id=run_id,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            organization_id=organization_id,
            status=WorkflowState.PENDING,
            input_payload=input_payload or {},
            model_name=model_name,
            prompt_version=prompt_version,
            policy_version=policy_version,
            start_time=datetime.now(timezone.utc),
        )
        self.runs[run_id] = run
        self.checkpoints[run_id] = {"state": WorkflowState.PENDING, "step": 0, "context": {}}
        return run

    def record_event(
        self,
        run_id: str,
        event_type: EventType,
        component: str,
        message: str,
        payload: Optional[dict[str, Any]] = None,
        latency_ms: float = 0.0,
    ) -> RunEvent:
        run = self.runs.get(run_id)
        if not run:
            raise KeyError(f"Run '{run_id}' not found")

        event = RunEvent(
            event_id=f"evt_{len(run.events) + 1}",
            run_id=run_id,
            workflow_id=run.workflow_id,
            sequence=len(run.events) + 1,
            event_type=event_type,
            component=component,
            message=message,
            payload=payload or {},
            latency_ms=latency_ms,
        )
        run.events.append(event)
        return event

    async def execute_activity_with_retry(
        self,
        run_id: str,
        activity_name: str,
        activity_fn: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        max_retries: int = 3,
        backoff_sec: float = 0.2,
        **kwargs: Any,
    ) -> Any:
        """Executes a durable activity step with automatic retry on transient exceptions."""
        attempt = 0
        while True:
            attempt += 1
            start = time.perf_counter()
            try:
                result = await activity_fn(*args, **kwargs)
                lat = (time.perf_counter() - start) * 1000.0
                self.record_event(
                    run_id,
                    EventType.TOOL_EXECUTE,
                    activity_name,
                    f"Activity '{activity_name}' completed on attempt {attempt}",
                    payload={"result": str(result)[:300]},
                    latency_ms=lat,
                )
                return result
            except Exception as exc:
                lat = (time.perf_counter() - start) * 1000.0
                self.record_event(
                    run_id,
                    EventType.ERROR,
                    activity_name,
                    f"Activity '{activity_name}' failed attempt {attempt}/{max_retries}: {exc}",
                    payload={"error": str(exc)},
                    latency_ms=lat,
                )
                if attempt >= max_retries:
                    raise WorkflowExecutionError(f"Activity '{activity_name}' exceeded max retries: {exc}") from exc
                await asyncio.sleep(backoff_sec * (2 ** (attempt - 1)))

    async def submit_and_evaluate_proposal(
        self,
        run_id: str,
        proposal: ActionProposal,
        context: Optional[dict[str, Any]] = None,
    ) -> tuple[PolicyDecision, Optional[str]]:
        """Submits an agent proposal to the deterministic policy engine.
        
        Returns (PolicyDecision, approval_id).
        If decision is REVIEW, the workflow run is marked SUSPENDED_APPROVAL.
        """
        run = self.runs[run_id]
        run.proposals.append(proposal)

        start = time.perf_counter()
        decision = await policy_engine.evaluate_proposal(proposal, context=context)
        lat = (time.perf_counter() - start) * 1000.0

        run.policy_decisions.append(decision)
        self.record_event(
            run_id,
            EventType.POLICY_CHECK,
            "policy_engine",
            f"Policy decision for {proposal.action}: {decision.decision.value} ({decision.reason})",
            payload={"decision": decision.decision.value, "policy": decision.policy_name, "action_hash": decision.action_hash},
            latency_ms=lat,
        )

        approval_id = None
        if decision.decision == DecisionType.REVIEW:
            approval_id = f"appr_{proposal.proposal_id}"
            run.status = WorkflowState.SUSPENDED_APPROVAL
            self.record_event(
                run_id,
                EventType.APPROVAL_REQUESTED,
                "approval_engine",
                f"Workflow suspended awaiting human approval for action hash {decision.action_hash[:12]}...",
                payload={"approval_id": approval_id, "action_hash": decision.action_hash},
            )

        return decision, approval_id

    async def execute_authorized_action(
        self,
        run_id: str,
        proposal: ActionProposal,
        approval_id: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Executes a consequential proposal ONLY IF authorized by policy or valid human approval."""
        run = self.runs[run_id]
        ctx = context or {}
        ctx["workflow_id"] = run.workflow_id
        ctx["run_id"] = run.run_id

        # 1. Verify authorization
        is_authorized, auth_reason = policy_engine.verify_execution_authorization(proposal, approval_id)
        if not is_authorized:
            self.record_event(
                run_id,
                EventType.ERROR,
                "execution_authority",
                f"UNAUTHORIZED ACTION BLOCKED: {auth_reason}",
                payload={"proposal_id": proposal.proposal_id, "action_hash": proposal.compute_action_hash()},
            )
            raise PermissionError(f"Action authorization failed: {auth_reason}")

        # 2. Attach idempotency key
        idempotency_key = proposal.generate_idempotency_key()
        tool_args = dict(proposal.parameters)
        tool_args["idempotency_key"] = idempotency_key

        # 3. Execute via tool registry
        tool_call = await default_registry.execute(
            proposal.action,
            arguments=tool_args,
            context=ctx,
            chaos_hook=ctx.get("chaos_hook"),
        )
        run.tool_calls.append(tool_call)

        if not tool_call.success:
            self.record_event(
                run_id,
                EventType.ERROR,
                proposal.action,
                f"Tool execution failed: {tool_call.error}",
                payload={"error": tool_call.error},
                latency_ms=tool_call.latency_ms,
            )
            raise RuntimeError(f"Tool execution failed: {tool_call.error}")

        self.record_event(
            run_id,
            EventType.ACTION_EXECUTED,
            proposal.action,
            f"Consequential action '{proposal.action}' executed successfully",
            payload={"result": str(tool_call.result)[:300], "idempotency_key": idempotency_key},
            latency_ms=tool_call.latency_ms,
        )
        return tool_call.result


durable_engine = DurableWorkflowEngine()
