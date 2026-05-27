"""Permission middleware - filters tools based on permission settings."""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware.types import AgentMiddleware

from ..permissions.checker import PermissionChecker
from ..permissions.settings import PermissionSettings


class PermissionMiddleware(AgentMiddleware):
    """Filters available tools based on permission settings.

    This middleware should be placed first in the pipeline to ensure
    only allowed tools are presented to the model.
    """

    def __init__(self, settings: PermissionSettings):
        self.checker = PermissionChecker(settings)

    def wrap_model_call(self, request, handler) -> Any:
        """Filter tools based on permissions before model call."""
        from ..permissions.settings import PermissionMode

        # In full_auto mode, allow all tools
        if self.checker.settings.mode == PermissionMode.FULL_AUTO:
            return handler(request)

        # Filter tools based on permission settings
        allowed_tools = []
        for tool in request.tools:
            tool_name = getattr(tool, "name", None) or (
                tool.get("name", "") if isinstance(tool, dict) else str(tool)
            )
            if self.checker.is_tool_allowed(tool_name):
                allowed_tools.append(tool)

        # Create a new request with filtered tools
        filtered_request = request.override(tools=allowed_tools)
        return handler(filtered_request)
