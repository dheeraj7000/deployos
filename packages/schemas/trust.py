"""Data Provenance and Trust Boundary Schemas."""

from enum import Enum
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class TrustLevel(str, Enum):
    """Trust hierarchy for all retrieved content and inputs."""
    SYSTEM_POLICY = "SYSTEM_POLICY"          # Trusted internal business rules / policy engine
    INTERNAL_DATABASE = "INTERNAL_DATABASE"  # Trusted enterprise databases (CRM, Stripe, ERP)
    EMPLOYEE_MESSAGE = "EMPLOYEE_MESSAGE"    # Semi-trusted authenticated internal employee communication
    CUSTOMER_EMAIL = "CUSTOMER_EMAIL"        # Untrusted external customer content
    UPLOADED_PDF = "UPLOADED_PDF"            # Untrusted arbitrary file attachments
    PUBLIC_WEB = "PUBLIC_WEB"                # Untrusted external web content

    @property
    def is_trusted(self) -> bool:
        return self in (TrustLevel.SYSTEM_POLICY, TrustLevel.INTERNAL_DATABASE)

    @property
    def numeric_weight(self) -> float:
        weights = {
            TrustLevel.SYSTEM_POLICY: 1.0,
            TrustLevel.INTERNAL_DATABASE: 1.0,
            TrustLevel.EMPLOYEE_MESSAGE: 0.75,
            TrustLevel.CUSTOMER_EMAIL: 0.25,
            TrustLevel.UPLOADED_PDF: 0.20,
            TrustLevel.PUBLIC_WEB: 0.10,
        }
        return weights.get(self, 0.0)


class DocumentProvenance(BaseModel):
    """Provenance tracking for any chunk of data provided to reasoning."""
    document_id: str
    source: str
    page: Optional[int] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    trust_level: TrustLevel
    author: Optional[str] = None
    checksum: Optional[str] = None


class DocumentChunk(BaseModel):
    """Normalized chunk for hybrid retrieval with provenance metadata."""
    chunk_id: str
    document_id: str
    content: str
    provenance: DocumentProvenance
    metadata: dict[str, Any] = Field(default_factory=dict)
