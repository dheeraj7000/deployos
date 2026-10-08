"""Base Tool Abstraction with Risk Tiers, Idempotency, and Chaos Hooks."""

import abc
import time
from typing import Any, Optional
from packages.schemas.tools import RiskTier, ToolDefinition, RetryPolicy, ToolCall
from packages.telemetry.logger import logger
from packages.telemetry.tracer import trace_span


class ToolExecutionError(Exception):
    def __init__(self, message: str, retryable: bool = False, code: str = "TOOL_ERROR"):
        super().__init__(message)
        self.retryable = retryable
        self.code = code


class BaseTool(abc.ABC):
    """Internal tool abstraction enforcing risk classification and durability."""

    name: str
    description: str
    risk_tier: RiskTier
    input_schema: dict[str, Any]
    output_schema: Optional[dict[str, Any]] = None
    idempotent: bool = True
    timeout_seconds: float = 30.0
    retry_policy: RetryPolicy = RetryPolicy()

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            risk_tier=self.risk_tier,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
            idempotent=self.idempotent,
            timeout_seconds=self.timeout_seconds,
            retry_policy=self.retry_policy,
        )

    async def run(
        self,
        arguments: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
        chaos_hook: Optional[Any] = None,
    ) -> ToolCall:
        ctx = context or {}
        workflow_id = ctx.get("workflow_id", "unknown_wf")
        run_id = ctx.get("run_id", "unknown_run")
        call_id = f"call_{self.name}_{int(time.time() * 1000)}"

        # Validate arguments against required fields in input schema
        required_props = self.input_schema.get("required", [])
        for prop in required_props:
            if prop not in arguments:
                err_msg = f"Missing required argument '{prop}' for tool '{self.name}'"
                logger.error(err_msg, workflow_id=workflow_id, run_id=run_id, tool=self.name)
                return ToolCall(
                    call_id=call_id,
                    tool_name=self.name,
                    risk_tier=self.risk_tier,
                    arguments=arguments,
                    error=err_msg,
                    success=False,
                )

        start_time = time.perf_counter()

        with trace_span(f"tool.{self.name}", workflow_id=workflow_id, run_id=run_id) as recorder:
            try:
                # Execute any active chaos injection hooks
                if chaos_hook:
                    await chaos_hook.intercept_tool(self.name, arguments)

                result = await self._execute(arguments, ctx)
                latency_ms = (time.perf_counter() - start_time) * 1000.0

                logger.info(
                    f"Tool {self.name} completed successfully",
                    workflow_id=workflow_id,
                    run_id=run_id,
                    tool=self.name,
                    latency_ms=round(latency_ms, 2),
                    status="success",
                )

                return ToolCall(
                    call_id=call_id,
                    tool_name=self.name,
                    risk_tier=self.risk_tier,
                    arguments=arguments,
                    result=result,
                    latency_ms=latency_ms,
                    success=True,
                )

            except Exception as exc:
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                err_msg = str(exc)
                logger.error(
                    f"Tool {self.name} failed: {err_msg}",
                    workflow_id=workflow_id,
                    run_id=run_id,
                    tool=self.name,
                    latency_ms=round(latency_ms, 2),
                    status="error",
                    error=err_msg,
                )

                return ToolCall(
                    call_id=call_id,
                    tool_name=self.name,
                    risk_tier=self.risk_tier,
                    arguments=arguments,
                    error=err_msg,
                    latency_ms=latency_ms,
                    success=False,
                )

    @abc.abstractmethod
    async def _execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> Any:
        pass
