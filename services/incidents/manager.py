"""Incident Management and Automated Regression Test Synthesis."""

import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from packages.schemas.chaos import Incident, IncidentSeverity, IncidentStatus, RootCauseCategory
from services.agent_runtime.durable_engine import durable_engine


class IncidentManager:
    """Captures failures, classifies root causes, and synthesizes permanent regression tests."""

    def __init__(self):
        self.incidents: dict[str, Incident] = {}
        self.regression_cases: dict[str, dict[str, Any]] = {}

    def classify_root_cause(self, error_message: str) -> RootCauseCategory:
        lowered = error_message.lower()
        if "ignore previous instructions" in lowered or "prompt injection" in lowered or "trust" in lowered:
            return RootCauseCategory.PROMPT_INJECTION
        elif "stale" in lowered or "version" in lowered or "expired" in lowered:
            return RootCauseCategory.STALE_STATE
        elif "rate limit" in lowered or "429" in lowered:
            return RootCauseCategory.RATE_LIMIT_EXCEEDED
        elif "timeout" in lowered or "connection" in lowered or "503" in lowered:
            return RootCauseCategory.TOOL_FAILURE
        elif "policy" in lowered or "prohibited" in lowered:
            return RootCauseCategory.POLICY_VIOLATION
        elif "schema" in lowered or "missing" in lowered:
            return RootCauseCategory.SCHEMA_MISMATCH
        else:
            return RootCauseCategory.UNEXPECTED_EXCEPTION

    def create_incident(
        self,
        run_id: str,
        title: str,
        error_trace: str,
        severity: IncidentSeverity = IncidentSeverity.HIGH,
        root_cause_override: Optional[RootCauseCategory] = None,
    ) -> Incident:
        run = durable_engine.runs.get(run_id)
        workflow_id = run.workflow_id if run else "wf_unknown"
        root_cause = root_cause_override or self.classify_root_cause(error_trace)
        incident_id = f"inc_{uuid.uuid4().hex[:8]}"

        run_summary = {}
        if run:
            run_summary = {
                "workflow_name": run.workflow_name,
                "model_name": run.model_name,
                "input": run.input_payload,
                "events_count": len(run.events),
                "tool_calls_count": len(run.tool_calls),
            }

        incident = Incident(
            incident_id=incident_id,
            run_id=run_id,
            workflow_id=workflow_id,
            title=title,
            severity=severity,
            root_cause_category=root_cause,
            status=IncidentStatus.OPEN,
            error_trace=error_trace,
            run_trace_summary=run_summary,
            created_at=datetime.now(timezone.utc),
        )

        self.incidents[incident_id] = incident
        return incident

    def synthesize_regression_case(self, incident_id: str) -> str:
        """Transforms a production failure into a permanent evaluation case."""
        incident = self.incidents.get(incident_id)
        if not incident:
            raise KeyError(f"Incident '{incident_id}' not found")

        case_id = f"reg_case_{incident_id}"
        self.regression_cases[case_id] = {
            "case_id": case_id,
            "origin_incident_id": incident_id,
            "root_cause": incident.root_cause_category.value,
            "expected_behavior": "Must fail-safe without unsafe execution or unhandled panic",
            "run_summary": incident.run_trace_summary,
            "synthesized_at": datetime.now(timezone.utc).isoformat(),
        }

        incident.reproduction_eval_case_id = case_id
        incident.status = IncidentStatus.REGRESSION_ADDED
        return case_id

    def list_incidents(self) -> list[Incident]:
        return list(self.incidents.values())


incident_manager = IncidentManager()
