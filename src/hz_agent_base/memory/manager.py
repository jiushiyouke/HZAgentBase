"""Memory manager - handles persistent memory storage."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any


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
    ) -> Path:
        """Add a new memory entry.

        Args:
            title: Short title for the memory.
            content: Memory content.
            memory_type: Type of memory (user, feedback, project, reference).
            description: One-line description for the index.
            tags: Optional tags for categorization.

        Returns:
            Path to the created memory file.
        """
        # Generate filename from title
        slug = self._title_to_slug(title)
        filepath = self.path / f"{slug}.md"

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
    ) -> None:
        """Extract memories from conversation and save them.

        This is a placeholder implementation. In production, this would
        use an LLM to extract relevant memories from the conversation.
        """
        # TODO: Implement LLM-based memory extraction
        pass

    def _title_to_slug(self, title: str) -> str:
        """Convert a title to a filesystem-safe slug."""
        import re
        slug = title.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug)
        return slug[:64]

    def _content_signature(self, content: str) -> str:
        """Generate a signature for content deduplication."""
        normalized = content.strip().lower()
        return hashlib.md5(normalized.encode()).hexdigest()[:16]

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
