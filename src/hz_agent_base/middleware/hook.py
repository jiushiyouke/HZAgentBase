"""Hook middleware - executes lifecycle hooks around tool calls."""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware.types import AgentMiddleware

from ..hooks.registry import HookRegistry
from ..hooks.executor import HookExecutor
from ..hooks.events import HookEvent


class HookMiddleware(AgentMiddleware):
    """Executes registered hooks at lifecycle events.

    Events:
        - PRE_TOOL_USE: Before each tool call
        - POST_TOOL_USE: After each tool call
        - USER_PROMPT_SUBMIT: When user sends a message
    """

    def __init__(self, registry: HookRegistry):
        self.executor = HookExecutor(registry)

    def wrap_model_call(self, request: dict[str, Any], handler) -> dict[str, Any]:
        """Execute hooks around tool calls."""
        tool_calls = request.get("tool_calls", [])

        # PRE_TOOL_USE hooks
        for tool_call in tool_calls:
            result = self.executor.execute(HookEvent.PRE_TOOL_USE, {
                "tool": tool_call.get("name", ""),
                "arguments": tool_call.get("arguments", {}),
            })
            if result.blocked:
                tool_call["result"] = f"Blocked by hook: {result.reason}"
                tool_call["skip_execution"] = True

        # Execute the actual tool calls
        response = handler(request)

        # POST_TOOL_USE hooks
        for tool_call in tool_calls:
            self.executor.execute(HookEvent.POST_TOOL_USE, {
                "tool": tool_call.get("name", ""),
                "result": tool_call.get("result"),
            })

        return response
