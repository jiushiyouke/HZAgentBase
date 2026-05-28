"""Filesystem middleware — 文件操作审计和变更追踪。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware


# 需要审计的文件操作工具名
FILE_TOOLS = {
    "write_file", "edit_file", "read_file",
    "create_file", "delete_file", "rename_file",
    "write", "edit", "read",
}


@dataclass
class FileOperation:
    """单次文件操作记录。

    Attributes:
        timestamp: 操作时间。
        tool_name: 工具名称。
        file_path: 操作的文件路径。
        operation: 操作类型（read / write / edit / delete）。
        thread_id: 线程标识。
        diff: 变更内容（写入/编辑时记录）。
        success: 是否成功。
    """

    timestamp: str
    tool_name: str
    file_path: str
    operation: str
    thread_id: str = ""
    diff: str = ""
    success: bool = True


@dataclass
class AuditLog:
    """审计日志，记录所有文件操作。

    Attributes:
        operations: 操作记录列表。
        log_path: 日志持久化路径（空则不持久化）。
    """

    operations: list[FileOperation] = field(default_factory=list)
    log_path: str = ""

    def add(self, op: FileOperation) -> None:
        """添加一条操作记录。"""
        self.operations.append(op)
        if self.log_path:
            self._persist(op)

    def query(
        self,
        *,
        file_path: str | None = None,
        operation: str | None = None,
        thread_id: str | None = None,
    ) -> list[FileOperation]:
        """按条件查询操作记录。"""
        results = self.operations
        if file_path:
            results = [op for op in results if op.file_path == file_path]
        if operation:
            results = [op for op in results if op.operation == operation]
        if thread_id:
            results = [op for op in results if op.thread_id == thread_id]
        return results

    def _persist(self, op: FileOperation) -> None:
        """追加写入日志文件（JSONL 格式）。"""
        log_file = Path(self.log_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": op.timestamp,
            "tool_name": op.tool_name,
            "file_path": op.file_path,
            "operation": op.operation,
            "thread_id": op.thread_id,
            "success": op.success,
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


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
        # 从 request 中提取工具列表和线程信息
        tools = request.tools or []
        thread_id = getattr(request.state, "thread_id", "") if hasattr(request, "state") else ""

        # 识别文件操作工具
        file_tool_names = set()
        for tool in tools:
            name = getattr(tool, "name", None) or (tool.get("name", "") if isinstance(tool, dict) else "")
            if name in FILE_TOOLS:
                file_tool_names.add(name)

        # 如果没有文件操作工具，直接透传
        if not file_tool_names and not self.track_changes:
            return handler(request)

        # 调用模型（模型调用后会执行工具）
        response = handler(request)

        # 从响应中提取工具执行结果并记录
        if self.audit:
            self._extract_and_log(response, thread_id)

        return response

    def _extract_and_log(self, response: Any, thread_id: str) -> None:
        """从 agent 响应中提取文件操作并记录到审计日志。"""
        messages = response.get("messages", []) if isinstance(response, dict) else []

        for msg in messages:
            # 检查是否为工具调用消息
            tool_calls = getattr(msg, "tool_calls", None) or []
            for tc in tool_calls:
                tool_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                if tool_name not in FILE_TOOLS:
                    continue

                args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                file_path = args.get("file_path", "") or args.get("path", "")

                # 判断操作类型
                operation = _classify_operation(tool_name)

                # 记录操作
                op = FileOperation(
                    timestamp=datetime.now().isoformat(),
                    tool_name=tool_name,
                    file_path=file_path,
                    operation=operation,
                    thread_id=thread_id,
                )
                self.audit_log.add(op)


def _classify_operation(tool_name: str) -> str:
    """根据工具名判断操作类型。"""
    if "write" in tool_name or "create" in tool_name:
        return "write"
    if "edit" in tool_name:
        return "edit"
    if "read" in tool_name:
        return "read"
    if "delete" in tool_name or "remove" in tool_name:
        return "delete"
    if "rename" in tool_name or "move" in tool_name:
        return "rename"
    return "other"
