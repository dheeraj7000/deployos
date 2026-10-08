"""Tool Registry and Execution Dispatcher."""

from typing import Any, Optional
from packages.schemas.tools import ToolDefinition, ToolCall
from packages.tools.base import BaseTool
from packages.tools.customer_ops import (
    GetCustomerTool,
    SearchCustomerTool,
    GetInvoiceTool,
    GetPaymentTransactionTool,
    SearchEmailTool,
    ReadEmailTool,
    SearchKnowledgeBaseTool,
    AddCrmNoteTool,
    CreateSupportTicketTool,
    SendCustomerEmailTool,
    SendSlackMessageTool,
    IssueRefundTool,
)


class ToolRegistry:
    """Central registry of all internal and MCP-compatible tools."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        defaults = [
            GetCustomerTool(),
            SearchCustomerTool(),
            GetInvoiceTool(),
            GetPaymentTransactionTool(),
            SearchEmailTool(),
            ReadEmailTool(),
            SearchKnowledgeBaseTool(),
            AddCrmNoteTool(),
            CreateSupportTicketTool(),
            SendCustomerEmailTool(),
            SendSlackMessageTool(),
            IssueRefundTool(),
        ]
        for t in defaults:
            self.register(t)

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_definitions(self) -> list[ToolDefinition]:
        return [tool.get_definition() for tool in self._tools.values()]

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
        chaos_hook: Optional[Any] = None,
    ) -> ToolCall:
        tool = self.get(tool_name)
        if not tool:
            from packages.schemas.tools import RiskTier
            return ToolCall(
                call_id=f"call_{tool_name}_err",
                tool_name=tool_name,
                risk_tier=RiskTier.TIER_0_READ_ONLY,
                arguments=arguments,
                error=f"Tool '{tool_name}' not registered in registry",
                success=False,
            )
        return await tool.run(arguments, context=context, chaos_hook=chaos_hook)


default_registry = ToolRegistry()
