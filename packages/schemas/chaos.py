"""Chaos Engineering and Incident Management Schemas."""

from enum import Enum
from datetime import datetime, timezone
from typing import Optional, Any
from pydantic import BaseModel, Field


class ChaosScenarioType(str, Enum):
    API_TIMEOUT = "api-timeout"
    TOOL_DOWN = "tool-down"
    STALE_DATA = "stale-data"
    MALFORMED_JSON = "malformed-json"
    DUPLICATE_WEBHOOK = "duplicate-webhook"
    PROMPT_INJECTION = "prompt-injection"
    SCHEMA_CHANGE = "schema-change"
    RATE_LIMIT = "rate-limit"
    CORRUPTED_PDF = "corrupted-pdf"
    MODEL_TIMEOUT = "model-timeout"


class ChaosExperimentResult(BaseModel):
    experiment_id: str
    scenario_type: ChaosScenarioType
    target_component: str
    injection_details: dict[str, Any] = Field(default_factory=dict)
    workflow_recovered: bool
    state_corrupted: bool
    unsafe_execution_occurred: bool
    escalation_appropriate: bool
    recovery_duration_ms: float
    summary: str
    error_message: Optional[str] = None
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IncidentSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RootCauseCategory(str, Enum):
    PROMPT_INJECTION = "PROMPT_INJECTION"
    STALE_STATE = "STALE_STATE"
    TOOL_FAILURE = "TOOL_FAILURE"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    UNEXPECTED_EXCEPTION = "UNEXPECTED_EXCEPTION"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    REGRESSION_ADDED = "REGRESSION_ADDED"


class Incident(BaseModel):
    incident_id: str
    run_id: str
    workflow_id: str
    title: str
    severity: IncidentSeverity
    root_cause_category: RootCauseCategory
    status: IncidentStatus = IncidentStatus.OPEN
    error_trace: str
    run_trace_summary: dict[str, Any] = Field(default_factory=dict)
    reproduction_eval_case_id: Optional[str] = None
    mitigation_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
