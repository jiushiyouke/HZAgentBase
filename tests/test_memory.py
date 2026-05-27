"""测试记忆系统：MemoryManager、relevance 搜索。"""

import pytest
from pathlib import Path

from hz_agent_base.memory.manager import MemoryManager
from hz_agent_base.memory.relevance import (
    select_relevant_memories,
    format_relevant_memories,
    _tokenize,
    _parse_memory_file,
    MemoryEntry,
)


class TestMemoryManager:
    """测试 MemoryManager。"""

    def test_creates_directory(self, tmp_path):
        """初始化时应创建记忆目录。"""
        mem_dir = tmp_path / "new_memory"
        manager = MemoryManager(str(mem_dir))
        assert mem_dir.exists()

    def test_add_memory_creates_file(self, tmp_memory_dir):
        """添加记忆应创建文件。"""
        manager = MemoryManager(str(tmp_memory_dir))
        path = manager.add_memory("test-key", "这是一条测试记忆")

        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "test-key" in content
        assert "这是一条测试记忆" in content

    def test_add_memory_has_frontmatter(self, tmp_memory_dir):
        """记忆文件应包含 YAML frontmatter。"""
        manager = MemoryManager(str(tmp_memory_dir))
        path = manager.add_memory("test", "content", memory_type="user")

        content = path.read_text(encoding="utf-8")
        assert content.startswith("---")
        assert "type: user" in content

    def test_add_memory_dedup(self, tmp_memory_dir):
        """相同内容不应重复创建。"""
        manager = MemoryManager(str(tmp_memory_dir))
        path1 = manager.add_memory("test", "same content")
        path2 = manager.add_memory("test", "same content")

        assert path1 == path2

    def test_list_memories(self, tmp_memory_dir):
        """应能列出所有记忆。"""
        manager = MemoryManager(str(tmp_memory_dir))
        manager.add_memory("memory-a", "content a")
        manager.add_memory("memory-b", "content b")

        memories = manager.list_memories()
        names = {m["name"] for m in memories}
        assert "memory-a" in names
        assert "memory-b" in names

    def test_list_memories_excludes_index(self, tmp_memory_dir):
        """列出记忆时应排除 MEMORY.md 索引文件。"""
        manager = MemoryManager(str(tmp_memory_dir))
        manager.add_memory("test", "content")

        memories = manager.list_memories()
        for m in memories:
            assert "MEMORY.md" not in m["path"]

    def test_update_index(self, tmp_memory_dir):
        """添加记忆应更新 MEMORY.md 索引。"""
        manager = MemoryManager(str(tmp_memory_dir))
        manager.add_memory("my-memory", "some content")

        index_path = tmp_memory_dir / "MEMORY.md"
        assert index_path.exists()
        content = index_path.read_text(encoding="utf-8")
        assert "my-memory" in content


class TestRelevance:
    """测试相关性搜索。"""

    def test_tokenize(self):
        """分词应返回小写单词集合。"""
        tokens = _tokenize("Hello World! Test-123")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens
        assert "123" in tokens

    def test_parse_memory_file_with_frontmatter(self):
        """解析带 frontmatter 的记忆文件。"""
        content = """---
name: my-mem
description: A test memory
type: user
---

Body content here."""
        name, desc, mem_type, body = _parse_memory_file(content)
        assert name == "my-mem"
        assert desc == "A test memory"
        assert mem_type == "user"
        assert "Body content here" in body

    def test_parse_memory_file_no_frontmatter(self):
        """没有 frontmatter 时应返回原始内容作为 body。"""
        content = "Just plain text content."
        name, desc, mem_type, body = _parse_memory_file(content)
        assert name == ""
        assert body == content

    def test_select_relevant_memories(self, tmp_memory_dir):
        """应能根据查询选出相关记忆。"""
        manager = MemoryManager(str(tmp_memory_dir))
        manager.add_memory("python-tips", "Python logging 最佳实践")
        manager.add_memory("cooking", "如何做红烧肉")

        results = select_relevant_memories("Python logging", str(tmp_memory_dir))
        assert len(results) > 0
        assert "python-tips" in results[0].name

    def test_select_relevant_memories_empty_dir(self, tmp_path):
        """空目录应返回空列表。"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        results = select_relevant_memories("query", str(empty_dir))
        assert results == []

    def test_select_relevant_memories_nonexistent_dir(self, tmp_path):
        """不存在的目录应返回空列表。"""
        results = select_relevant_memories("query", str(tmp_path / "nope"))
        assert results == []

    def test_select_limits_results(self, tmp_memory_dir):
        """应限制返回数量。"""
        manager = MemoryManager(str(tmp_memory_dir))
        for i in range(10):
            manager.add_memory(f"mem-{i}", f"content about python {i}")

        results = select_relevant_memories("python", str(tmp_memory_dir), max_results=3)
        assert len(results) <= 3

    def test_format_relevant_memories(self):
        """格式化输出应包含记忆名称和内容。"""
        memories = [
            MemoryEntry(
                path=Path("/test"),
                name="test-mem",
                description="A test",
                memory_type="general",
                content="Important content",
            )
        ]
        formatted = format_relevant_memories(memories)
        assert "test-mem" in formatted
        assert "Important content" in formatted

    def test_format_empty_memories(self):
        """空记忆列表应返回空字符串。"""
        assert format_relevant_memories([]) == ""

    def test_zero_score_filtered_out(self, tmp_memory_dir):
        """评分为零的记忆应被过滤。"""
        manager = MemoryManager(str(tmp_memory_dir))
        manager.add_memory("unrelated", "烹饪美食大全")

        results = select_relevant_memories("quantum physics", str(tmp_memory_dir))
        assert len(results) == 0
