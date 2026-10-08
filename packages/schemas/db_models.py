"""SQLAlchemy Async ORM Database Models for DeployOS."""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    Enum as SAEnum,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return uuid.uuid4().hex


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    """Multi-tenant organization account boundary."""
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(128), nullable=False)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    tier = Column(String(32), default="ENTERPRISE")
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    workflows = relationship("Workflow", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    """User account with RBAC roles (ADMIN, OPERATOR, REVIEWER, VIEWER)."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(128), nullable=False)
    role = Column(String(32), default="OPERATOR")  # ADMIN, OPERATOR, REVIEWER, VIEWER
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    organization = relationship("Organization", back_populates="users")


class Agent(Base):
    """Registered AI Agent identity."""
    __tablename__ = "agents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    risk_tier = Column(Integer, default=3)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    versions = relationship("AgentVersion", back_populates="agent", cascade="all, delete-orphan")


class AgentVersion(Base):
    """Immutably versioned prompt and configuration definitions for an agent."""
    __tablename__ = "agent_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    version_tag = Column(String(32), nullable=False)  # e.g., 'v1', 'v2.1'
    system_prompt = Column(Text, nullable=False)
    model_name = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    agent = relationship("Agent", back_populates="versions")


class Workflow(Base):
    """Registered operational workflow definition."""
    __tablename__ = "workflows"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    organization = relationship("Organization", back_populates="workflows")
    runs = relationship("WorkflowRun", back_populates="workflow", cascade="all, delete-orphan")


class WorkflowRun(Base):
    """Execution instance of a workflow."""
    __tablename__ = "workflow_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workflow_id = Column(String(36), ForeignKey("workflows.id"), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="PENDING", index=True)
    input_payload = Column(JSON, default=dict)
    output_payload = Column(JSON, nullable=True)
    model_name = Column(String(64), default="mock-reliable-v1")
    prompt_version = Column(String(32), default="v1")
    policy_version = Column(String(32), default="standard-2026")
    duration_ms = Column(Float, default=0.0)
    total_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    workflow = relationship("Workflow", back_populates="runs")
    events = relationship("RunEvent", back_populates="run", cascade="all, delete-orphan")
    tool_calls = relationship("ToolCall", back_populates="run", cascade="all, delete-orphan")
    proposals = relationship("ActionProposal", back_populates="run", cascade="all, delete-orphan")


class RunEvent(Base):
    """Chronological execution trace event in a workflow run."""
    __tablename__ = "run_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("workflow_runs.id"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    event_type = Column(String(32), nullable=False)
    component = Column(String(64), nullable=False)
    message = Column(Text, nullable=False)
    payload = Column(JSON, default=dict)
    latency_ms = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    run = relationship("WorkflowRun", back_populates="events")


class Tool(Base):
    """Registered tool definition in the platform."""
    __tablename__ = "tools"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=True, index=True)
    name = Column(String(64), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False)
    risk_tier = Column(Integer, nullable=False)  # 0 to 3
    input_schema = Column(JSON, nullable=False)
    output_schema = Column(JSON, nullable=True)
    idempotent = Column(Boolean, default=True)
    timeout_seconds = Column(Float, default=30.0)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class ToolCall(Base):
    """Log of a tool execution with idempotency key."""
    __tablename__ = "tool_calls"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("workflow_runs.id"), nullable=False, index=True)
    tool_name = Column(String(64), nullable=False, index=True)
    risk_tier = Column(Integer, nullable=False)
    arguments = Column(JSON, nullable=False)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    latency_ms = Column(Float, default=0.0)
    idempotency_key = Column(String(128), nullable=True, index=True)
    success = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    run = relationship("WorkflowRun", back_populates="tool_calls")


class ActionProposal(Base):
    """Structured proposal generated by an agent reasoning step."""
    __tablename__ = "action_proposals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("workflow_runs.id"), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    agent_id = Column(String(64), nullable=False)
    action = Column(String(64), nullable=False)
    target = Column(String(128), nullable=False)
    parameters = Column(JSON, nullable=False)
    reason = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    evidence_ids = Column(JSON, default=list)
    state_version = Column(Integer, default=1)
    action_hash = Column(String(64), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    trust_level = Column(String(32), default="CUSTOMER_EMAIL")
    risk_tier = Column(Integer, default=3)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    run = relationship("WorkflowRun", back_populates="proposals")
    decisions = relationship("PolicyDecision", back_populates="proposal", cascade="all, delete-orphan")
    approval = relationship("Approval", back_populates="proposal", uselist=False, cascade="all, delete-orphan")


class PolicyDecision(Base):
    """Deterministic verdict produced by the policy engine for a proposal."""
    __tablename__ = "policy_decisions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    proposal_id = Column(String(36), ForeignKey("action_proposals.id"), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    decision = Column(String(16), nullable=False, index=True)  # EXECUTE, REVIEW, RETRY, REJECT
    policy_name = Column(String(64), nullable=False)
    reason = Column(Text, nullable=False)
    action_hash = Column(String(64), nullable=False, index=True)
    required_approver_role = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    proposal = relationship("ActionProposal", back_populates="decisions")


class Approval(Base):
    """Human-in-the-loop review ticket cryptographically bound to an action hash."""
    __tablename__ = "approvals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    proposal_id = Column(String(36), ForeignKey("action_proposals.id"), unique=True, nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    action_hash = Column(String(64), nullable=False, index=True)
    status = Column(String(32), default="PENDING", index=True)  # PENDING, APPROVED, REJECTED, MORE_EVIDENCE_REQUESTED, INVALIDATED
    reviewer_id = Column(String(64), nullable=True)
    reviewer_comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    proposal = relationship("ActionProposal", back_populates="approval")


class Document(Base):
    """Knowledge base or case document with provenance tracking."""
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    source_uri = Column(String(512), nullable=False)
    trust_level = Column(String(32), nullable=False, index=True)
    author = Column(String(128), nullable=True)
    checksum = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """Chunk of document text for hybrid search and provenance extraction."""
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    document = relationship("Document", back_populates="chunks")


class Incident(Base):
    """Production agent failure ticket for root cause analysis."""
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("workflow_runs.id"), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    severity = Column(String(16), default="HIGH", index=True)  # LOW, MEDIUM, HIGH, CRITICAL
    root_cause_category = Column(String(32), nullable=False, index=True)
    status = Column(String(32), default="OPEN", index=True)
    error_trace = Column(Text, nullable=False)
    run_trace_summary = Column(JSON, default=dict)
    reproduction_eval_case_id = Column(String(64), nullable=True)
    mitigation_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class Evaluation(Base):
    """Evaluation suite registry."""
    __tablename__ = "evaluations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    suite_name = Column(String(128), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    runs = relationship("EvaluationRun", back_populates="evaluation", cascade="all, delete-orphan")


class EvaluationCase(Base):
    """Individual test scenario case within an evaluation suite."""
    __tablename__ = "evaluation_cases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    evaluation_id = Column(String(36), ForeignKey("evaluations.id"), nullable=False, index=True)
    scenario_id = Column(String(64), nullable=False, index=True)
    goal = Column(Text, nullable=False)
    expected_action = Column(String(64), nullable=False)
    failure_conditions = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class EvaluationRun(Base):
    """Benchmark execution run result report."""
    __tablename__ = "evaluation_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    evaluation_id = Column(String(36), ForeignKey("evaluations.id"), nullable=False, index=True)
    model_name = Column(String(64), nullable=False, index=True)
    prompt_version = Column(String(32), default="v1")
    total_cases = Column(Integer, default=0)
    task_success_rate = Column(Float, default=0.0)
    unsafe_action_rate = Column(Float, default=0.0)
    failure_recovery_rate = Column(Float, default=0.0)
    reliability_score = Column(Float, default=0.0)
    latency_p95_ms = Column(Float, default=0.0)
    total_cost_usd = Column(Float, default=0.0)
    metrics_json = Column(JSON, default=dict)
    case_results = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    evaluation = relationship("Evaluation", back_populates="runs")


class ModelUsage(Base):
    """Audit of token consumption, latency, and cost per inference invocation."""
    __tablename__ = "model_usage"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("workflow_runs.id"), nullable=True, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    model_name = Column(String(64), nullable=False)
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=utc_now)
