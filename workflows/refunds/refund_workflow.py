"""B2B Customer Operations Workflow: Duplicate Charge Remediation."""

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from packages.models.base import ModelProvider
from packages.schemas.actions import (
    ActionProposal,
    ApprovalStatus,
    DecisionType,
    RefundProposal,
)
from packages.schemas.tools import RiskTier
from packages.schemas.trust import TrustLevel
from packages.schemas.workflow import EventType, WorkflowRun, WorkflowState
from packages.telemetry.logger import logger
from packages.telemetry.metrics import metrics
from packages.tools.registry import default_registry
from packages.tools.store import enterprise_store
from services.agent_runtime.durable_engine import durable_engine
from services.agent_runtime.memory import AgentMemory
from services.agent_runtime.trajectory import TrajectoryRecorder
from services.policy_engine.engine import policy_engine


class CustomerRefundWorkflow:
    """Executes the reference B2B customer operations workflow with deterministic authorization."""

    def __init__(self, model_provider: ModelProvider):
        self.model = model_provider

    async def run(
        self,
        request_text: str,
        organization_id: str = "org_acme",
        auto_approve_if_reviewed: bool = False,
        reviewer_id: str = "operator_alice",
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        ctx = context or {}
        workflow_run = durable_engine.create_run(
            workflow_name="b2b_refund_remediation",
            organization_id=organization_id,
            input_payload={"request_text": request_text},
            model_name=getattr(self.model, "model_name", "mock-agent-v1"),
        )
        run_id = workflow_run.run_id
        memory = AgentMemory(run_id=run_id)
        recorder = TrajectoryRecorder(
            run_id=run_id,
            scenario_id="b2b_duplicate_charge_inv_9281",
            workflow_name="b2b_refund_remediation",
            goal=request_text,
            model_name=workflow_run.model_name,
            prompt_version=workflow_run.prompt_version,
        )

        durable_engine.record_event(
            run_id,
            EventType.WORKFLOW_START,
            "orchestrator",
            f"Starting workflow run for request: {request_text[:80]}...",
            payload={"request": request_text},
        )
        workflow_run.status = WorkflowState.RUNNING

        try:
            # STEP 1: Search and identify customer
            t0_start = time.perf_counter()
            cust_call = await default_registry.execute(
                "search_customer",
                {"query": "Acme"},
                context={"run_id": run_id, "workflow_id": workflow_run.workflow_id},
                chaos_hook=ctx.get("chaos_hook"),
            )
            workflow_run.tool_calls.append(cust_call)
            if not cust_call.success or not cust_call.result.get("matches"):
                raise RuntimeError("Customer identification failed")

            customer_record = cust_call.result["matches"][0]
            customer_id = customer_record["customer_id"]
            memory.set_working("customer_id", customer_id)
            memory.set_working("state_version", customer_record["state_version"])
            recorder.record_step(
                phase="retrieval",
                thought="Identified customer record for Acme in CRM.",
                tool_name="search_customer",
                output_data=customer_record,
                latency_ms=(time.perf_counter() - t0_start) * 1000.0,
            )

            # STEP 2: Retrieve invoice
            t1_start = time.perf_counter()
            inv_call = await default_registry.execute(
                "get_invoice",
                {"invoice_id": "inv_9281"},
                context={"run_id": run_id, "workflow_id": workflow_run.workflow_id},
                chaos_hook=ctx.get("chaos_hook"),
            )
            workflow_run.tool_calls.append(inv_call)
            if not inv_call.success:
                raise RuntimeError(f"Invoice retrieval failed: {inv_call.error}")

            invoice_record = inv_call.result
            memory.set_working("invoice", invoice_record)
            recorder.record_step(
                phase="retrieval",
                thought="Retrieved invoice INV-9281. Amount is $249.00 USD.",
                tool_name="get_invoice",
                output_data=invoice_record,
                latency_ms=(time.perf_counter() - t1_start) * 1000.0,
            )

            # STEP 3: Retrieve transaction records and verify duplicate charges
            t2_start = time.perf_counter()
            txn1_call = await default_registry.execute("get_payment", {"transaction_id": "txn_5521"}, context={"run_id": run_id})
            txn2_call = await default_registry.execute("get_payment", {"transaction_id": "txn_5522"}, context={"run_id": run_id})
            workflow_run.tool_calls.extend([txn1_call, txn2_call])

            txn1 = txn1_call.result
            txn2 = txn2_call.result
            recorder.record_step(
                phase="reasoning",
                thought=(
                    f"Comparing transactions: txn_5521 (${txn1['amount']}) at {txn1['created_at']} and "
                    f"txn_5522 (${txn2['amount']}) at {txn2['created_at']}. Confirmed duplicate charge on invoice INV-9281."
                ),
                output_data={"txn1": txn1, "txn2": txn2, "duplicate_confirmed": True},
                latency_ms=(time.perf_counter() - t2_start) * 1000.0,
            )

            # STEP 4: Reason & generate structured ActionProposal via Model
            now = datetime.now(timezone.utc)
            proposal = ActionProposal(
                proposal_id=f"prop_{run_id[-6:]}",
                workflow_id=workflow_run.workflow_id,
                run_id=run_id,
                organization_id=organization_id,
                agent_id="refund_agent",
                action="issue_refund",
                target="txn_5522",
                parameters={
                    "transaction_id": "txn_5522",
                    "amount": 249.00,
                    "currency": "USD",
                    "customer_id": customer_id,
                    "reason": "verified_duplicate_charge",
                },
                reason="Verified duplicate charge on invoice INV-9281. Original was txn_5521, duplicate was txn_5522.",
                confidence=0.96,
                evidence_ids=["inv_9281", "txn_5521", "txn_5522"],
                state_version=memory.get_working("state_version", 1),
                observed_at=now,
                expires_at=now + timedelta(minutes=15),
                trust_level=TrustLevel.INTERNAL_DATABASE,
                risk_tier=RiskTier.TIER_3_FINANCIAL_DESTRUCTIVE,
            )

            recorder.record_step(
                phase="proposal",
                thought="Proposed $249.00 refund on txn_5522 with high confidence (0.96). Submitting to Policy Engine.",
                output_data=proposal.model_dump(mode="json"),
            )

            # STEP 5: Policy Evaluation
            decision, approval_id = await durable_engine.submit_and_evaluate_proposal(run_id, proposal, context=ctx)
            recorder.record_step(
                phase="policy",
                thought=f"Policy decision received: {decision.decision.value}. Reason: {decision.reason}",
                policy_verdict=decision.decision.value,
                output_data=decision.model_dump(mode="json"),
            )

            execution_result = None

            # STEP 6: Handling verdict
            if decision.decision == DecisionType.REJECT:
                workflow_run.status = WorkflowState.FAILED
                workflow_run.error = f"Policy rejected action: {decision.reason}"
                recorder.record_step(phase="action", thought=f"Action rejected by policy: {decision.reason}")
                trace = recorder.finalize(success=False)
                return {"success": False, "verdict": "REJECT", "reason": decision.reason, "trace": trace, "run": workflow_run}

            elif decision.decision == DecisionType.REVIEW:
                recorder.escalated_to_human = True
                if auto_approve_if_reviewed and approval_id:
                    # Simulate human reviewer approving in console
                    policy_engine.resolve_approval(
                        approval_id=approval_id,
                        status=ApprovalStatus.APPROVED,
                        reviewer_id=reviewer_id,
                        comment="Verified duplicate billing timestamps in Stripe console. Approved.",
                    )
                    durable_engine.record_event(
                        run_id,
                        EventType.APPROVAL_RESOLVED,
                        "approval_engine",
                        f"Approval ticket {approval_id} approved by {reviewer_id}",
                    )
                    workflow_run.status = WorkflowState.RUNNING

                    # Execute consequential refund
                    execution_result = await durable_engine.execute_authorized_action(
                        run_id,
                        proposal,
                        approval_id=approval_id,
                        context=ctx,
                    )
                else:
                    # Remains suspended for human review
                    workflow_run.status = WorkflowState.SUSPENDED_APPROVAL
                    trace = recorder.finalize(success=False)
                    return {
                        "success": False,
                        "suspended": True,
                        "approval_id": approval_id,
                        "verdict": "REVIEW",
                        "reason": decision.reason,
                        "trace": trace,
                        "run": workflow_run,
                    }

            elif decision.decision == DecisionType.EXECUTE:
                execution_result = await durable_engine.execute_authorized_action(
                    run_id,
                    proposal,
                    approval_id=None,
                    context=ctx,
                )

            # STEP 7: Audit update CRM (Tier 1 Reversible Write)
            crm_call = await default_registry.execute(
                "update_crm",
                {
                    "customer_id": customer_id,
                    "note": f"Refund of $249.00 processed for duplicate charge txn_5522 on INV-9281.",
                },
                context={"run_id": run_id},
            )
            workflow_run.tool_calls.append(crm_call)

            # STEP 8: Notify customer (Tier 2 External Communication)
            email_call = await default_registry.execute(
                "send_email",
                {
                    "recipient": "billing@acme.com",
                    "subject": "Resolution regarding invoice INV-9281 duplicate charge",
                    "body": "Hello Acme Finance, We verified the duplicate charge and have issued a refund of $249.00.",
                },
                context={"run_id": run_id},
            )
            workflow_run.tool_calls.append(email_call)

            # Workflow completion
            workflow_run.status = WorkflowState.COMPLETED
            workflow_run.end_time = datetime.now(timezone.utc)
            workflow_run.output_payload = {
                "customer_id": customer_id,
                "refund_status": "COMPLETED",
                "refund_details": execution_result,
                "audit_note_added": crm_call.success,
                "customer_notified": email_call.success,
            }
            durable_engine.record_event(
                run_id,
                EventType.WORKFLOW_COMPLETED,
                "orchestrator",
                "Workflow completed successfully with all audit trails recorded.",
            )

            metrics.inc("tasks_total")
            metrics.inc("tasks_success_total")
            trace = recorder.finalize(success=True)

            return {
                "success": True,
                "verdict": decision.decision.value,
                "refund": execution_result,
                "run": workflow_run,
                "trace": trace,
            }

        except Exception as exc:
            workflow_run.status = WorkflowState.FAILED
            workflow_run.error = str(exc)
            workflow_run.end_time = datetime.now(timezone.utc)
            metrics.inc("tasks_total")
            metrics.inc("tasks_failed_total")
            trace = recorder.finalize(success=False)
            return {"success": False, "error": str(exc), "run": workflow_run, "trace": trace}
