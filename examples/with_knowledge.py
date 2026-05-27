"""示例：使用知识库 RAG 检索。

本示例使用 MockRetriever 演示知识库集成，无需安装 hz-knowledge-base。
实际项目中可替换为 ChromaRetriever 等真实实现。

用法:
    pip install hz-knowledge-base  # 安装独立知识库项目
    python examples/with_knowledge.py
"""

from hz_agent_base import create_agent, run_agent, Retriever, RetrievalResult


class MockRetriever:
    """模拟知识库检索器，用于演示和测试。

    实际项目中替换为：
        from hz_knowledge_base import ChromaRetriever
        retriever = ChromaRetriever("./knowledge_db")
        retriever.load_directory("./docs/")
    """

    def __init__(self, knowledge: dict[str, str] | None = None):
        # 模拟知识库内容
        self.knowledge = knowledge or {
            "Python logging": (
                "Python logging 最佳实践：\n"
                "1. 使用 logging.getLogger(__name__) 获取模块级 logger\n"
                "2. 在应用入口配置 basicConfig，不要在库中配置\n"
                "3. 使用 structured logging（JSON 格式）便于日志聚合\n"
                "4. 日志级别：DEBUG < INFO < WARNING < ERROR < CRITICAL"
            ),
            "FastAPI 部署": (
                "FastAPI 生产部署建议：\n"
                "1. 使用 uvicorn + gunicorn 多 worker 模式\n"
                "2. 配置 health check 端点\n"
                "3. 使用 middleware 处理 CORS、限流、认证\n"
                "4. 日志输出到 stdout，由容器运行时收集"
            ),
            "LangGraph 状态管理": (
                "LangGraph StateGraph 状态管理：\n"
                "1. 使用 TypedDict 定义状态结构\n"
                "2. thread_id 实现多用户状态隔离\n"
                "3. checkpoint 持久化状态到数据库\n"
                "4. 状态在节点间通过 reducer 函数合并"
            ),
        }

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        """模拟检索：基于关键词匹配返回相关文档。"""
        results = []
        query_lower = query.lower()

        for topic, content in self.knowledge.items():
            # 简单的关键词匹配打分
            score = 0.0
            for word in query_lower.split():
                if word in topic.lower() or word in content.lower():
                    score += 0.3
            score = min(score, 1.0)

            if score > 0:
                results.append(RetrievalResult(
                    content=content,
                    source=f"知识库/{topic}",
                    score=score,
                ))

        # 按分数排序，返回 top_k
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]


# 创建带知识库的 agent
retriever = MockRetriever()
agent = create_agent(
    retriever=retriever,
    knowledge_top_k=3,
)

# 运行 —— agent 会自动从知识库检索相关内容
result = run_agent(
    agent,
    "Python logging 怎么配置比较好？",
    thread_id="demo",
)

for msg in result.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"Agent: {msg.content}")
