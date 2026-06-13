"""权限中间件 — 在模型调用前过滤可用工具列表。

应放在管道最前面，确保模型只能看到被允许的工具。
FULL_AUTO 模式下跳过过滤。
"""

from __future__ import annotations

from typing import Any, Callable, Awaitable

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

    async def awrap_model_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """在模型调用前过滤工具列表（异步版本）。"""
        from ..permissions.settings import PermissionMode

        # FULL_AUTO 模式：不过滤，全部放行
        if self.checker.settings.mode == PermissionMode.FULL_AUTO:
            return await handler(request)

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
        return await handler(filtered_request)

    def wrap_tool_call(self, request, handler) -> Any:
        """在工具执行前检查路径规则和命令黑名单。"""
        from ..permissions.settings import PermissionMode
        from langchain_core.messages import ToolMessage

        # FULL_AUTO 模式：全部放行
        if self.checker.settings.mode == PermissionMode.FULL_AUTO:
            return handler(request)

        tool_call = request.tool_call
        tool_name = tool_call.get("name", "") if isinstance(tool_call, dict) else getattr(tool_call, "name", "")
        args = tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, "args", {})

        # 提取文件路径和命令参数
        file_path = args.get("file_path") or args.get("path") or None
        command = args.get("command") or None

        # 使用 evaluate() 检查完整权限规则（路径、命令等）
        decision = self.checker.evaluate(
            tool_name,
            file_path=file_path,
            command=command,
        )

        if not decision.allowed:
            tool_call_id = tool_call.get("id", "") if isinstance(tool_call, dict) else getattr(tool_call, "id", "")
            return ToolMessage(
                content=f"Permission denied: {decision.reason}",
                tool_call_id=tool_call_id,
            )

        return handler(request)

    async def awrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """在工具执行前检查路径规则和命令黑名单（异步版本）。"""
        from ..permissions.settings import PermissionMode
        from langchain_core.messages import ToolMessage

        # FULL_AUTO 模式：全部放行
        if self.checker.settings.mode == PermissionMode.FULL_AUTO:
            return await handler(request)

        tool_call = request.tool_call
        tool_name = tool_call.get("name", "") if isinstance(tool_call, dict) else getattr(tool_call, "name", "")
        args = tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, "args", {})

        # 提取文件路径和命令参数
        file_path = args.get("file_path") or args.get("path") or None
        command = args.get("command") or None

        # 使用 evaluate() 检查完整权限规则（路径、命令等）
        decision = self.checker.evaluate(
            tool_name,
            file_path=file_path,
            command=command,
        )

        if not decision.allowed:
            tool_call_id = tool_call.get("id", "") if isinstance(tool_call, dict) else getattr(tool_call, "id", "")
            return ToolMessage(
                content=f"Permission denied: {decision.reason}",
                tool_call_id=tool_call_id,
            )

        return await handler(request)
