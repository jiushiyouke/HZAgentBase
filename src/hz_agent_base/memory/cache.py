"""记忆缓存与文件锁 — 高并发改造核心组件。

- MemoryCache: LRU + TTL 内存缓存，避免每次请求都读磁盘
- FileLock: 跨进程文件锁，防止并发写入竞态
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class MemoryCache:
    """记忆文件的 LRU + TTL 内存缓存。

    所有记忆条目缓存在内存中，避免每次请求都扫描磁盘。
    写入时自动使对应缓存失效，下次读取时重新加载。

    Args:
        max_size: 最大缓存条目数，超出时淘汰最久未使用的。
        ttl_seconds: 缓存过期时间（秒），过期条目在下次访问时重新加载。
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 60):
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        """从缓存获取条目，过期或不存在返回 None。"""
        with self._lock:
            if key not in self._cache:
                return None
            value, ts = self._cache[key]
            # 检查是否过期
            if time.time() - ts > self._ttl:
                del self._cache[key]
                return None
            # 移到末尾（LRU）
            self._cache.move_to_end(key)
            return value

    def put(self, key: str, value: Any) -> None:
        """写入缓存，超出容量时淘汰最久未使用的条目。"""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (value, time.time())
            # LRU 淘汰
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def invalidate(self, key: str) -> None:
        """使指定条目失效。"""
        with self._lock:
            self._cache.pop(key, None)

    def invalidate_all(self) -> None:
        """清空全部缓存。"""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        """当前缓存条目数。"""
        return len(self._cache)


class FileLock:
    """跨进程文件锁，防止并发写入竞态。

    使用方式：
        with FileLock(path / ".lock"):
            # 安全的文件读写操作
            ...

    Windows 使用 msvcrt.locking，Linux 使用 fcntl.flock。
    """

    def __init__(self, lock_path: Path):
        self._lock_path = lock_path
        self._fd = None

    def __enter__(self):
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = open(self._lock_path, "w")
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._fd.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX)
        except Exception:
            self._fd.close()
            raise
        return self

    def __exit__(self, *args):
        try:
            if self._fd:
                if os.name == "nt":
                    import msvcrt
                    try:
                        msvcrt.locking(self._fd.fileno(), msvcrt.LK_UNLCK, 1)
                    except Exception:
                        pass
                else:
                    import fcntl
                    fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
                self._fd.close()
        except Exception:
            pass
        finally:
            self._fd = None
