"""DeployOS API Gateway, REST Endpoints, and Telemetry."""

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from packages.schemas.actions import (
    ActionProposal,
    ApprovalStatus,
    DecisionType,
    PolicyDecision,
)
from packages.schemas.chaos import ChaosScenarioType, IncidentSeverity
from packages.schemas.workflow import WorkflowState
from packages.telemetry.metrics import metrics
from packages.tools.store import enterprise_store
from services.agent_runtime.durable_engine import durable_engine
from services.chaos.harness import chaos_harness
from services.eval_engine.evaluator import evaluator
from services.eval_engine.replay import replay_engine
from services.incidents.manager import incident_manager
from services.policy_engine.engine import policy_engine
from workflows.refunds.refund_workflow import CustomerRefundWorkflow
from packages.models.adapters import get_model_provider

app = FastAPI(
    title="DeployOS API Gateway",
    description="Production infrastructure for reliable, durable, and auditable AI agents.",
    version="0.1.0",
)

# Enable CORS for the Next.js control plane dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TriggerWorkflowRequest(BaseModel):
    workflow_name: str = "b2b_refund_remediation"
    request_text: str = "Customer Acme says they were charged twice for invoice INV-9281. Verify the issue and process the appropriate resolution."
    organization_id: str = "org_acme"
    model_name: str = "mock-reliable-v1"
    auto_approve_if_reviewed: bool = False


class ResolveApprovalRequest(BaseModel):
    status: ApprovalStatus = ApprovalStatus.APPROVED
    reviewer_id: str = "operator_alice"
    comment: Optional[str] = "Verified duplicate Stripe transactions. Approved."


class EvaluateProposalRequest(BaseModel):
    proposal: ActionProposal


class RunChaosRequest(BaseModel):
    scenario: ChaosScenarioType


class ReplayRequest(BaseModel):
    original_run_id: str
    candidate_model: str = "mock-candidate-v2"
    candidate_prompt_version: str = "v2"


@app.get("/health")
def health_check():
    return {"status": "HEALTHY", "platform": "DeployOS", "version": "0.1.0", "timestamp": datetime.now(timezone.utc)}


@app.get("/api/metrics")
def get_metrics():
    summary = metrics.get_summary()
    return {
        **summary,
        "active_runs": len([r for r in durable_engine.runs.values() if r.status == WorkflowState.RUNNING]),
        "pending_approvals": len([a for a in policy_engine.approvals_db.values() if a.status == ApprovalStatus.PENDING]),
    }


# Workflows
@app.post("/api/workflows/run")
async def run_workflow(req: TriggerWorkflowRequest):
    provider = get_model_provider(req.model_name)
    workflow = CustomerRefundWorkflow(provider)

    result = await workflow.run(
        request_text=req.request_text,
        organization_id=req.organization_id,
        auto_approve_if_reviewed=req.auto_approve_if_reviewed,
    )
    run = result["run"]
    return {
        "run_id": run.run_id,
        "workflow_id": run.workflow_id,
        "status": run.status.value,
        "success": result.get("success", False),
        "verdict": result.get("verdict"),
        "suspended": result.get("suspended", False),
        "approval_id": result.get("approval_id"),
        "reason": result.get("reason"),
        "events_count": len(run.events),
        "tool_calls_count": len(run.tool_calls),
    }


@app.get("/api/workflows/runs")
def list_runs():
    return [
        {
            "run_id": r.run_id,
            "workflow_id": r.workflow_id,
            "workflow_name": r.workflow_name,
            "status": r.status.value,
            "model_name": r.model_name,
            "start_time": r.start_time,
            "end_time": r.end_time,
            "events_count": len(r.events),
            "tool_calls_count": len(r.tool_calls),
            "error": r.error,
        }
        for r in durable_engine.runs.values()
    ]


@app.get("/api/workflows/runs/{run_id}")
def get_run_details(run_id: str):
    run = durable_engine.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


# Human Approvals
@app.get("/api/approvals")
def list_approvals():
    return list(policy_engine.approvals_db.values())


@app.post("/api/approvals/{approval_id}/resolve")
async def resolve_approval(approval_id: str, req: ResolveApprovalRequest):
    try:
        resolved = policy_engine.resolve_approval(
            approval_id=approval_id,
            status=req.status,
            reviewer_id=req.reviewer_id,
            comment=req.comment,
        )
        # If approved, resume the associated suspended run
        run_to_resume = durable_engine.runs.get(resolved.run_id)
        if run_to_resume and req.status == ApprovalStatus.APPROVED:
            run_to_resume.status = WorkflowState.RUNNING
            # Execute consequential action safely
            last_proposal = run_to_resume.proposals[-1] if run_to_resume.proposals else None
            if last_proposal:
                await durable_engine.execute_authorized_action(
                    resolved.run_id,
                    last_proposal,
                    approval_id=approval_id,
                )
                run_to_resume.status = WorkflowState.COMPLETED
        elif run_to_resume and req.status == ApprovalStatus.REJECTED:
            run_to_resume.status = WorkflowState.FAILED
            run_to_resume.error = f"Human reviewer rejected proposal: {req.comment}"

        return resolved
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# Policies
@app.get("/api/policies")
def list_policies():
    return [
        {"name": "STATE_FRESHNESS", "description": "Ensures entity versions have not mutated during execution."},
        {"name": "TRUST_BOUNDARY", "description": "Blocks financial mutations derived exclusively from untrusted inputs."},
        {"name": "DUPLICATE_ACTION", "description": "Enforces idempotency and prevents double-refunds."},
        {"name": "TRANSACTION_VERIFICATION", "description": "Verifies target transaction exists in billing records."},
        {"name": "REFUND_LIMIT", "threshold_usd": 100.0, "description": "Refunds > $100 require Human Review."},
    ]


@app.post("/api/policies/evaluate")
async def evaluate_custom_proposal(req: EvaluateProposalRequest):
    decision = await policy_engine.evaluate_proposal(req.proposal)
    return decision


# Evals & Benchmarks
@app.post("/api/evals/benchmark")
async def run_benchmark(model_name: str = "mock-reliable-v1"):
    from evals.scenarios.benchmark_suite import BenchmarkSuite
    suite = BenchmarkSuite(model_name=model_name)
    report = await suite.run_all()
    return report


@app.get("/api/evals/leaderboard")
def get_leaderboard():
    return [
        {
            "model": "Claude 3.5 Sonnet",
            "prompt_version": "v1.2",
            "task_success_rate": 96.4,
            "correct_tool_usage": 98.2,
            "unsafe_execution": 0.0,
            "failure_recovery": 92.5,
            "reliability_score": 97.4,
            "cost_per_task": 0.0142,
            "p95_latency_s": 4.2,
        },
        {
            "model": "DeployOS Reliable Agent (Mock)",
            "prompt_version": "v1.0",
            "task_success_rate": 90.0,
            "correct_tool_usage": 100.0,
            "unsafe_execution": 0.0,
            "failure_recovery": 100.0,
            "reliability_score": 96.6,
            "cost_per_task": 0.0001,
            "p95_latency_s": 0.01,
        },
        {
            "model": "GPT-4o",
            "prompt_version": "v1.0",
            "task_success_rate": 94.2,
            "correct_tool_usage": 96.1,
            "unsafe_execution": 0.0,
            "failure_recovery": 88.0,
            "reliability_score": 94.8,
            "cost_per_task": 0.0185,
            "p95_latency_s": 5.1,
        },
        {
            "model": "Llama-3-70B-Instruct",
            "prompt_version": "v0.9",
            "task_success_rate": 86.8,
            "correct_tool_usage": 91.0,
            "unsafe_execution": 1.2,
            "failure_recovery": 76.4,
            "reliability_score": 84.1,
            "cost_per_task": 0.0022,
            "p95_latency_s": 6.8,
        },
    ]


# Replay
@app.post("/api/replay")
async def replay_run(req: ReplayRequest):
    try:
        diff = await replay_engine.replay_run(
            original_run_id=req.original_run_id,
            candidate_model_name=req.candidate_model,
            candidate_prompt_version=req.candidate_prompt_version,
        )
        return diff
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# Chaos Harness
@app.post("/api/chaos/run")
async def trigger_chaos(req: RunChaosRequest):
    result = await chaos_harness.run_scenario(req.scenario)
    return result


# Incidents
@app.get("/api/incidents")
def list_incidents():
    return incident_manager.list_incidents()


@app.post("/api/incidents/{incident_id}/regression")
def create_regression_from_incident(incident_id: str):
    try:
        case_id = incident_manager.synthesize_regression_case(incident_id)
        return {"incident_id": incident_id, "regression_case_id": case_id, "status": "REGRESSION_ADDED"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# Data Store Inspection
@app.get("/api/store/state")
def get_store_state():
    return {
        "customers": enterprise_store.customers,
        "invoices": enterprise_store.invoices,
        "transactions": enterprise_store.transactions,
        "idempotency_store": enterprise_store.idempotency_store,
        "sent_emails": enterprise_store.sent_emails,
    }
