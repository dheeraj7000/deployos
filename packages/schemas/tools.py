"""Tool Schemas and Risk Classification Tiers."""

from enum import IntEnum
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class RiskTier(IntEnum):
    """Consequence classification for agent tools."""
    TIER_0_READ_ONLY = 0             # Read-only queries, search, retrieval (autonomous)
    TIER_1_REVERSIBLE_WRITE = 1      # Notes, drafts, internal logs (usually autonomous)
    TIER_2_EXTERNAL_COMMUNICATION = 2 # Sending emails, Slack messages, webhooks (conditional review)
    TIER_3_FINANCIAL_DESTRUCTIVE = 3  # Refunds, deletions, contracts, mutations (strict authorization)

    @property
    def label(self) -> str:
        labels = {
            RiskTier.TIER_0_READ_ONLY: "Tier 0 (Read-Only)",
            RiskTier.TIER_1_REVERSIBLE_WRITE: "Tier 1 (Reversible Write)",
            RiskTier.TIER_2_EXTERNAL_COMMUNICATION: "Tier 2 (External Communication)",
            RiskTier.TIER_3_FINANCIAL_DESTRUCTIVE: "Tier 3 (Financial / Destructive)",
        }
        return labels.get(self, "Unknown")


class RetryPolicy(BaseModel):
    max_attempts: int = 3
    initial_interval_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    retryable_exceptions: list[str] = Field(default_factory=lambda: ["TimeoutError", "ConnectionError", "HTTPStatusError_503"])


class ToolDefinition(BaseModel):
    name: str
    description: str
    risk_tier: RiskTier
    input_schema: dict[str, Any]
    output_schema: Optional[dict[str, Any]] = None
    idempotent: bool = True
    timeout_seconds: float = 30.0
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    required_permissions: list[str] = Field(default_factory=list)


class ToolCall(BaseModel):
    call_id: str
    tool_name: str
    risk_tier: RiskTier
    arguments: dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    idempotency_key: Optional[str] = None
    success: bool = True
