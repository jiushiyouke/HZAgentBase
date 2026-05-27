"""权限中间件 — 在模型调用前过滤可用工具列表。

应放在管道最前面，确保模型只能看到被允许的工具。
FULL_AUTO 模式下跳过过滤。
"""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware.types import AgentMiddleware

from ..permissions.checker import PermissionChecker
from ..permissions.settings import PermissionSettings


class PermissionMiddleware(AgentMiddleware):
    """根据权限设置过滤可用工具的中间件。"""

    def __init__(self, settings: PermissionSettings):
        self.checker = PermissionChecker(settings)

    def wrap_model_call(self, request, handler) -> Any:
        """在模型调用前过滤工具列表。"""
        from ..permissions.settings import PermissionMode

        # FULL_AUTO 模式：不过滤，全部放行
        if self.checker.settings.mode == PermissionMode.FULL_AUTO:
            return handler(request)

        # 按白名单/黑名单过滤工具
        allowed_tools = []
        for tool in request.tools:
            tool_name = getattr(tool, "name", None) or (
                tool.get("name", "") if isinstance(tool, dict) else str(tool)
            )
            if self.checker.is_tool_allowed(tool_name):
                allowed_tools.append(tool)

        # 用过滤后的工具列表创建新请求
        filtered_request = request.override(tools=allowed_tools)
        return handler(filtered_request)
