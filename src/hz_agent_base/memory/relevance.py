"""Memory relevance - search and rank memories by relevance to a query."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class MemoryEntry:
    """A parsed memory entry."""

    path: Path
    name: str
    description: str
    memory_type: str
    content: str
    score: float = 0.0


def select_relevant_memories(
    query: str,
    memory_path: str | Path,
    max_results: int = 5,
    selector: Callable[[str, list[MemoryEntry]], list[MemoryEntry]] | None = None,
) -> list[MemoryEntry]:
    """Select memories relevant to a query.

    Args:
        query: The search query.
        memory_path: Path to the memory directory.
        max_results: Maximum number of results.
        selector: Optional custom selector function.

    Returns:
        List of relevant MemoryEntry objects.
    """
    memory_path = Path(memory_path)
    if not memory_path.exists():
        return []

    # Load all memories
    entries = _load_memories(memory_path)
    if not entries:
        return []

    # Score by relevance
    query_tokens = _tokenize(query)
    for entry in entries:
        entry.score = _compute_score(query_tokens, entry)

    # Sort by score descending
    entries.sort(key=lambda e: e.score, reverse=True)

    # Apply custom selector if provided
    if selector:
        entries = selector(query, entries)

    # Return top results (filter out zero-score)
    return [e for e in entries[:max_results] if e.score > 0]


def format_relevant_memories(memories: list[MemoryEntry]) -> str:
    """Format memories for injection into system prompt."""
    if not memories:
        return ""

    lines = ["The following memories may be relevant to the current context:\n"]
    for mem in memories:
        lines.append(f"### {mem.name}")
        if mem.description:
            lines.append(f"Description: {mem.description}")
        lines.append(mem.content.strip())
        lines.append("")

    return "\n".join(lines)


def _load_memories(memory_path: Path) -> list[MemoryEntry]:
    """Load all memory files from the directory."""
    entries = []
    for filepath in memory_path.glob("*.md"):
        if filepath.name == "MEMORY.md":
            continue

        content = filepath.read_text(encoding="utf-8")
        name, description, memory_type, body = _parse_memory_file(content)

        entries.append(MemoryEntry(
            path=filepath,
            name=name or filepath.stem,
            description=description,
            memory_type=memory_type,
            content=body,
        ))

    return entries


def _parse_memory_file(content: str) -> tuple[str, str, str, str]:
    """Parse a memory file with YAML frontmatter.

    Returns:
        (name, description, memory_type, body)
    """
    name = ""
    description = ""
    memory_type = "general"
    body = content

    # Check for frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            body = parts[2].strip()

            # Parse simple YAML fields
            for line in frontmatter.split("\n"):
                line = line.strip()
                if line.startswith("name:"):
                    name = line[5:].strip()
                elif line.startswith("description:"):
                    description = line[12:].strip()
                elif line.startswith("type:"):
                    memory_type = line[5:].strip()

    return name, description, memory_type, body


def _tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase words."""
    return set(re.findall(r"\w+", text.lower()))


def _compute_score(query_tokens: set[str], entry: MemoryEntry) -> float:
    """Compute relevance score between query and memory entry."""
    # Tokenize all fields
    name_tokens = _tokenize(entry.name)
    desc_tokens = _tokenize(entry.description)
    content_tokens = _tokenize(entry.content)

    # Weighted overlap scoring
    # Name matches: 3x weight
    name_overlap = len(query_tokens & name_tokens) * 3
    # Description matches: 2x weight
    desc_overlap = len(query_tokens & desc_tokens) * 2
    # Content matches: 1x weight
    content_overlap = len(query_tokens & content_tokens)

    total = name_overlap + desc_overlap + content_overlap

    # Normalize by query length to avoid bias toward longer queries
    if query_tokens:
        total = total / len(query_tokens)

    return total
