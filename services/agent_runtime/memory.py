"""Agent Memory System: Working, Episodic, Semantic, and Procedural."""

from datetime import datetime, timezone
from typing import Any, Optional
from packages.schemas.trust import TrustLevel, DocumentChunk, DocumentProvenance


class AgentMemory:
    """Multi-tiered auditable agent memory."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        # Working memory: active state for the current run
        self.working_memory: dict[str, Any] = {}
        # Episodic memory: timeline of actions taken and observations made
        self.episodic_memory: list[dict[str, Any]] = []
        # Semantic memory: verified knowledge chunks with provenance
        self.semantic_memory: list[DocumentChunk] = []
        # Procedural memory: standard workflows and operating procedures
        self.procedural_memory: list[str] = [
            "Step 1: Ingest request and extract customer & invoice IDs",
            "Step 2: Query CRM and retrieve current customer status and state version",
            "Step 3: Query Stripe payments and compare invoice charges to detect duplicate transactions",
            "Step 4: Formulate structured ActionProposal and submit to Policy Engine",
            "Step 5: Await policy evaluation (EXECUTE, REVIEW, RETRY, REJECT)",
            "Step 6: If reviewed and approved, execute consequential refund with idempotency key",
            "Step 7: Update CRM audit notes and notify customer",
        ]

    def set_working(self, key: str, value: Any) -> None:
        self.working_memory[key] = value

    def get_working(self, key: str, default: Any = None) -> Any:
        return self.working_memory.get(key, default)

    def record_episode(self, action_type: str, details: dict[str, Any]) -> None:
        self.episodic_memory.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": action_type,
            "details": details,
        })

    def add_semantic_chunk(self, content: str, source: str, trust_level: TrustLevel) -> DocumentChunk:
        chunk_id = f"chunk_{len(self.semantic_memory) + 1}"
        chunk = DocumentChunk(
            chunk_id=chunk_id,
            document_id=source,
            content=content,
            provenance=DocumentProvenance(
                document_id=source,
                source=source,
                trust_level=trust_level,
            ),
        )
        self.semantic_memory.append(chunk)
        return chunk
