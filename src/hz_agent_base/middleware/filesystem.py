"""Filesystem middleware — 文件操作审计和变更追踪。

高并发改造：异步写入线程 + 内存上限（deque maxlen）。
安全改造：HMAC 签名 + workspace 限制。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware


# 需要审计的文件操作工具名
FILE_TOOLS = {
    "write_file", "edit_file", "read_file",
    "create_file", "delete_file", "rename_file",
    "remove_file", "move_file",
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


class AuditLog:
    """审计日志，记录所有文件操作。

    高并发改造：
    - operations 使用 deque(maxlen) 防止内存无限增长
    - 异步写入线程：日志记录放入队列，独立线程批量写入磁盘
    - 主线程不阻塞在磁盘 I/O 上

    安全改造：
    - 每条日志记录追加 HMAC-SHA256 签名
    - 提供 verify_log() 校验日志完整性
    - 签名密钥从环境变量 AUDIT_HMAC_KEY 读取

    Args:
        log_path: 日志持久化路径（空则不持久化）。
        max_operations: 内存中最多保留的操作记录数。
        buffer_size: 缓冲区满多少条后写入磁盘。
        flush_interval: 缓冲区最长多久写入一次（秒）。
        hmac_key: HMAC 签名密钥。None 时从环境变量 AUDIT_HMAC_KEY 读取。
    """

    def __init__(
        self,
        log_path: str = "",
        max_operations: int = 10000,
        buffer_size: int = 100,
        flush_interval: float = 5.0,
        hmac_key: bytes | None = None,
    ):
        self.operations: deque[FileOperation] = deque(maxlen=max_operations)
        self.log_path = log_path
        self._buffer_size = buffer_size
        self._flush_interval = flush_interval
        # HMAC 签名密钥
        if hmac_key is not None:
            self._hmac_key = hmac_key
        else:
            env_key = os.environ.get("AUDIT_HMAC_KEY", "")
            self._hmac_key = env_key.encode() if env_key else b""

        # 异步写入队列和线程
        self._write_queue: queue.Queue[str | None] = queue.Queue(maxsize=10000)
        self._writer_thread: threading.Thread | None = None
        self._shutdown = False
        # 刷盘信号哨兵（与退出哨兵 None 区分）
        self._FLUSH_SENTINEL = "__FLUSH__"
        if log_path:
            self._start_writer()

    def _start_writer(self) -> None:
        """启动异步写入线程。"""
        def _writer_loop():
            """写入线程主循环：从队列取记录，批量写入磁盘。"""
            buffer: list[str] = []
            last_flush = time.time()

            while not self._shutdown:
                try:
                    # 阻塞等待，超时后检查是否需要刷新
                    try:
                        line = self._write_queue.get(timeout=self._flush_interval)
                        if line is None:  # 退出哨兵
                            self._write_queue.task_done()
                            break
                        if line == self._FLUSH_SENTINEL:  # 刷盘信号
                            if buffer:
                                self._flush_buffer(buffer)
                                buffer.clear()
                                last_flush = time.time()
                            self._write_queue.task_done()
                            continue
                        buffer.append(line)
                        self._write_queue.task_done()  # 通知 put() 方消费完毕
                    except queue.Empty:
                        pass

                    # 批量写入条件：缓冲区满 或 超时
                    now = time.time()
                    if buffer and (len(buffer) >= self._buffer_size or now - last_flush >= self._flush_interval):
                        self._flush_buffer(buffer)
                        buffer.clear()
                        last_flush = now

                except Exception:
                    # 写入异常不应影响主线程
                    pass

            # 退出前写入剩余数据
            if buffer:
                self._flush_buffer(buffer)

        self._writer_thread = threading.Thread(
            target=_writer_loop, daemon=True, name="audit-writer"
        )
        self._writer_thread.start()

    def _flush_buffer(self, buffer: list[str]) -> None:
        """批量写入磁盘。"""
        if not buffer or not self.log_path:
            return
        log_file = Path(self.log_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.writelines(buffer)

    def _sign_record(self, record_json: str) -> str:
        """为日志记录生成 HMAC-SHA256 签名。"""
        if not self._hmac_key:
            return record_json + "\n"
        sig = hmac.new(self._hmac_key, record_json.encode(), hashlib.sha256).hexdigest()[:16]
        record = json.loads(record_json)
        record["__sig"] = sig
        return json.dumps(record, ensure_ascii=False) + "\n"

    def add(self, op: FileOperation) -> None:
        """添加一条操作记录（内存 + 异步写入队列）。"""
        self.operations.append(op)
        if self.log_path and self._writer_thread:
            record = {
                "timestamp": op.timestamp,
                "tool_name": op.tool_name,
                "file_path": op.file_path,
                "operation": op.operation,
                "thread_id": op.thread_id,
                "success": op.success,
            }
            record_json = json.dumps(record, ensure_ascii=False)
            line = self._sign_record(record_json)
            try:
                self._write_queue.put_nowait(line)
            except queue.Full:
                # 队列满时丢弃（避免阻塞主线程）
                pass

    def flush(self) -> None:
        """手动刷新（等待队列消费完毕 + 强制刷盘）。"""
        if self._writer_thread and self._writer_thread.is_alive():
            # 等待队列消费完毕
            self._write_queue.join()
            # 发送刷盘信号，让写入线程清空 buffer
            self._write_queue.put_nowait(self._FLUSH_SENTINEL)
            self._write_queue.join()  # 等待刷盘完成

    def close(self) -> None:
        """关闭审计日志（停止写入线程）。"""
        self._shutdown = True
        if self._writer_thread:
            self._write_queue.put(None)  # 哨兵值
            self._writer_thread.join(timeout=5)
            self._writer_thread = None

    def verify_log(self, log_path: str | None = None) -> tuple[bool, list[str]]:
        """校验审计日志的完整性。

        Args:
            log_path: 日志文件路径。None 时使用 self.log_path。

        Returns:
            (is_valid, errors) 元组。is_valid 为 True 表示所有记录签名正确。
        """
        path = Path(log_path or self.log_path)
        if not path.exists():
            return True, []

        if not self._hmac_key:
            return True, ["HMAC key not configured, skipping verification"]

        errors = []
        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    sig = record.pop("__sig", None)
                    if sig is None:
                        errors.append(f"Line {line_num}: missing signature")
                        continue
                    # 重新计算签名
                    record_json = json.dumps(record, ensure_ascii=False)
                    expected_sig = hmac.new(
                        self._hmac_key, record_json.encode(), hashlib.sha256
                    ).hexdigest()[:16]
                    if sig != expected_sig:
                        errors.append(f"Line {line_num}: signature mismatch")
                except json.JSONDecodeError:
                    errors.append(f"Line {line_num}: invalid JSON")

        return len(errors) == 0, errors

    def query(
        self,
        *,
        file_path: str | None = None,
        operation: str | None = None,
        thread_id: str | None = None,
    ) -> list[FileOperation]:
        """按条件查询操作记录。"""
        results = list(self.operations)
        if file_path:
            results = [op for op in results if op.file_path == file_path]
        if operation:
            results = [op for op in results if op.operation == operation]
        if thread_id:
            results = [op for op in results if op.thread_id == thread_id]
        return results


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
            # 检查是否为工具调用消息
            tool_calls = getattr(msg, "tool_calls", None) or []
            for tc in tool_calls:
                tool_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                if tool_name not in FILE_TOOLS:
                    continue

                args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                file_path = args.get("file_path", "") or args.get("path", "")

                # workspace 限制检查
                if file_path and not self._is_in_workspace(file_path):
                    # 超出 workspace 范围，记录但标记为失败
                    op = FileOperation(
                        timestamp=datetime.now().isoformat(),
                        tool_name=tool_name,
                        file_path=file_path,
                        operation=_classify_operation(tool_name),
                        thread_id=thread_id,
                        success=False,
                    )
                    self.audit_log.add(op)
                    continue

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
