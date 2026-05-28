"""记忆系统包。

提供基于文件的持久化记忆存储（Markdown + YAML frontmatter），
支持相关性搜索和从对话中自动提取记忆。

高并发改造：MemoryCache（LRU 缓存）+ FileLock（文件锁）。
"""

from .manager import MemoryManager
from .relevance import select_relevant_memories, format_relevant_memories
from .cache import MemoryCache, FileLock

__all__ = [
    "MemoryManager",
    "select_relevant_memories",
    "format_relevant_memories",
    "MemoryCache",
    "FileLock",
]
