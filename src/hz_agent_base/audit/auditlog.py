"""审计日志 — 异步写入和 HMAC 签名。"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import queue
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from .operations import FileOperation

logger = logging.getLogger(__name__)


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
                    try:
                        line = self._write_queue.get(timeout=self._flush_interval)
                        if line is None:  # 哨兵值，退出
                            break
                        buffer.append(line)
                    except queue.Empty:
                        pass

                    # 批量写入条件：缓冲区满 或 超时
                    now = time.time()
                    if buffer and (len(buffer) >= self._buffer_size or now - last_flush >= self._flush_interval):
                        self._flush_buffer(buffer)
                        buffer.clear()
                        last_flush = now

                except Exception:
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
                pass

    def flush(self) -> None:
        """手动刷新（等待队列消费完毕）。"""
        if self._writer_thread and self._writer_thread.is_alive():
            self._write_queue.join()

    def close(self) -> None:
        """关闭审计日志（停止写入线程）。"""
        self._shutdown = True
        if self._writer_thread:
            self._write_queue.put(None)  # 哨兵值
            self._writer_thread.join(timeout=5)
            self._writer_thread = None

    def verify_log(self, log_path: str | None = None) -> tuple[bool, list[str]]:
        """校验审计日志的完整性。"""
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
