"""记忆搜索与相关性算法。

使用 token 重叠加权评分：
- 名称匹配: 3 倍权重
- 描述匹配: 2 倍权重
- 内容匹配: 1 倍权重

按查询词归一化后排序，返回 top-N 结果。

高并发优化：使用 MemoryCache 缓存记忆条目，避免每次请求都读磁盘。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .cache import MemoryCache

# 模块级全局缓存（所有调用者共享）
_global_cache: MemoryCache | None = None
_cache_lock = __import__("threading").Lock()


def get_memory_cache(max_size: int = 1000, ttl_seconds: int = 60) -> MemoryCache:
    """获取全局记忆缓存（单例）。"""
    global _global_cache
    if _global_cache is None:
        with _cache_lock:
            if _global_cache is None:
                _global_cache = MemoryCache(max_size=max_size, ttl_seconds=ttl_seconds)
    return _global_cache


@dataclass
class MemoryEntry:
    """解析后的记忆条目。"""

    path: Path
    """记忆文件路径。"""

    name: str
    """记忆名称（来自 frontmatter）。"""

    description: str
    """记忆描述（来自 frontmatter）。"""

    memory_type: str
    """记忆类型（user / feedback / project / reference）。"""

    content: str
    """记忆正文内容。"""

    score: float = 0.0
    """相关性评分。"""


def select_relevant_memories(
    query: str,
    memory_path: str | Path,
    max_results: int = 5,
    selector: Callable[[str, list[MemoryEntry]], list[MemoryEntry]] | None = None,
    cache: MemoryCache | None = None,
) -> list[MemoryEntry]:
    """根据查询选择最相关的记忆。

    Args:
        query: 搜索查询文本。
        memory_path: 记忆存储目录路径。
        max_results: 最大返回数量。
        selector: 可选的自定义选择函数，用于二次过滤。
        cache: 记忆缓存实例。None 时使用全局缓存。

    Returns:
        按相关性排序的记忆列表（过滤掉评分为 0 的）。
    """
    memory_path = Path(memory_path)
    if not memory_path.exists():
        return []

    # 使用缓存加载记忆（避免每次请求都读磁盘）
    if cache is None:
        cache = get_memory_cache()
    entries = _load_memories_cached(memory_path, cache)
    if not entries:
        return []

    # 计算相关性评分（每次重新计算，因为查询不同）
    query_tokens = _tokenize(query)
    scored = []
    for entry in entries:
        # 创建副本避免修改缓存中的对象
        scored_entry = MemoryEntry(
            path=entry.path,
            name=entry.name,
            description=entry.description,
            memory_type=entry.memory_type,
            content=entry.content,
            score=_compute_score(query_tokens, entry),
        )
        scored.append(scored_entry)

    # 按评分降序排序
    scored.sort(key=lambda e: e.score, reverse=True)

    # 应用自定义选择器
    if selector:
        scored = selector(query, scored)

    # 返回 top 结果，过滤掉评分为 0 的
    return [e for e in scored[:max_results] if e.score > 0]


def format_relevant_memories(memories: list[MemoryEntry]) -> str:
    """将记忆格式化为可注入系统提示词的文本。"""
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


def _load_memories_cached(memory_path: Path, cache: MemoryCache) -> list[MemoryEntry]:
    """从缓存或磁盘加载记忆条目。

    缓存 key 使用目录路径的 str 形式。
    缓存 value 是整个目录的记忆列表。
    """
    cache_key = f"dir:{memory_path.resolve()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # 缓存未命中，从磁盘加载
    entries = _load_memories(memory_path)
    cache.put(cache_key, entries)
    return entries


def _load_memories(memory_path: Path) -> list[MemoryEntry]:
    """从目录加载所有记忆文件。"""
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
    """解析带 YAML frontmatter 的记忆文件。

    Returns:
        (name, description, memory_type, body) 四元组。
    """
    name = ""
    description = ""
    memory_type = "general"
    body = content

    # 解析 frontmatter（--- 分隔的 YAML 块）
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            body = parts[2].strip()

            # 简单解析 YAML 字段（不引入 PyYAML 依赖）
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
    """将文本分词为小写单词集合。"""
    return set(re.findall(r"\w+", text.lower()))


def _compute_score(query_tokens: set[str], entry: MemoryEntry) -> float:
    """计算查询与记忆条目的相关性评分。

    加权策略：
    - 名称 token 重叠 × 3
    - 描述 token 重叠 × 2
    - 内容 token 重叠 × 1

    最终按查询长度归一化，避免长查询天然高分。
    """
    name_tokens = _tokenize(entry.name)
    desc_tokens = _tokenize(entry.description)
    content_tokens = _tokenize(entry.content)

    name_overlap = len(query_tokens & name_tokens) * 3
    desc_overlap = len(query_tokens & desc_tokens) * 2
    content_overlap = len(query_tokens & content_tokens)

    total = name_overlap + desc_overlap + content_overlap

    # 按查询长度归一化
    if query_tokens:
        total = total / len(query_tokens)

    return total


def invalidate_memory_cache(memory_path: str | Path) -> None:
    """使指定目录的记忆缓存失效（写入新记忆后调用）。"""
    cache = get_memory_cache()
    cache_key = f"dir:{Path(memory_path).resolve()}"
    cache.invalidate(cache_key)
