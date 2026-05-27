"""记忆中间件 — 注入相关记忆到系统提示词，对话后提取新记忆。

工作流程：
1. 每次模型调用前：搜索与当前查询相关的记忆，注入到系统提示词
2. 每次模型调用后：从对话中自动提取值得记忆的信息并保存
"""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware.types import AgentMiddleware

from ..memory.manager import MemoryManager
from ..memory.relevance import select_relevant_memories, format_relevant_memories


class MemoryMiddleware(AgentMiddleware):
    """管理跨会话持久化记忆的中间件。"""

    def __init__(self, memory_path: str):
        self.manager = MemoryManager(memory_path)

    def wrap_model_call(self, request, handler) -> Any:
        """注入记忆 → 调用模型 → 提取新记忆。"""
        # 提取最新的用户消息作为搜索查询
        messages = request.messages or []
        query = ""
        for msg in messages:
            content = getattr(msg, "content", None)
            if content and getattr(msg, "type", "") == "human":
                query = content if isinstance(content, str) else str(content)

        # 搜索相关记忆并注入系统提示词
        if query:
            memories = select_relevant_memories(query, self.manager.path, max_results=5)
            if memories:
                memory_context = format_relevant_memories(memories)
                current_system = request.system_prompt or ""
                new_request = request.override(
                    system_prompt=f"{current_system}\n\n## Relevant Memories\n{memory_context}"
                )
                response = handler(new_request)
                # 对话结束后提取新记忆
                self.manager.extract_and_save(messages, response)
                return response

        # 无相关记忆时直接调用模型
        response = handler(request)

        # 对话结束后提取新记忆
        self.manager.extract_and_save(messages, response)

        return response
