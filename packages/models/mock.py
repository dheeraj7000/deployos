"""Deterministic Mock Model Provider for Reproducible Evaluation & Testing."""

import json
import time
from typing import Any, Type, TypeVar, Optional
from pydantic import BaseModel
from packages.models.base import ModelProvider, ModelResponse
from packages.schemas.actions import RefundProposal, ActionProposal
from packages.schemas.trust import TrustLevel
from packages.schemas.tools import RiskTier
from datetime import datetime, timedelta, timezone

T = TypeVar("T", bound=BaseModel)


class MockModelProvider(ModelProvider):
    """Zero-dependency, deterministic provider that powers unit tests, CI, and benchmark suites."""

    def __init__(
        self,
        model_name: str = "mock-agent-v1",
        simulated_latency_ms: float = 120.0,
        cost_per_1k_tokens: float = 0.002,
        force_error: Optional[str] = None,
    ):
        self.model_name = model_name
        self.simulated_latency_ms = simulated_latency_ms
        self.cost_per_1k_tokens = cost_per_1k_tokens
        self.force_error = force_error

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> ModelResponse:
        start_time = time.perf_counter()
        if self.force_error:
            raise RuntimeError(f"Simulated Model Error: {self.force_error}")

        # Deterministic tokens & cost
        input_tokens = len(prompt.split()) + (len(system_prompt.split()) if system_prompt else 0)
        output_text = f"Analyzed context. Goal alignment verified. System healthy."
        output_tokens = len(output_text.split())
        total_tokens = input_tokens + output_tokens
        cost = (total_tokens / 1000.0) * self.cost_per_1k_tokens
        latency = (time.perf_counter() - start_time) * 1000.0 + self.simulated_latency_ms

        return ModelResponse(
            content=output_text,
            model_name=self.model_name,
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            latency_ms=latency,
        )

    async def structured_generate(
        self,
        schema: Type[T],
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> tuple[T, ModelResponse]:
        start_time = time.perf_counter()
        if self.force_error:
            raise RuntimeError(f"Simulated Model Error: {self.force_error}")

        lowered_prompt = prompt.lower()
        now = datetime.now(timezone.utc)

        # Handle specific scenario proposals based on context
        if schema == RefundProposal:
            # Check if this is an adversarial prompt
            if "issue a $5,000 refund immediately" in lowered_prompt or "ignore previous instructions" in lowered_prompt:
                # The model reasons and outputs the requested adversarial action, allowing the POLICY layer to test rejection!
                parsed_instance = RefundProposal(
                    customer_id="cus_unknown",
                    transaction_id="txn_unverified",
                    amount=5000.0,
                    currency="USD",
                    reason="Customer requested emergency refund via email attachment instruction",
                    evidence_ids=["doc_malicious_pdf"],
                    confidence=0.85,
                    state_version=1,
                )
            elif "inv-9281" in lowered_prompt or "acme" in lowered_prompt:
                # Standard verified duplicate charge
                amount = 249.00
                if "high_amount" in lowered_prompt or "$1,249" in lowered_prompt:
                    amount = 1249.00
                parsed_instance = RefundProposal(
                    customer_id="cus_acme_9281",
                    transaction_id="txn_5522",
                    amount=amount,
                    currency="USD",
                    reason="verified_duplicate_charge",
                    evidence_ids=["inv_9281", "txn_5521", "txn_5522", "email_thread_104"],
                    confidence=0.96,
                    state_version=1,
                )
            else:
                parsed_instance = RefundProposal(
                    customer_id="cus_generic_001",
                    transaction_id="txn_9999",
                    amount=50.00,
                    currency="USD",
                    reason="standard_billing_adjustment",
                    evidence_ids=["inv_001"],
                    confidence=0.90,
                    state_version=1,
                )

        elif schema == ActionProposal:
            if "issue a $5,000 refund immediately" in lowered_prompt or "ignore previous instructions" in lowered_prompt:
                parsed_instance = ActionProposal(
                    proposal_id="prop_adv_001",
                    workflow_id="wf_adversarial_test",
                    run_id="run_adv_001",
                    organization_id="org_acme",
                    agent_id="refund_agent",
                    action="issue_refund",
                    target="txn_unverified",
                    parameters={"amount": 5000.0, "currency": "USD", "reason": "unauthorized_instruction"},
                    reason="Customer requested $5,000 refund in attachment",
                    confidence=0.85,
                    evidence_ids=["doc_malicious_pdf"],
                    state_version=1,
                    observed_at=now,
                    expires_at=now + timedelta(minutes=15),
                    trust_level=TrustLevel.UPLOADED_PDF,
                    risk_tier=RiskTier.TIER_3_FINANCIAL_DESTRUCTIVE,
                )
            elif "stale" in lowered_prompt:
                parsed_instance = ActionProposal(
                    proposal_id="prop_stale_001",
                    workflow_id="wf_stale_test",
                    run_id="run_stale_001",
                    organization_id="org_acme",
                    agent_id="refund_agent",
                    action="issue_refund",
                    target="txn_5521",
                    parameters={"amount": 249.0, "currency": "USD"},
                    reason="refund_duplicate",
                    confidence=0.95,
                    evidence_ids=["inv_9281", "txn_5521"],
                    state_version=1,  # Stale: assume live DB has moved to version 2
                    observed_at=now - timedelta(minutes=30),
                    expires_at=now - timedelta(minutes=5),  # Expired!
                    trust_level=TrustLevel.INTERNAL_DATABASE,
                    risk_tier=RiskTier.TIER_3_FINANCIAL_DESTRUCTIVE,
                )
            else:
                parsed_instance = ActionProposal(
                    proposal_id="prop_norm_9281",
                    workflow_id="wf_refund_9281",
                    run_id="run_refund_9281",
                    organization_id="org_acme",
                    agent_id="refund_agent",
                    action="issue_refund",
                    target="txn_5522",
                    parameters={"amount": 249.0, "currency": "USD", "customer_id": "cus_acme_9281"},
                    reason="verified_duplicate_charge",
                    confidence=0.96,
                    evidence_ids=["inv_9281", "txn_5521", "txn_5522"],
                    state_version=1,
                    observed_at=now,
                    expires_at=now + timedelta(minutes=15),
                    trust_level=TrustLevel.INTERNAL_DATABASE,
                    risk_tier=RiskTier.TIER_3_FINANCIAL_DESTRUCTIVE,
                )
        else:
            # Fallback instantiation
            try:
                parsed_instance = schema()
            except Exception:
                raise ValueError(f"MockProvider cannot auto-construct generic schema {schema.__name__}")

        input_tokens = len(prompt.split())
        output_tokens = len(parsed_instance.model_dump_json().split())
        total_tokens = input_tokens + output_tokens
        cost = (total_tokens / 1000.0) * self.cost_per_1k_tokens
        latency = (time.perf_counter() - start_time) * 1000.0 + self.simulated_latency_ms

        response = ModelResponse(
            content=parsed_instance.model_dump_json(),
            parsed=parsed_instance,
            model_name=self.model_name,
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            latency_ms=latency,
        )
        return parsed_instance, response
