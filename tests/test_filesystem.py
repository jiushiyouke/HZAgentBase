"""测试文件操作审计和变更追踪中间件。"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from langchain_core.messages import HumanMessage, AIMessage

from hz_agent_base.middleware.filesystem import (
    FilesystemMiddleware,
    FileOperation,
    AuditLog,
    FILE_TOOLS,
    _classify_operation,
)


# ============================================================
# 辅助函数
# ============================================================

def make_mock_request(messages=None, tools=None):
    """创建模拟的 ModelRequest。"""
    request = MagicMock()
    request.messages = messages or [HumanMessage(content="hello")]
    request.tools = tools or []
    request.system_prompt = "You are helpful."
    request.state = MagicMock()
    request.state.thread_id = "test-thread"

    def mock_override(**kwargs):
        new_req = MagicMock()
        new_req.messages = request.messages
        new_req.system_prompt = kwargs.get("system_prompt", request.system_prompt)
        return new_req

    request.override = MagicMock(side_effect=mock_override)
    return request


def make_mock_tool(name):
    """创建模拟工具。"""
    tool = MagicMock()
    tool.name = name
    return tool


def make_tool_call_response(tool_name, args):
    """创建包含工具调用的模拟响应。"""
    tool_call = MagicMock()
    tool_call.name = tool_name
    tool_call.args = args

    msg = MagicMock()
    msg.tool_calls = [tool_call]

    return {"messages": [msg]}


# ============================================================
# _classify_operation 测试
# ============================================================

class TestClassifyOperation:
    """测试操作类型分类。"""

    def test_write(self):
        assert _classify_operation("write_file") == "write"
        assert _classify_operation("create_file") == "write"

    def test_edit(self):
        assert _classify_operation("edit_file") == "edit"
        assert _classify_operation("edit") == "edit"

    def test_read(self):
        assert _classify_operation("read_file") == "read"
        assert _classify_operation("read") == "read"

    def test_delete(self):
        assert _classify_operation("delete_file") == "delete"

    def test_rename(self):
        assert _classify_operation("rename_file") == "rename"

    def test_other(self):
        assert _classify_operation("bash") == "other"


# ============================================================
# AuditLog 测试
# ============================================================

class TestAuditLog:
    """测试审计日志。"""

    def test_add_and_query(self):
        """添加记录后应能查询。"""
        log = AuditLog()
        op = FileOperation(
            timestamp="2026-01-01T00:00:00",
            tool_name="write_file",
            file_path="test.txt",
            operation="write",
        )
        log.add(op)

        assert len(log.operations) == 1
        assert log.query(file_path="test.txt") == [op]

    def test_query_by_operation(self):
        """按操作类型查询。"""
        log = AuditLog()
        log.add(FileOperation(timestamp="", tool_name="", file_path="a", operation="read"))
        log.add(FileOperation(timestamp="", tool_name="", file_path="b", operation="write"))
        log.add(FileOperation(timestamp="", tool_name="", file_path="c", operation="read"))

        results = log.query(operation="read")
        assert len(results) == 2

    def test_query_by_thread_id(self):
        """按线程 ID 查询。"""
        log = AuditLog()
        log.add(FileOperation(timestamp="", tool_name="", file_path="a", operation="read", thread_id="t1"))
        log.add(FileOperation(timestamp="", tool_name="", file_path="b", operation="read", thread_id="t2"))

        results = log.query(thread_id="t1")
        assert len(results) == 1
        assert results[0].file_path == "a"

    def test_query_combined_filters(self):
        """组合条件查询。"""
        log = AuditLog()
        log.add(FileOperation(timestamp="", tool_name="", file_path="a", operation="read", thread_id="t1"))
        log.add(FileOperation(timestamp="", tool_name="", file_path="a", operation="write", thread_id="t1"))
        log.add(FileOperation(timestamp="", tool_name="", file_path="b", operation="read", thread_id="t2"))

        results = log.query(file_path="a", thread_id="t1")
        assert len(results) == 2

    def test_persist_creates_jsonl(self, tmp_path):
        """持久化应创建 JSONL 文件。"""
        log_file = tmp_path / "audit.jsonl"
        log = AuditLog(log_path=str(log_file))

        log.add(FileOperation(
            timestamp="2026-01-01T00:00:00",
            tool_name="write_file",
            file_path="test.txt",
            operation="write",
        ))

        assert log_file.exists()
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["file_path"] == "test.txt"

    def test_persist_appends(self, tmp_path):
        """多次写入应追加而非覆盖。"""
        log_file = tmp_path / "audit.jsonl"
        log = AuditLog(log_path=str(log_file))

        for i in range(3):
            log.add(FileOperation(
                timestamp="",
                tool_name="write_file",
                file_path=f"file-{i}.txt",
                operation="write",
            ))

        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3


# ============================================================
# FilesystemMiddleware 测试
# ============================================================

class TestFilesystemMiddleware:
    """测试文件系统中间件。"""

    def test_default_disabled(self):
        """默认构造应启用审计。"""
        mw = FilesystemMiddleware()
        assert mw.audit is True
        assert mw.track_changes is True

    def test_passthrough_when_no_file_tools(self):
        """没有文件操作工具时应直接透传。"""
        mw = FilesystemMiddleware(audit=False, track_changes=False)
        request = make_mock_request(tools=[make_mock_tool("bash")])
        handler = MagicMock(return_value="response")

        result = mw.wrap_model_call(request, handler)
        handler.assert_called_once_with(request)
        assert result == "response"

    def test_records_file_operation(self):
        """应记录文件操作。"""
        mw = FilesystemMiddleware(audit=True, track_changes=False)

        request = make_mock_request(tools=[make_mock_tool("write_file")])
        response = make_tool_call_response("write_file", {"file_path": "output.txt", "content": "hello"})

        handler = MagicMock(return_value=response)
        mw.wrap_model_call(request, handler)

        assert len(mw.audit_log.operations) == 1
        op = mw.audit_log.operations[0]
        assert op.tool_name == "write_file"
        assert op.file_path == "output.txt"
        assert op.operation == "write"

    def test_ignores_non_file_tools(self):
        """非文件操作工具不应被记录。"""
        mw = FilesystemMiddleware(audit=True)

        request = make_mock_request(tools=[make_mock_tool("bash")])
        response = make_tool_call_response("bash", {"command": "ls"})

        handler = MagicMock(return_value=response)
        mw.wrap_model_call(request, handler)

        assert len(mw.audit_log.operations) == 0

    def test_audit_disabled(self):
        """审计禁用时不应记录。"""
        mw = FilesystemMiddleware(audit=False)

        request = make_mock_request(tools=[make_mock_tool("write_file")])
        response = make_tool_call_response("write_file", {"file_path": "test.txt"})

        handler = MagicMock(return_value=response)
        mw.wrap_model_call(request, handler)

        assert mw.audit_log is None

    def test_custom_workspace(self):
        """应支持自定义工作目录。"""
        mw = FilesystemMiddleware(workspace="/project/src")
        assert mw.workspace == "/project/src"

    def test_audit_log_with_persistence(self, tmp_path):
        """审计日志应持久化到文件。"""
        log_file = tmp_path / "audit.jsonl"
        mw = FilesystemMiddleware(audit=True, log_path=str(log_file))

        request = make_mock_request(tools=[make_mock_tool("edit_file")])
        response = make_tool_call_response("edit_file", {"file_path": "main.py"})

        handler = MagicMock(return_value=response)
        mw.wrap_model_call(request, handler)

        assert log_file.exists()
        record = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert record["tool_name"] == "edit_file"

    def test_multiple_operations_logged(self):
        """多次文件操作应全部记录。"""
        mw = FilesystemMiddleware(audit=True)

        # 模拟响应中有两个文件操作
        tool_call_1 = MagicMock()
        tool_call_1.name = "write_file"
        tool_call_1.args = {"file_path": "a.txt"}

        tool_call_2 = MagicMock()
        tool_call_2.name = "read_file"
        tool_call_2.args = {"file_path": "b.txt"}

        msg = MagicMock()
        msg.tool_calls = [tool_call_1, tool_call_2]
        response = {"messages": [msg]}

        request = make_mock_request(tools=[make_mock_tool("write_file"), make_mock_tool("read_file")])
        handler = MagicMock(return_value=response)

        mw.wrap_model_call(request, handler)

        assert len(mw.audit_log.operations) == 2
        assert mw.audit_log.operations[0].operation == "write"
        assert mw.audit_log.operations[1].operation == "read"
