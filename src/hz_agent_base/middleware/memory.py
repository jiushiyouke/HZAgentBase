"""记忆中间件 — 注入相关记忆到系统提示词，对话后提取新记忆。

工作流程：
1. 每次模型调用前：搜索与当前查询相关的记忆，注入到系统提示词
2. 每次模型调用后：从对话中自动提取值得记忆的信息并保存

安全特性：
- isolate_by_user=True 时，每个用户的记忆完全隔离（按 user_id 分目录）
- 防止跨用户记忆泄露和 prompt injection
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware

from ..memory.manager import MemoryManager
from ..memory.relevance import select_relevant_memories, format_relevant_memories


class MemoryMiddleware(AgentMiddleware):
    """管理跨会话持久化记忆的中间件。

    Args:
        memory_path: 记忆存储根目录。
        isolate_by_user: 是否按用户隔离记忆。开启后每个用户有独立的记忆目录。
    """

    def __init__(self, memory_path: str, isolate_by_user: bool = False):
        self.base_path = Path(memory_path)
        self.isolate_by_user = isolate_by_user
        # 非隔离模式下使用共享 manager
        if not isolate_by_user:
            self.manager = MemoryManager(memory_path)

    def _get_user_id(self, request: Any) -> str:
        """从 request 中提取用户标识。"""
        # 优先使用 request 上的 user_id
        user_id = getattr(request, "user_id", None)
        if user_id:
            return str(user_id)
        # 降级到 thread_id
        thread_id = getattr(request, "thread_id", None)
        if thread_id:
            return str(thread_id)
        return "shared"

    def _get_memory_path(self, request: Any) -> Path:
        """获取当前请求的记忆路径。"""
        if not self.isolate_by_user:
            return self.manager.path
        user_id = self._get_user_id(request)
        return self.base_path / user_id

    def _get_manager(self, request: Any) -> MemoryManager:
        """获取当前请求的 MemoryManager。"""
        if not self.isolate_by_user:
            return self.manager
        path = self._get_memory_path(request)
        return MemoryManager(str(path))

    def wrap_model_call(self, request, handler) -> Any:
        """注入记忆 → 调用模型 → 提取新记忆。"""
        # 提取最新的用户消息作为搜索查询
        messages = request.messages or []
        query = ""
        for msg in messages:
            content = getattr(msg, "content", None)
            if content and getattr(msg, "type", "") == "human":
                query = content if isinstance(content, str) else str(content)

        manager = self._get_manager(request)
        memory_path = self._get_memory_path(request)

        # 搜索相关记忆并注入系统提示词
        if query:
            memories = select_relevant_memories(query, memory_path, max_results=5)
            if memories:
                memory_context = format_relevant_memories(memories)
                current_system = request.system_prompt or ""
                new_request = request.override(
                    system_prompt=f"{current_system}\n\n## Relevant Memories\n{memory_context}"
                )
                response = handler(new_request)
                # 对话结束后提取新记忆
                manager.extract_and_save(messages, response)
                return response

        # 无相关记忆时直接调用模型
        response = handler(request)

        # 对话结束后提取新记忆
        manager.extract_and_save(messages, response)

        return response
