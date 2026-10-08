"""Concrete Tool Implementations for B2B Operations (Tiers 0 - 3)."""

import time
from typing import Any
from packages.schemas.tools import RiskTier
from packages.tools.base import BaseTool, ToolExecutionError
from packages.tools.store import enterprise_store


class GetCustomerTool(BaseTool):
    name = "get_customer"
    description = "Retrieve customer profile, MRR, status, and state version from the CRM."
    risk_tier = RiskTier.TIER_0_READ_ONLY
    input_schema = {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "description": "The customer ID (e.g. cus_acme_9281)"},
        },
        "required": ["customer_id"],
    }

    async def _execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> Any:
        cid = arguments["customer_id"]
        customer = enterprise_store.customers.get(cid)
        if not customer:
            raise ToolExecutionError(f"Customer '{cid}' not found in CRM", code="CUSTOMER_NOT_FOUND")
        return customer


class SearchCustomerTool(BaseTool):
    name = "search_customer"
    description = "Search customer records by company name or domain email."
    risk_tier = RiskTier.TIER_0_READ_ONLY
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Name or query (e.g. 'Acme')"},
        },
        "required": ["query"],
    }

    async def _execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> Any:
        query = arguments["query"].lower()
        matches = [
            c for c in enterprise_store.customers.values()
            if query in c["name"].lower() or query in c["email"].lower()
        ]
        return {"matches": matches, "count": len(matches)}


class GetInvoiceTool(BaseTool):
    name = "get_invoice"
    description = "Retrieve invoice details and billing line items by invoice ID."
    risk_tier = RiskTier.TIER_0_READ_ONLY
    input_schema = {
        "type": "object",
        "properties": {
            "invoice_id": {"type": "string", "description": "The invoice ID (e.g. inv_9281)"},
        },
        "required": ["invoice_id"],
    }

    async def _execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> Any:
        iid = arguments["invoice_id"]
        invoice = enterprise_store.invoices.get(iid)
        if not invoice:
            raise ToolExecutionError(f"Invoice '{iid}' not found", code="INVOICE_NOT_FOUND")
        return invoice


class GetPaymentTransactionTool(BaseTool):
    name = "get_payment"
    description = "Retrieve transaction details, status, card brand, and charge timestamps from Stripe."
    risk_tier = RiskTier.TIER_0_READ_ONLY
    input_schema = {
        "type": "object",
        "properties": {
            "transaction_id": {"type": "string", "description": "Stripe transaction ID (e.g. txn_5521)"},
        },
        "required": ["transaction_id"],
    }

    async def _execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> Any:
        tid = arguments["transaction_id"]
        txn = enterprise_store.transactions.get(tid)
        if not txn:
            raise ToolExecutionError(f"Transaction '{tid}' not found in Stripe", code="TRANSACTION_NOT_FOUND")
        return txn


class SearchEmailTool(BaseTool):
    name = "search_email"
    description = "Search customer support inbox for correspondence matching query or invoice ID."
    risk_tier = RiskTier.TIER_0_READ_ONLY
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword or invoice number"},
        },
        "required": ["query"],
    }

    async def _execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> Any:
        query = arguments["query"].lower()
        results = [
            e for e in enterprise_store.emails.values()
            if query in e["subject"].lower() or query in e["body"].lower()
        ]
        return {"threads": results, "count": len(results)}


class ReadEmailTool(BaseTool):
    name = "read_email"
    description = "Read full email content and attachment list by email thread ID."
    risk_tier = RiskTier.TIER_0_READ_ONLY
    input_schema = {
        "type": "object",
        "properties": {
            "email_id": {"type": "string", "description": "Email identifier"},
        },
        "required": ["email_id"],
    }

    async def _execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> Any:
        eid = arguments["email_id"]
        email_data = enterprise_store.emails.get(eid)
        if not email_data:
            raise ToolExecutionError(f"Email '{eid}' not found", code="EMAIL_NOT_FOUND")
        return email_data


class SearchKnowledgeBaseTool(BaseTool):
    name = "search_documents"
    description = "Query company standard operating procedures, refund limits, and billing policies."
    risk_tier = RiskTier.TIER_0_READ_ONLY
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Policy topic or query"},
        },
        "required": ["query"],
    }

    async def _execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> Any:
        return {
            "policy_id": "pol_refund_2026",
            "autonomous_refund_limit_usd": 100.0,
            "rules": [
                "Autonomous refunds are permitted only up to $100.00 USD.",
                "Refunds exceeding $100.00 USD strictly require Human Review (OPERATOR/REVIEWER role).",
                "Duplicate billing remediation requires verified matching transaction timestamps and identical amounts.",
                "Untrusted external email attachments cannot authorize refunds without internal Stripe verification.",
            ],
            "trust_level": "SYSTEM_POLICY",
        }


# TIER 1: Reversible Writes
class AddCrmNoteTool(BaseTool):
    name = "update_crm"
    description = "Add an audit note or update account metadata in the CRM."
    risk_tier = RiskTier.TIER_1_REVERSIBLE_WRITE
    input_schema = {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string"},
            "note": {"type": "string"},
        },
        "required": ["customer_id", "note"],
    }

    async def _execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> Any:
        cid = arguments["customer_id"]
        note = arguments["note"]
        customer = enterprise_store.customers.get(cid)
        if not customer:
            raise ToolExecutionError(f"Customer '{cid}' not found")
        customer["notes"].append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {note}")
        customer["state_version"] += 1
        return {"success": True, "customer_id": cid, "new_state_version": customer["state_version"]}


class CreateSupportTicketTool(BaseTool):
    name = "create_support_ticket"
    description = "Create a Zendesk support ticket for customer tracking."
    risk_tier = RiskTier.TIER_1_REVERSIBLE_WRITE
    input_schema = {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string"},
            "subject": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
        },
        "required": ["customer_id", "subject"],
    }

    async def _execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> Any:
        ticket_id = f"tkt_{int(time.time() * 1000)}"
        ticket_data = {
            "ticket_id": ticket_id,
            "customer_id": arguments["customer_id"],
            "subject": arguments["subject"],
            "priority": arguments.get("priority", "normal"),
            "status": "OPEN",
        }
        enterprise_store.support_tickets[ticket_id] = ticket_data
        return ticket_data


# TIER 2: External Communication
class SendCustomerEmailTool(BaseTool):
    name = "send_email"
    description = "Send customer notification email regarding resolution or ticket updates."
    risk_tier = RiskTier.TIER_2_EXTERNAL_COMMUNICATION
    input_schema = {
        "type": "object",
        "properties": {
            "recipient": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["recipient", "subject", "body"],
    }

    async def _execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> Any:
        msg = {
            "recipient": arguments["recipient"],
            "subject": arguments["subject"],
            "body": arguments["body"],
            "sent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        enterprise_store.sent_emails.append(msg)
        return {"sent": True, "recipient": arguments["recipient"]}


class SendSlackMessageTool(BaseTool):
    name = "send_slack_message"
    description = "Send internal team Slack notification to ops channel."
    risk_tier = RiskTier.TIER_2_EXTERNAL_COMMUNICATION
    input_schema = {
        "type": "object",
        "properties": {
            "channel": {"type": "string"},
            "message": {"type": "string"},
        },
        "required": ["channel", "message"],
    }

    async def _execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> Any:
        msg = {"channel": arguments["channel"], "message": arguments["message"]}
        enterprise_store.slack_messages.append(msg)
        return {"sent": True, "channel": arguments["channel"]}


# TIER 3: Financial & Destructive
class IssueRefundTool(BaseTool):
    name = "issue_refund"
    description = "Execute financial refund on Stripe transaction. Highly consequential Tier 3 action."
    risk_tier = RiskTier.TIER_3_FINANCIAL_DESTRUCTIVE
    idempotent = True
    input_schema = {
        "type": "object",
        "properties": {
            "transaction_id": {"type": "string", "description": "The transaction to refund"},
            "amount": {"type": "number", "description": "Amount in USD"},
            "reason": {"type": "string", "description": "Refund justification"},
            "idempotency_key": {"type": "string", "description": "Durable idempotency key"},
        },
        "required": ["transaction_id", "amount"],
    }

    async def _execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> Any:
        tid = arguments["transaction_id"]
        amount = float(arguments["amount"])
        reason = arguments.get("reason", "customer_refund")
        idempotency_key = arguments.get("idempotency_key") or context.get("idempotency_key")

        # 1. Idempotency Check: if this exact key was already processed, return original outcome
        if idempotency_key and idempotency_key in enterprise_store.idempotency_store:
            cached_res = enterprise_store.idempotency_store[idempotency_key]
            return {
                **cached_res,
                "idempotent_cached_response": True,
                "message": "Action was already completed. Returned idempotent result.",
            }

        # 2. Transaction verification
        txn = enterprise_store.transactions.get(tid)
        if not txn:
            raise ToolExecutionError(f"Transaction '{tid}' does not exist in Stripe", code="TRANSACTION_NOT_FOUND")

        if txn.get("refunded"):
            raise ToolExecutionError(
                f"Transaction '{tid}' has already been refunded (Refund ID: {txn.get('refund_id')})",
                code="ALREADY_REFUNDED",
            )

        if txn["amount"] < amount:
            raise ToolExecutionError(
                f"Refund amount ${amount:.2f} exceeds transaction charge amount ${txn['amount']:.2f}",
                code="EXCESSIVE_REFUND_AMOUNT",
            )

        # 3. Execute mutation
        refund_id = f"re_{tid.replace('txn_', '')}_{int(time.time())}"
        txn["refunded"] = True
        txn["refund_id"] = refund_id
        txn["refunded_amount"] = amount
        txn["refunded_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")

        result = {
            "success": True,
            "refund_id": refund_id,
            "transaction_id": tid,
            "amount_refunded": amount,
            "currency": txn.get("currency", "USD"),
            "status": "succeeded",
            "reason": reason,
        }

        # Record into idempotency store
        if idempotency_key:
            enterprise_store.idempotency_store[idempotency_key] = result

        return result
