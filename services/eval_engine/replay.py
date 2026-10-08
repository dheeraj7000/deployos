"""Historical Run Replay Engine and Trajectory Diff Analyzer."""

from typing import Optional, Any
from packages.models.adapters import get_model_provider
from packages.schemas.eval import ReplayComparison, TrajectoryTrace
from packages.schemas.workflow import WorkflowRun
from services.agent_runtime.durable_engine import durable_engine
from workflows.refunds.refund_workflow import CustomerRefundWorkflow


class ReplayEngine:
    """Replays historical workflow runs with different models, prompts, or policies."""

    @staticmethod
    async def replay_run(
        original_run_id: str,
        candidate_model_name: str,
        candidate_prompt_version: str = "v2",
        auto_approve: bool = True,
    ) -> ReplayComparison:
        original_run = durable_engine.runs.get(original_run_id)
        if not original_run:
            raise KeyError(f"Original run '{original_run_id}' not found in registry")

        original_model = original_run.model_name
        original_prompt_version = original_run.prompt_version
        original_success = (original_run.status.value == "COMPLETED")
        original_tool_count = len(original_run.tool_calls)
        original_duration = original_run.duration_ms or 420.0
        original_cost = original_run.estimated_cost_usd or 0.004

        # Instantiate candidate model provider
        candidate_provider = get_model_provider(candidate_model_name)

        # Execute candidate workflow run with the exact same input payload
        input_req = original_run.input_payload.get(
            "request_text",
            "Customer Acme says they were charged twice for invoice INV-9281. Verify the issue and process the appropriate resolution."
        )

        wf = CustomerRefundWorkflow(candidate_provider)
        candidate_result = await wf.run(
            request_text=input_req,
            organization_id=original_run.organization_id,
            auto_approve_if_reviewed=auto_approve,
        )

        cand_run: WorkflowRun = candidate_result["run"]
        cand_trace: TrajectoryTrace = candidate_result["trace"]

        cand_success = candidate_result["success"]
        cand_tool_count = len(cand_run.tool_calls)
        cand_duration = cand_trace.total_duration_ms
        cand_cost = cand_trace.total_cost_usd

        # Compute diff summary
        diff_summary = (
            f"Replay compared {original_model} ({original_prompt_version}) against {candidate_model_name} ({candidate_prompt_version}). "
            f"Success: {original_success} -> {cand_success}. "
            f"Tool calls: {original_tool_count} -> {cand_tool_count}. "
            f"Cost: ${original_cost:.4f} -> ${cand_cost:.4f}. "
            f"Latency: {original_duration:.1f}ms -> {cand_duration:.1f}ms."
        )

        step_diffs = [
            {
                "step_index": idx + 1,
                "candidate_phase": step.phase,
                "candidate_tool": step.tool_name,
                "candidate_verdict": step.policy_verdict,
                "latency_ms": step.latency_ms,
            }
            for idx, step in enumerate(cand_trace.steps)
        ]

        return ReplayComparison(
            original_run_id=original_run_id,
            candidate_run_id=cand_run.run_id,
            scenario_id="b2b_duplicate_charge_inv_9281",
            original_model=original_model,
            candidate_model=candidate_model_name,
            original_prompt_version=original_prompt_version,
            candidate_prompt_version=candidate_prompt_version,
            original_success=original_success,
            candidate_success=cand_success,
            original_cost_usd=original_cost,
            candidate_cost_usd=cand_cost,
            original_tool_calls_count=original_tool_count,
            candidate_tool_calls_count=cand_tool_count,
            original_duration_ms=original_duration,
            candidate_duration_ms=cand_duration,
            diff_summary=diff_summary,
            step_diffs=step_diffs,
        )


replay_engine = ReplayEngine()
