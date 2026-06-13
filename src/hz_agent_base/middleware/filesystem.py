"""Filesystem middleware — 文件操作审计和变更追踪。

使用方式：
    from hz_agent_base.middleware.filesystem import FileAuditMiddleware

    agent = create_agent(filesystem=True)
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Awaitable

from langchain.agents.middleware.types import AgentMiddleware

from ..audit import AuditLog, FileOperation, FILE_TOOLS, classify_operation

logger = logging.getLogger(__name__)


class FileAuditMiddleware(AgentMiddleware):
    """文件操作审计和变更追踪中间件。

    功能：
    - audit=True：记录所有文件操作（谁、什么时候、操作了什么文件）
    - track_changes=True：记录变更内容（写入/编辑的 diff）
    - workspace：限制文件操作范围（空则不限制）

    通过 create_agent(filesystem=...) 启用。
    """

    def __init__(
        self,
        *,
        audit: bool = True,
        track_changes: bool = True,
        workspace: str = "",
        log_path: str = "",
    ):
        self.audit = audit
        self.track_changes = track_changes
        self.workspace = workspace
        self.audit_log = AuditLog(log_path=log_path) if audit else None

    def wrap_model_call(self, request, handler) -> Any:
        """在模型调用前后记录文件操作。"""
        tools = request.tools or []
        thread_id = getattr(request.state, "thread_id", "") if hasattr(request, "state") else ""

        # 识别文件操作工具
        file_tool_names = set()
        for tool in tools:
            name = getattr(tool, "name", None) or (
                tool.get("name", "") if isinstance(tool, dict) else str(tool)
            )
            if name in FILE_TOOLS:
                file_tool_names.add(name)

        # 如果没有文件操作工具，直接透传
        if not file_tool_names and not self.track_changes:
            return handler(request)

    async def awrap_model_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """在模型调用前后记录文件操作（异步版本）。"""
        tools = request.tools or []
        thread_id = getattr(request.state, "thread_id", "") if hasattr(request, "state") else ""

        # 识别文件操作工具
        file_tool_names = set()
        for tool in tools:
            name = getattr(tool, "name", None) or (
                tool.get("name", "") if isinstance(tool, dict) else str(tool)
            )
            if name in FILE_TOOLS:
                file_tool_names.add(name)

        # 如果没有文件操作工具，直接透传
        if not file_tool_names and not self.track_changes:
            return await handler(request)

        # 调用模型
        response = await handler(request)

        # 从响应中提取工具执行结果并记录
        if self.audit:
            self._extract_and_log(response, thread_id)

        return response

    def _is_in_workspace(self, file_path: str) -> bool:
        """检查文件路径是否在允许的工作目录内。"""
        if not self.workspace:
            return True
        try:
            resolved = Path(file_path).resolve()
            workspace_resolved = Path(self.workspace).resolve()
            return str(resolved).startswith(str(workspace_resolved))
        except Exception:
            return False

    def _extract_and_log(self, response: Any, thread_id: str) -> None:
        """从 agent 响应中提取文件操作并记录到审计日志。"""
        try:
            messages = response.get("messages", []) if isinstance(response, dict) else []
        except Exception:
            return

        for msg in messages:
            tool_calls = getattr(msg, "tool_calls", None) or []
            for tc in tool_calls:
                tool_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                if tool_name not in FILE_TOOLS:
                    continue

                args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                file_path = args.get("file_path", "") or args.get("path", "")

                # workspace 限制检查
                if file_path and not self._is_in_workspace(file_path):
                    op = FileOperation(
                        timestamp=datetime.now().isoformat(),
                        tool_name=tool_name,
                        file_path=file_path,
                        operation=classify_operation(tool_name),
                        thread_id=thread_id,
                        success=False,
                    )
                    self.audit_log.add(op)
                    continue

                # 记录操作
                op = FileOperation(
                    timestamp=datetime.now().isoformat(),
                    tool_name=tool_name,
                    file_path=file_path,
                    operation=classify_operation(tool_name),
                    thread_id=thread_id,
                )
                self.audit_log.add(op)
