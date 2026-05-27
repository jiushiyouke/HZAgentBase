"""检索协议定义 — 参考 LlamaIndex BaseRetriever 的最小接口。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class RetrievalResult:
    """单条检索结果。

    Attributes:
        content: 文档片段内容。
        source: 来源标识（文件名、URL 等）。
        score: 相关性分数，0~1，越高越相关。
    """

    content: str
    source: str = ""
    score: float = 0.0


@runtime_checkable
class Retriever(Protocol):
    """检索器协议 — 任何实现此协议的对象都可以接入 KnowledgeMiddleware。

    实现示例（独立项目中）：

        class ChromaRetriever:
            def __init__(self, persist_dir: str):
                self.client = chromadb.PersistentClient(path=persist_dir)
                self.collection = self.client.get_collection("docs")

            def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
                results = self.collection.query(query_texts=[query], n_results=top_k)
                return [
                    RetrievalResult(content=doc, source=meta.get("source", ""), score=dist)
                    for doc, meta, dist in zip(...)
                ]
    """

    def retrieve(self, query: str, top_k: int = 5) -> Sequence[RetrievalResult]:
        """根据查询文本返回相关文档片段。

        Args:
            query: 用户查询文本。
            top_k: 最多返回的结果数量。

        Returns:
            按相关性降序排列的检索结果列表。
        """
        ...
