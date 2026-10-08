"""Unit Tests for Tool Infrastructure and Idempotency Protection."""

import pytest
from packages.schemas.tools import RiskTier
from packages.tools.registry import default_registry
from packages.tools.store import enterprise_store


@pytest.fixture(autouse=True)
def reset_store():
    enterprise_store.reset()


@pytest.mark.asyncio
async def test_tier0_read_tools():
    # Customer
    c_call = await default_registry.execute("get_customer", {"customer_id": "cus_acme_9281"})
    assert c_call.success
    assert c_call.result["name"] == "Acme Corporation"
    assert c_call.risk_tier == RiskTier.TIER_0_READ_ONLY

    # Invoice
    i_call = await default_registry.execute("get_invoice", {"invoice_id": "inv_9281"})
    assert i_call.success
    assert i_call.result["amount"] == 249.00

    # Payment
    p_call = await default_registry.execute("get_payment", {"transaction_id": "txn_5521"})
    assert p_call.success
    assert p_call.result["status"] == "SUCCEEDED"


@pytest.mark.asyncio
async def test_idempotent_refund_execution():
    idempotency_key = "wf_test_101:issue_refund:txn_5521:abcd1234efgh5678"

    # First execution
    call1 = await default_registry.execute(
        "issue_refund",
        {"transaction_id": "txn_5521", "amount": 249.00, "idempotency_key": idempotency_key},
    )
    assert call1.success
    assert call1.result["refund_id"] is not None
    orig_refund_id = call1.result["refund_id"]

    # Second identical execution (e.g. network retry)
    call2 = await default_registry.execute(
        "issue_refund",
        {"transaction_id": "txn_5521", "amount": 249.00, "idempotency_key": idempotency_key},
    )
    assert call2.success
    assert call2.result["refund_id"] == orig_refund_id
    assert call2.result.get("idempotent_cached_response") is True
