"""OpenTelemetry Tracing and Span Management for DeployOS."""

import time
from contextlib import contextmanager
from typing import Any, Generator, Optional
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from packages.telemetry.logger import logger

tracer = trace.get_tracer("deployos", "0.1.0")


class SpanRecorder:
    def __init__(self, name: str, attributes: Optional[dict[str, Any]] = None):
        self.name = name
        self.attributes = attributes or {}
        self.start_time: float = 0.0
        self.duration_ms: float = 0.0
        self.status = "success"
        self.error: Optional[str] = None

    def start(self) -> "SpanRecorder":
        self.start_time = time.perf_counter()
        return self

    def finish(self, error: Optional[Exception] = None) -> float:
        self.duration_ms = (time.perf_counter() - self.start_time) * 1000.0
        if error:
            self.status = "error"
            self.error = str(error)
        return self.duration_ms


@contextmanager
def trace_span(
    name: str,
    workflow_id: Optional[str] = None,
    run_id: Optional[str] = None,
    attributes: Optional[dict[str, Any]] = None,
) -> Generator[SpanRecorder, None, None]:
    """Context manager for tracing execution with OpenTelemetry and logging."""
    attrs = attributes or {}
    if workflow_id:
        attrs["workflow.id"] = workflow_id
    if run_id:
        attrs["run.id"] = run_id

    recorder = SpanRecorder(name, attrs).start()

    with tracer.start_as_current_span(name, attributes=attrs) as span:
        try:
            yield recorder
            recorder.finish()
            span.set_status(Status(StatusCode.OK))
            span.set_attribute("duration_ms", recorder.duration_ms)
        except Exception as exc:
            recorder.finish(error=exc)
            span.set_status(Status(StatusCode.ERROR, description=str(exc)))
            span.record_exception(exc)
            logger.error(
                f"Span {name} failed: {exc}",
                workflow_id=workflow_id,
                run_id=run_id,
                latency_ms=recorder.duration_ms,
                status="error",
                error=str(exc),
            )
            raise
        else:
            logger.info(
                f"Completed span: {name}",
                workflow_id=workflow_id,
                run_id=run_id,
                latency_ms=round(recorder.duration_ms, 2),
                status="success",
            )
