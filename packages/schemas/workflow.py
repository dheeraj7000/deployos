"""Workflow Run, Event, and Execution Trace Schemas."""

from enum import Enum
from datetime import datetime, timezone
from typing import Optional, Any
from pydantic import BaseModel, Field
from packages.schemas.actions import ActionProposal, PolicyDecision, ApprovalRequest
from packages.schemas.tools import ToolCall


class WorkflowState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUSPENDED_APPROVAL = "SUSPENDED_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class EventType(str, Enum):
    WORKFLOW_START = "WORKFLOW_START"
    STEP_START = "STEP_START"
    RETRIEVAL = "RETRIEVAL"
    REASONING = "REASONING"
    TOOL_PROPOSAL = "TOOL_PROPOSAL"
    TOOL_EXECUTE = "TOOL_EXECUTE"
    POLICY_CHECK = "POLICY_CHECK"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_RESOLVED = "APPROVAL_RESOLVED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    ERROR = "ERROR"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"


class RunEvent(BaseModel):
    event_id: str
    run_id: str
    workflow_id: str
    sequence: int
    event_type: EventType
    component: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: float = 0.0


class WorkflowRun(BaseModel):
    run_id: str
    workflow_id: str
    workflow_name: str
    organization_id: str
    status: WorkflowState = WorkflowState.PENDING
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: Optional[dict[str, Any]] = None
    model_name: str = "mock-reliable-v1"
    prompt_version: str = "v1"
    policy_version: str = "standard-2026"
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    error: Optional[str] = None
    events: list[RunEvent] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    proposals: list[ActionProposal] = Field(default_factory=list)
    policy_decisions: list[PolicyDecision] = Field(default_factory=list)
    approvals: list[ApprovalRequest] = Field(default_factory=list)
