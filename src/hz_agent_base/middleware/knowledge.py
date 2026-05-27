"""Knowledge middleware — 从知识库检索相关上下文并注入系统提示词。"""

from __future__ import annotations

from typing import Any, Sequence

from langchain.agents.middleware.types import AgentMiddleware

from ..knowledge.protocol import Retriever, RetrievalResult


class KnowledgeMiddleware(AgentMiddleware):
    """在每次模型调用前，从知识库检索相关内容并注入系统提示词。

    工作流程：
    1. 提取用户最新消息作为查询
    2. 调用 retriever.retrieve() 获取相关文档片段
    3. 将片段格式化后拼接到系统提示词
    4. 调用下一个 middleware / LLM
    """

    def __init__(self, retriever: Retriever, top_k: int = 5):
        self.retriever = retriever
        self.top_k = top_k

    def wrap_model_call(self, request, handler) -> Any:
        """检索知识库并注入上下文。"""
        # 提取用户最新消息作为查询
        messages = request.messages or []
        query = ""
        for msg in messages:
            content = getattr(msg, "content", None)
            if content and getattr(msg, "type", "") == "human":
                query = content if isinstance(content, str) else str(content)

        if not query:
            return handler(request)

        # 从知识库检索
        try:
            results = self.retriever.retrieve(query, top_k=self.top_k)
        except Exception:
            # 检索失败不应阻断模型调用
            return handler(request)

        if not results:
            return handler(request)

        # 格式化检索结果
        context = _format_results(results)

        # 注入系统提示词
        current_system = request.system_prompt or ""
        new_request = request.override(
            system_prompt=f"{current_system}\n\n## Knowledge Base\n{context}"
        )
        return handler(new_request)


def _format_results(results: Sequence[RetrievalResult]) -> str:
    """将检索结果格式化为可注入系统提示词的文本。"""
    parts = ["The following information from the knowledge base may be relevant:\n"]
    for i, r in enumerate(results, 1):
        header = f"### [{i}] {r.source}" if r.source else f"### [{i}]"
        parts.append(header)
        parts.append(r.content.strip())
        parts.append("")
    return "\n".join(parts)
