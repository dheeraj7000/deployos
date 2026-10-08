"""Temporal Python SDK Workflow Definitions for DeployOS."""

from datetime import timedelta
from typing import Any
try:
    from temporalio import activity, workflow
    from temporalio.common import RetryPolicy as TemporalRetryPolicy
except ImportError:
    def activity_defn(f): return f
    def workflow_defn(f): return f
    class workflow:
        defn = activity_defn
        run = activity_defn
    class activity:
        defn = activity_defn


@activity.defn
async def identify_customer_activity(query: str) -> dict[str, Any]:
    from packages.tools.registry import default_registry
    res = await default_registry.execute("search_customer", {"query": query})
    return res.result


@activity.defn
async def retrieve_invoice_activity(invoice_id: str) -> dict[str, Any]:
    from packages.tools.registry import default_registry
    res = await default_registry.execute("get_invoice", {"invoice_id": invoice_id})
    return res.result


@activity.defn
async def retrieve_transactions_activity(txn_ids: list[str]) -> list[dict[str, Any]]:
    from packages.tools.registry import default_registry
    results = []
    for tid in txn_ids:
        call = await default_registry.execute("get_payment", {"transaction_id": tid})
        results.append(call.result)
    return results


@activity.defn
async def execute_refund_activity(transaction_id: str, amount: float, idempotency_key: str) -> dict[str, Any]:
    from packages.tools.registry import default_registry
    res = await default_registry.execute(
        "issue_refund",
        {"transaction_id": transaction_id, "amount": amount, "idempotency_key": idempotency_key},
    )
    return res.result


@workflow.defn
class TemporalCustomerRefundWorkflow:
    """Temporal durable workflow definition ensuring process-restart survivability."""

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        retry_policy = TemporalRetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_attempts=3,
        )
        customer = await workflow.execute_activity(
            identify_customer_activity,
            input_data.get("company_name", "Acme"),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        invoice = await workflow.execute_activity(
            retrieve_invoice_activity,
            input_data.get("invoice_id", "inv_9281"),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        txns = await workflow.execute_activity(
            retrieve_transactions_activity,
            ["txn_5521", "txn_5522"],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        return {
            "customer": customer,
            "invoice": invoice,
            "transactions": txns,
            "status": "AWAITING_APPROVAL",
        }
