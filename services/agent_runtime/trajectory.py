"""Trajectory Recording and Step-by-Step Observability."""

from datetime import datetime, timezone
from typing import Any, Optional
from packages.schemas.eval import TrajectoryStep, TrajectoryTrace


class TrajectoryRecorder:
    """Captures the granular execution trajectory of an agent workflow."""

    def __init__(self, run_id: str, scenario_id: str, workflow_name: str, goal: str, model_name: str = "mock-v1", prompt_version: str = "v1"):
        self.run_id = run_id
        self.scenario_id = scenario_id
        self.workflow_name = workflow_name
        self.goal = goal
        self.model_name = model_name
        self.prompt_version = prompt_version
        self.steps: list[TrajectoryStep] = []
        self.failure_injected: bool = False
        self.recovered_from_failure: bool = False
        self.unsafe_action_executed: bool = False
        self.escalated_to_human: bool = False

    def record_step(
        self,
        phase: str,
        thought: Optional[str] = None,
        input_data: Optional[dict[str, Any]] = None,
        output_data: Optional[dict[str, Any]] = None,
        tool_name: Optional[str] = None,
        policy_verdict: Optional[str] = None,
        latency_ms: float = 0.0,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        is_safe: bool = True,
        trusted: bool = True,
    ) -> TrajectoryStep:
        step = TrajectoryStep(
            step_index=len(self.steps) + 1,
            phase=phase,
            thought=thought,
            input_data=input_data or {},
            output_data=output_data or {},
            tool_name=tool_name,
            policy_verdict=policy_verdict,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            is_safe=is_safe,
            trusted=trusted,
        )
        self.steps.append(step)
        if not is_safe:
            self.unsafe_action_executed = True
        return step

    def finalize(self, success: bool) -> TrajectoryTrace:
        total_cost = sum(s.cost_usd for s in self.steps)
        total_duration = sum(s.latency_ms for s in self.steps)
        return TrajectoryTrace(
            run_id=self.run_id,
            scenario_id=self.scenario_id,
            workflow_name=self.workflow_name,
            goal=self.goal,
            model_name=self.model_name,
            prompt_version=self.prompt_version,
            steps=self.steps,
            final_success=success,
            unsafe_action_executed=self.unsafe_action_executed,
            failure_injected=self.failure_injected,
            recovered_from_failure=self.recovered_from_failure,
            escalated_to_human=self.escalated_to_human,
            total_cost_usd=round(total_cost, 4),
            total_duration_ms=round(total_duration, 2),
        )
