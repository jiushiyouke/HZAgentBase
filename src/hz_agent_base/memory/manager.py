"""Memory manager - handles persistent memory storage.

高并发改造：写入时使用 FileLock 防止竞态，写入后自动使缓存失效。
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from .cache import FileLock
from .relevance import invalidate_memory_cache


class MemoryManager:
    """Manages persistent file-based memory storage.

    Memories are stored as Markdown files with YAML frontmatter
    in the specified directory.
    """

    def __init__(self, memory_path: str):
        self.path = Path(memory_path)
        self.path.mkdir(parents=True, exist_ok=True)

    def add_memory(
        self,
        title: str,
        content: str,
        *,
        memory_type: str = "general",
        description: str = "",
        tags: list[str] | None = None,
        user_id: str | None = None,
    ) -> Path:
        """Add a new memory entry.

        Args:
            title: Short title for the memory.
            content: Memory content.
            memory_type: Type of memory (user, feedback, project, reference).
            description: One-line description for the index.
            tags: Optional tags for categorization.
            user_id: Optional user ID for sharded locking.

        Returns:
            Path to the created memory file.
        """
        # Generate filename from title
        slug = self._title_to_slug(title)
        filepath = self.path / f"{slug}.md"

        # 使用分片锁：按 slug 分锁，不同记忆文件可以并发写入
        lock = FileLock.sharded(self.path, key=slug, user_id=user_id)
        with lock:
            # Check if memory already exists (dedup by content signature)
            signature = self._content_signature(content)
            if filepath.exists():
                existing = filepath.read_text(encoding="utf-8")
                if self._content_signature(existing) == signature:
                    return filepath  # Already exists with same content

            # Build frontmatter
            tags_str = ", ".join(tags) if tags else ""
            frontmatter = f"""---
name: {slug}
description: {description or title}
metadata:
  type: {memory_type}
  tags: [{tags_str}]
  created: {datetime.now().isoformat()}
  signature: {signature}
---"""

            # Write memory file
            filepath.write_text(
                f"{frontmatter}\n\n{content}\n",
                encoding="utf-8",
            )

            # Update index
            self._update_index(slug, description or title)

        # 写入完成后使缓存失效
        invalidate_memory_cache(self.path)

        return filepath

    def list_memories(self) -> list[dict[str, str]]:
        """List all memories in the directory."""
        memories = []
        for f in self.path.glob("*.md"):
            if f.name == "MEMORY.md":
                continue
            memories.append({
                "path": str(f),
                "name": f.stem,
            })
        return memories

    def extract_and_save(
        self,
        messages: list[Any],
        response: Any,
    ) -> list[Path]:
        """Extract memories from conversation and save them.

        使用关键词模式匹配从对话中提取值得记忆的信息。
        支持的记忆触发模式：
        - "记住..." / "remember..."
        - "我喜欢..." / "我偏好..." / "I prefer..."
        - "不要..." / "别..." / "don't..."
        - "我是..." / "I am..."（角色/身份信息）

        Args:
            messages: 对话历史消息列表。
            response: Agent 的响应（支持 dict 或带 messages 属性的对象）。

        Returns:
            已保存的记忆文件路径列表。
        """
        saved: list[Path] = []

        # 提取用户消息文本
        user_texts = self._extract_user_texts(messages)
        if not user_texts:
            return saved

        # 合并最近几轮对话用于上下文
        recent = user_texts[-5:]

        for text in recent:
            memories = self._parse_memory_patterns(text)
            for title, content, mem_type in memories:
                path = self.add_memory(
                    title=title,
                    content=content,
                    memory_type=mem_type,
                    description=f"从对话中自动提取: {title}",
                )
                saved.append(path)

        return saved

    def _extract_user_texts(self, messages: list[Any]) -> list[str]:
        """从消息列表中提取用户消息文本。"""
        texts = []
        for msg in messages:
            # 支持多种消息格式
            role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
            if role != "user":
                continue
            content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else None)
            if content and isinstance(content, str):
                texts.append(content)
        return texts

    def _parse_memory_patterns(self, text: str) -> list[tuple[str, str, str]]:
        """从文本中匹配记忆触发模式。

        Returns:
            列表元素为 (title, content, memory_type)。
        """
        import re

        results: list[tuple[str, str, str]] = []

        # 模式定义：(正则, memory_type)
        patterns = [
            # "记住xxx" / "remember xxx"
            (r"(?:记住|记得|remember)[:：\s]*(.+)", "user"),
            # "我喜欢xxx" / "我偏好xxx" / "I prefer xxx"
            (r"(?:我(?:喜欢|偏好|习惯)|i\s+prefer)[:：\s]*(.+)", "user"),
            # "不要xxx" / "别xxx" / "don't xxx"
            (r"(?:不要|别|请勿|don'?t)[:：\s]*(.+)", "feedback"),
            # "我是xxx" / "I am xxx"（身份/角色）
            (r"(?:我是|i\s+am(?:\s+a)?)[:：\s]*(.+)", "user"),
        ]

        for pattern, mem_type in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                content = match.group(1).strip()
                if len(content) >= 2:  # 过滤过短的匹配
                    # 用内容前20个字符作为标题
                    title = content[:20].replace("\n", " ")
                    results.append((title, content, mem_type))

        return results

    def _title_to_slug(self, title: str) -> str:
        """Convert a title to a filesystem-safe slug."""
        import re
        slug = title.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug)
        return slug[:64]

    def _content_signature(self, content: str) -> str:
        """生成内容签名用于去重（SHA-256）。"""
        normalized = content.strip().lower()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _update_index(self, slug: str, description: str) -> None:
        """Update the MEMORY.md index file."""
        index_path = self.path / "MEMORY.md"
        entry = f"- [{slug}]({slug}.md) — {description}\n"

        if index_path.exists():
            content = index_path.read_text(encoding="utf-8")
            if entry not in content:
                with open(index_path, "a", encoding="utf-8") as f:
                    f.write(entry)
        else:
            index_path.write_text(
                f"# Memory Index\n\n{entry}",
                encoding="utf-8",
            )
