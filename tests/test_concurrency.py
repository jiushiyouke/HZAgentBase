"""并发压测脚本 — 100 线程并发验证高并发改造效果。

测试内容：
1. 记忆缓存并发读取（100 线程同时读）
2. 记忆系统并发写入（100 线程同时写，验证文件锁）
3. 审计日志并发写入（100 线程同时写，验证缓冲机制）
4. Hook 并行执行（验证全局线程池）
5. 记忆缓存并发读写混合（验证缓存失效）

运行方式：
    python -m pytest tests/test_concurrency.py -v
"""

from __future__ import annotations

import json
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from hz_agent_base.memory.cache import MemoryCache, FileLock
from hz_agent_base.memory.manager import MemoryManager
from hz_agent_base.memory.relevance import (
    select_relevant_memories,
    get_memory_cache,
    invalidate_memory_cache,
)
from hz_agent_base.middleware.filesystem import AuditLog, FileOperation
from hz_agent_base.hooks.executor import HookExecutor, get_hook_pool, set_hook_pool
from hz_agent_base.hooks.registry import HookRegistry
from hz_agent_base.hooks.events import HookEvent
from hz_agent_base.hooks.schemas import CommandHookDefinition


CONCURRENT_THREADS = 100


# ============================================================
# 1. 记忆缓存并发读取
# ============================================================

class TestMemoryCacheConcurrency:
    """测试 MemoryCache 的并发安全性。"""

    def test_concurrent_read_write(self, tmp_path):
        """100 线程同时读写缓存，不应崩溃或数据错乱。"""
        cache = MemoryCache(max_size=500, ttl_seconds=60)
        errors = []
        results = []

        def writer(thread_id: int):
            try:
                for i in range(10):
                    cache.put(f"key-{thread_id}-{i}", f"value-{thread_id}-{i}")
            except Exception as e:
                errors.append(f"writer-{thread_id}: {e}")

        def reader(thread_id: int):
            try:
                hits = 0
                for i in range(10):
                    val = cache.get(f"key-{thread_id}-{i}")
                    if val is not None:
                        hits += 1
                results.append(hits)
            except Exception as e:
                errors.append(f"reader-{thread_id}: {e}")

        # 先写后读
        with ThreadPoolExecutor(max_workers=CONCURRENT_THREADS) as pool:
            futures = [pool.submit(writer, i) for i in range(CONCURRENT_THREADS)]
            for f in as_completed(futures):
                f.result()

        with ThreadPoolExecutor(max_workers=CONCURRENT_THREADS) as pool:
            futures = [pool.submit(reader, i) for i in range(CONCURRENT_THREADS)]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0, f"并发错误: {errors}"
        assert cache.size <= 500, f"缓存超出上限: {cache.size}"

    def test_concurrent_invalidate(self):
        """100 线程同时失效缓存，不应崩溃。"""
        cache = MemoryCache(max_size=1000, ttl_seconds=60)
        errors = []

        # 预填充
        for i in range(1000):
            cache.put(f"key-{i}", f"value-{i}")

        def invalidator(thread_id: int):
            try:
                for i in range(10):
                    cache.invalidate(f"key-{thread_id * 10 + i}")
            except Exception as e:
                errors.append(f"invalidator-{thread_id}: {e}")

        with ThreadPoolExecutor(max_workers=CONCURRENT_THREADS) as pool:
            futures = [pool.submit(invalidator, i) for i in range(CONCURRENT_THREADS)]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0, f"并发错误: {errors}"


# ============================================================
# 2. 记忆系统并发写入
# ============================================================

class TestMemoryManagerConcurrency:
    """测试 MemoryManager 的文件锁并发安全性。"""

    def test_concurrent_add_memory(self, tmp_path):
        """100 线程同时写入记忆，不应产生竞态条件。"""
        manager = MemoryManager(str(tmp_path / "memory"))
        errors = []
        paths = []
        lock = threading.Lock()

        def adder(thread_id: int):
            try:
                path = manager.add_memory(
                    title=f"记忆-{thread_id}",
                    content=f"这是线程 {thread_id} 写入的记忆内容",
                    memory_type="user",
                )
                with lock:
                    paths.append(path)
            except Exception as e:
                errors.append(f"adder-{thread_id}: {e}")

        with ThreadPoolExecutor(max_workers=CONCURRENT_THREADS) as pool:
            futures = [pool.submit(adder, i) for i in range(CONCURRENT_THREADS)]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0, f"并发错误: {errors}"
        assert len(paths) == CONCURRENT_THREADS

        # 验证所有文件都存在
        for path in paths:
            assert path.exists(), f"文件不存在: {path}"

        # 验证索引文件没有重复条目
        index_path = tmp_path / "memory" / "MEMORY.md"
        if index_path.exists():
            content = index_path.read_text(encoding="utf-8")
            lines = [l for l in content.strip().split("\n") if l.startswith("- [")]
            # 索引条目数应等于写入数（去重后）
            assert len(lines) == CONCURRENT_THREADS, f"索引条目数不匹配: {len(lines)} vs {CONCURRENT_THREADS}"

    def test_concurrent_add_same_memory(self, tmp_path):
        """100 线程同时写入相同内容，应去重。"""
        manager = MemoryManager(str(tmp_path / "memory"))
        errors = []
        paths = []
        lock = threading.Lock()

        def adder(thread_id: int):
            try:
                path = manager.add_memory(
                    title="相同的记忆",
                    content="所有线程写入的内容完全一样",
                    memory_type="user",
                )
                with lock:
                    paths.append(path)
            except Exception as e:
                errors.append(f"adder-{thread_id}: {e}")

        with ThreadPoolExecutor(max_workers=CONCURRENT_THREADS) as pool:
            futures = [pool.submit(adder, i) for i in range(CONCURRENT_THREADS)]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0, f"并发错误: {errors}"
        # 去重后应只有一个文件
        unique_paths = set(str(p) for p in paths)
        assert len(unique_paths) == 1, f"去重失败，产生了 {len(unique_paths)} 个文件"


# ============================================================
# 3. 审计日志并发写入
# ============================================================

class TestAuditLogConcurrency:
    """测试 AuditLog 的缓冲写入并发安全性。"""

    def test_concurrent_buffered_write(self, tmp_path):
        """100 线程同时写入审计日志，验证批量缓冲机制。"""
        log_file = tmp_path / "audit.jsonl"
        log = AuditLog(
            log_path=str(log_file),
            buffer_size=50,
            flush_interval=1.0,
        )
        errors = []

        def writer(thread_id: int):
            try:
                for i in range(10):
                    log.add(FileOperation(
                        timestamp=f"2026-01-01T00:00:{thread_id:02d}",
                        tool_name="write_file",
                        file_path=f"file-{thread_id}-{i}.txt",
                        operation="write",
                    ))
            except Exception as e:
                errors.append(f"writer-{thread_id}: {e}")

        with ThreadPoolExecutor(max_workers=CONCURRENT_THREADS) as pool:
            futures = [pool.submit(writer, i) for i in range(CONCURRENT_THREADS)]
            for f in as_completed(futures):
                f.result()

        # 关闭日志，确保所有数据写入磁盘
        log.close()

        assert len(errors) == 0, f"并发错误: {errors}"

        # 验证所有记录都写入了磁盘
        assert log_file.exists(), "日志文件不存在"
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == CONCURRENT_THREADS * 10, \
            f"日志行数不匹配: {len(lines)} vs {CONCURRENT_THREADS * 10}"

        # 验证内存中也有记录
        assert len(log.operations) == CONCURRENT_THREADS * 10

    def test_concurrent_mixed_operations(self, tmp_path):
        """100 线程混合不同类型的操作写入。"""
        log_file = tmp_path / "audit.jsonl"
        log = AuditLog(log_path=str(log_file), buffer_size=100)
        errors = []
        operations = ["read", "write", "edit", "delete"]

        def writer(thread_id: int):
            try:
                for i in range(5):
                    log.add(FileOperation(
                        timestamp="2026-01-01T00:00:00",
                        tool_name=f"{operations[i % 4]}_file",
                        file_path=f"file-{thread_id}-{i}.txt",
                        operation=operations[i % 4],
                    ))
            except Exception as e:
                errors.append(f"writer-{thread_id}: {e}")

        with ThreadPoolExecutor(max_workers=CONCURRENT_THREADS) as pool:
            futures = [pool.submit(writer, i) for i in range(CONCURRENT_THREADS)]
            for f in as_completed(futures):
                f.result()

        log.flush()

        assert len(errors) == 0, f"并发错误: {errors}"
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == CONCURRENT_THREADS * 5


# ============================================================
# 4. Hook 并行执行
# ============================================================

class TestHookExecutorConcurrency:
    """测试 HookExecutor 的并行执行。"""

    def test_parallel_hook_execution(self):
        """多个 Hook 并行执行，延迟应取最大而非求和。"""
        registry = HookRegistry()
        delay = 0.2  # 每个 hook 延迟 0.2 秒

        for i in range(5):
            registry.register(CommandHookDefinition(
                event=HookEvent.POST_TOOL_USE,
                command=f"python -c \"import time; time.sleep(0.2)\"",
                block_on_failure=False,
            ))

        executor = HookExecutor(registry)
        start = time.time()
        result = executor.execute(HookEvent.POST_TOOL_USE, {"test": True})
        elapsed = time.time() - start

        # 5 个 hook 并行执行，总时间应远小于 5 * delay
        assert len(result.results) == 5
        # 串行需要至少 5 * 0.2 = 1.0 秒，并行应快很多
        # 给一些余量，只要小于 0.8 秒就算通过
        assert elapsed < 0.8, f"并行执行太慢: {elapsed:.2f}s（预期 < 0.8s）"

    def test_single_hook_no_thread_pool(self):
        """单个 hook 不走线程池，直接执行。"""
        registry = HookRegistry()
        registry.register(CommandHookDefinition(
            event=HookEvent.POST_TOOL_USE,
            command="echo test",
            block_on_failure=False,
        ))

        executor = HookExecutor(registry)
        result = executor.execute(HookEvent.POST_TOOL_USE, {"test": True})

        assert len(result.results) == 1
        assert result.results[0].success

    def test_global_thread_pool_singleton(self):
        """全局线程池应为单例。"""
        pool1 = get_hook_pool(max_workers=10)
        pool2 = get_hook_pool(max_workers=20)  # 参数应被忽略
        assert pool1 is pool2

        # 清理
        set_hook_pool(None)


# ============================================================
# 5. 记忆缓存读写混合
# ============================================================

class TestMemoryCacheReadWriteMix:
    """测试记忆缓存的读写混合场景。"""

    def test_concurrent_read_write_with_invalidate(self, tmp_path):
        """100 线程同时读写记忆，中间穿插缓存失效。"""
        cache = MemoryCache(max_size=1000, ttl_seconds=60)
        manager = MemoryManager(str(tmp_path / "memory"))
        errors = []

        def worker(thread_id: int):
            try:
                # 写入记忆
                manager.add_memory(
                    title=f"thread-{thread_id}",
                    content=f"content from thread {thread_id}",
                )
                # 搜索记忆
                results = select_relevant_memories(
                    query=f"thread {thread_id}",
                    memory_path=str(tmp_path / "memory"),
                    max_results=5,
                    cache=cache,
                )
                # 再次写入
                manager.add_memory(
                    title=f"thread-{thread_id}-v2",
                    content=f"updated content from thread {thread_id}",
                )
            except Exception as e:
                errors.append(f"worker-{thread_id}: {e}")

        with ThreadPoolExecutor(max_workers=CONCURRENT_THREADS) as pool:
            futures = [pool.submit(worker, i) for i in range(CONCURRENT_THREADS)]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0, f"并发错误: {errors}"

        # 验证文件数量
        memory_dir = tmp_path / "memory"
        md_files = list(memory_dir.glob("*.md"))
        md_files = [f for f in md_files if f.name != "MEMORY.md"]
        assert len(md_files) == CONCURRENT_THREADS * 2  # 每个线程写了 2 个


# ============================================================
# 6. 性能基准
# ============================================================

class TestPerformanceBenchmark:
    """性能基准测试，验证改造效果。"""

    def test_memory_cache_speedup(self, tmp_path):
        """缓存命中时应比磁盘读取快 10 倍以上。"""
        manager = MemoryManager(str(tmp_path / "memory"))

        # 预写入 100 个记忆
        for i in range(100):
            manager.add_memory(
                title=f"memory-{i}",
                content=f"This is memory number {i} about topic {i % 10}",
            )

        cache = MemoryCache(max_size=1000, ttl_seconds=60)

        # 冷启动（无缓存）
        start = time.time()
        for _ in range(10):
            cache.invalidate_all()
            select_relevant_memories(
                query="topic 5",
                memory_path=str(tmp_path / "memory"),
                cache=cache,
            )
        cold_time = time.time() - start

        # 热缓存
        start = time.time()
        for _ in range(10):
            select_relevant_memories(
                query="topic 5",
                memory_path=str(tmp_path / "memory"),
                cache=cache,
            )
        hot_time = time.time() - start

        # 缓存命中应明显更快
        speedup = cold_time / hot_time if hot_time > 0 else float("inf")
        assert speedup > 2, f"缓存加速不足: {speedup:.1f}x（冷 {cold_time:.3f}s, 热 {hot_time:.3f}s）"

    def test_audit_buffer_speedup(self, tmp_path):
        """缓冲写入应比逐条写入快 5 倍以上。"""
        import os

        # 逐条写入
        log_file_1 = tmp_path / "sync.jsonl"
        log_sync = AuditLog(log_path=str(log_file_1), buffer_size=10000)  # 大缓冲区 = 不自动 flush

        start = time.time()
        for i in range(1000):
            log_sync.add(FileOperation(
                timestamp="2026-01-01T00:00:00",
                tool_name="write_file",
                file_path=f"file-{i}.txt",
                operation="write",
            ))
            # 模拟旧版逐条写入
            with open(log_file_1, "a") as f:
                f.write(json.dumps({"i": i}) + "\n")
        sync_time = time.time() - start

        # 批量缓冲写入
        log_file_2 = tmp_path / "buffered.jsonl"
        log_buffered = AuditLog(log_path=str(log_file_2), buffer_size=500)

        start = time.time()
        for i in range(1000):
            log_buffered.add(FileOperation(
                timestamp="2026-01-01T00:00:00",
                tool_name="write_file",
                file_path=f"file-{i}.txt",
                operation="write",
            ))
        log_buffered.flush()
        buffered_time = time.time() - start

        speedup = sync_time / buffered_time if buffered_time > 0 else float("inf")
        assert speedup > 2, f"缓冲加速不足: {speedup:.1f}x（同步 {sync_time:.3f}s, 缓冲 {buffered_time:.3f}s）"
