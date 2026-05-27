"""Permission middleware - gates all tool calls through permission checker."""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware.types import AgentMiddleware

from ..permissions.checker import PermissionChecker
from ..permissions.settings import PermissionSettings


class PermissionMiddleware(AgentMiddleware):
    """Intercepts tool calls and checks permissions before execution.

    This middleware should be placed first in the pipeline to ensure
    all tool calls are gated by the permission system.
    """

    def __init__(self, settings: PermissionSettings):
        self.checker = PermissionChecker(settings)

    def wrap_model_call(self, request: dict[str, Any], handler) -> dict[str, Any]:
        """Check permissions for each tool call before execution."""
        tool_calls = request.get("tool_calls", [])

        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            arguments = tool_call.get("arguments", {})

            # Evaluate permission
            decision = self.checker.evaluate(
                tool_name=tool_name,
                is_read_only=arguments.get("is_read_only", False),
                file_path=arguments.get("file_path") or arguments.get("path"),
                command=arguments.get("command"),
            )

            if not decision.allowed:
                # Replace tool result with permission denial
                tool_call["result"] = f"Permission denied: {decision.reason}"
                tool_call["skip_execution"] = True
            elif decision.requires_confirmation:
                # Mark for user confirmation (handled by UI layer)
                tool_call["requires_confirmation"] = True
                tool_call["confirmation_reason"] = decision.reason

        return handler(request)
