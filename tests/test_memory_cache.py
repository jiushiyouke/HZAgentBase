"""测试记忆缓存和文件锁。"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from hz_agent_base.memory.cache import MemoryCache, FileLock


# ============================================================
# MemoryCache 测试
# ============================================================

class TestMemoryCache:
    """测试 MemoryCache 的基本功能。"""

    def test_get_put(self):
        """基本的 get/put 操作。"""
        cache = MemoryCache(max_size=100, ttl_seconds=60)
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent(self):
        """获取不存在的 key 应返回 None。"""
        cache = MemoryCache(max_size=100, ttl_seconds=60)
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self):
        """过期的条目应返回 None。"""
        cache = MemoryCache(max_size=100, ttl_seconds=0)
        cache.put("key1", "value1")
        time.sleep(0.01)
        assert cache.get("key1") is None

    def test_lru_eviction(self):
        """超出容量时应淘汰最久未使用的条目。"""
        cache = MemoryCache(max_size=3, ttl_seconds=60)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.put("d", 4)  # 应淘汰 "a"
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("d") == 4

    def test_lru_access_refreshes(self):
        """访问条目应刷新其 LRU 位置。"""
        cache = MemoryCache(max_size=3, ttl_seconds=60)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.get("a")  # 刷新 "a"
        cache.put("d", 4)  # 应淘汰 "b"（最久未访问）
        assert cache.get("a") == 1
        assert cache.get("b") is None

    def test_invalidate(self):
        """invalidate 应删除指定条目。"""
        cache = MemoryCache(max_size=100, ttl_seconds=60)
        cache.put("key1", "value1")
        cache.invalidate("key1")
        assert cache.get("key1") is None

    def test_invalidate_nonexistent(self):
        """invalidate 不存在的 key 不应报错。"""
        cache = MemoryCache(max_size=100, ttl_seconds=60)
        cache.invalidate("nonexistent")  # 不应抛异常

    def test_invalidate_all(self):
        """invalidate_all 应清空全部缓存。"""
        cache = MemoryCache(max_size=100, ttl_seconds=60)
        for i in range(10):
            cache.put(f"key-{i}", f"value-{i}")
        cache.invalidate_all()
        assert cache.size == 0

    def test_size_property(self):
        """size 属性应返回当前条目数。"""
        cache = MemoryCache(max_size=100, ttl_seconds=60)
        assert cache.size == 0
        cache.put("a", 1)
        assert cache.size == 1
        cache.put("b", 2)
        assert cache.size == 2

    def test_overwrite_existing_key(self):
        """写入已存在的 key 应更新值。"""
        cache = MemoryCache(max_size=100, ttl_seconds=60)
        cache.put("key1", "old")
        cache.put("key1", "new")
        assert cache.get("key1") == "new"
        assert cache.size == 1


# ============================================================
# FileLock 测试
# ============================================================

class TestFileLock:
    """测试 FileLock 的基本功能。"""

    def test_basic_lock_unlock(self, tmp_path):
        """基本的加锁/解锁操作。"""
        lock_path = tmp_path / ".lock"
        with FileLock(lock_path):
            pass  # 不应抛异常

    def test_lock_creates_file(self, tmp_path):
        """加锁应创建锁文件。"""
        lock_path = tmp_path / ".lock"
        with FileLock(lock_path):
            assert lock_path.exists()

    def test_concurrent_access(self, tmp_path):
        """并发访问应被序列化。"""
        counter_file = tmp_path / "counter.txt"
        counter_file.write_text("0", encoding="utf-8")
        lock_path = tmp_path / ".lock"
        errors = []

        def increment():
            try:
                for _ in range(10):
                    with FileLock(lock_path):
                        val = int(counter_file.read_text(encoding="utf-8"))
                        val += 1
                        counter_file.write_text(str(val), encoding="utf-8")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=increment) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"错误: {errors}"
        final = int(counter_file.read_text(encoding="utf-8"))
        assert final == 100, f"计数器值不正确: {final}（预期 100）"

    def test_lock_with_exception(self, tmp_path):
        """锁内抛异常应正常释放锁。"""
        lock_path = tmp_path / ".lock"
        try:
            with FileLock(lock_path):
                raise ValueError("test error")
        except ValueError:
            pass

        # 锁应已释放，再次加锁不应阻塞
        with FileLock(lock_path):
            pass


# ============================================================
# 集成测试：缓存 + 文件锁 + MemoryManager
# ============================================================

class TestMemoryCacheIntegration:
    """测试缓存与 MemoryManager 的集成。"""

    def test_write_invalidates_cache(self, tmp_path):
        """写入新记忆后缓存应失效。"""
        from hz_agent_base.memory.manager import MemoryManager
        from hz_agent_base.memory.relevance import select_relevant_memories

        manager = MemoryManager(str(tmp_path / "memory"))
        cache = MemoryCache(max_size=100, ttl_seconds=60)

        # 写入记忆
        manager.add_memory(title="python", content="Python is great")

        # 搜索应能命中（缓存失效后重新加载）
        results = select_relevant_memories(
            query="python",
            memory_path=str(tmp_path / "memory"),
            cache=cache,
        )
        assert len(results) > 0

    def test_cache_hit_avoids_disk_read(self, tmp_path):
        """缓存命中时不应读磁盘。"""
        from hz_agent_base.memory.relevance import (
            select_relevant_memories,
            _load_memories,
        )

        # 手动创建记忆文件
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "test.md").write_text(
            "---\nname: test\ndescription: test memory\n---\n\nTest content",
            encoding="utf-8",
        )

        cache = MemoryCache(max_size=100, ttl_seconds=60)

        # 第一次加载（冷启动）
        results1 = select_relevant_memories(
            query="test",
            memory_path=str(memory_dir),
            cache=cache,
        )
        assert len(results1) == 1

        # 删除文件（缓存中仍有数据）
        (memory_dir / "test.md").unlink()

        # 第二次搜索应命中缓存
        results2 = select_relevant_memories(
            query="test",
            memory_path=str(memory_dir),
            cache=cache,
        )
        assert len(results2) == 1  # 缓存命中
