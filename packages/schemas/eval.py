"""Trajectory-level Evaluation, Benchmark, and Replay Schemas."""

from datetime import datetime, timezone
from typing import Optional, Any
from pydantic import BaseModel, Field


class TrajectoryStep(BaseModel):
    step_index: int
    phase: str  # retrieval, reasoning, tool_selection, proposal, policy, action
    thought: Optional[str] = None
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    tool_name: Optional[str] = None
    policy_verdict: Optional[str] = None
    latency_ms: float = 0.0
    tokens_used: int = 0
    cost_usd: float = 0.0
    is_safe: bool = True
    trusted: bool = True


class TrajectoryTrace(BaseModel):
    run_id: str
    scenario_id: str
    workflow_name: str
    goal: str
    model_name: str
    prompt_version: str
    steps: list[TrajectoryStep] = Field(default_factory=list)
    final_success: bool = False
    unsafe_action_executed: bool = False
    failure_injected: bool = False
    recovered_from_failure: bool = False
    escalated_to_human: bool = False
    total_cost_usd: float = 0.0
    total_duration_ms: float = 0.0


class EvaluationMetrics(BaseModel):
    task_success_rate: float = Field(ge=0.0, le=100.0)      # % completed_tasks / attempted_tasks
    tool_selection_accuracy: float = Field(ge=0.0, le=100.0) # % correct tool picked
    argument_accuracy: float = Field(ge=0.0, le=100.0)      # % valid & accurate arguments
    retrieval_precision: float = Field(ge=0.0, le=100.0)    # % retrieved chunks that supported the task
    unsafe_action_rate: float = Field(ge=0.0, le=100.0)     # Target: 0.0%
    failure_recovery_rate: float = Field(ge=0.0, le=100.0)  # % recovered from injected failures
    appropriate_escalation_rate: float = Field(ge=0.0, le=100.0) # % correctly escalated vs over/under escalated
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    average_cost_usd: float = 0.0
    reliability_score: float = Field(ge=0.0, le=100.0)     # Composite benchmark score (0 - 100)


class BenchmarkReport(BaseModel):
    report_id: str
    suite_name: str
    model_name: str
    prompt_version: str
    policy_version: str
    total_cases: int
    metrics: EvaluationMetrics
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    case_results: list[dict[str, Any]] = Field(default_factory=list)


class ReplayComparison(BaseModel):
    original_run_id: str
    candidate_run_id: str
    scenario_id: str
    original_model: str
    candidate_model: str
    original_prompt_version: str
    candidate_prompt_version: str
    original_success: bool
    candidate_success: bool
    original_cost_usd: float
    candidate_cost_usd: float
    original_tool_calls_count: int
    candidate_tool_calls_count: int
    original_duration_ms: float
    candidate_duration_ms: float
    diff_summary: str
    step_diffs: list[dict[str, Any]] = Field(default_factory=list)
