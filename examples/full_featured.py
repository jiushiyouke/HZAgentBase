"""综合示例：HZAgentBase 全部功能演示。

本示例在一个文件中演示所有功能模块的集成：
- 权限系统（自定义工具和工作目录限制）
- Hook 系统（POST_TOOL_USE 事件记录）
- 记忆系统（跨会话持久化）
- 知识库 RAG（Mock 检索器）
- 文件审计（JSONL 持久化）
- 提示词管理（目录加载 + 共享规则）
- 自定义中间件（注入业务上下文）
- 多 Agent 编排（Coordinator + Worker）
- 多用户隔离（独立 thread_id）
- 安全后端（StateBackend，内存隔离）

用法:
    python examples/full_featured.py
"""

from hz_agent_base import (
    create_agent,
    run_agent,
    PermissionSettings,
    PermissionMode,
    HookRegistry,
    HookEvent,
    Retriever,
    RetrievalResult,
    WorkerConfig,
    AgentMiddleware,
    StateBackend,
)
from hz_agent_base.hooks import CommandHookDefinition

# ============================================================
# 1. 知识库检索器（Mock 实现，生产环境替换为 ChromaRetriever）
# ============================================================


class DemoRetriever:
    """演示用检索器，根据查询关键词返回预设文档片段。

    生产环境应使用 hz-knowledge-base 的 ChromaRetriever：
        from hz_knowledge_base import ChromaRetriever
        retriever = ChromaRetriever("./knowledge_db")
        retriever.load_directory("./docs/")
    """

    def __init__(self):
        self._docs = {
            "python": RetrievalResult(
                content="Python 是一种解释型、面向对象的高级编程语言，"
                        "具有动态语义。广泛应用于 Web 开发、数据科学、AI 等领域。",
                source="python_intro.md",
                score=0.95,
            ),
            "logging": RetrievalResult(
                content="Python logging 模块提供了灵活的日志记录框架。"
                        "支持 DEBUG / INFO / WARNING / ERROR / CRITICAL 五个级别。"
                        "通过 handlers 和 formatters 可以自定义输出格式和目的地。",
                source="logging_guide.md",
                score=0.88,
            ),
            "架构": RetrievalResult(
                content="微服务架构将应用拆分为多个小型独立服务，每个服务围绕业务能力构建，"
                        "可独立部署和扩展。通信方式包括 REST API、gRPC 和消息队列。",
                source="architecture.md",
                score=0.82,
            ),
        }

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        # 基于关键词匹配（演示用，实际应使用向量检索）
        results = []
        for keyword, doc in self._docs.items():
            if keyword.lower() in query.lower():
                results.append(doc)
        return results[:top_k]


# ============================================================
# 2. Hook 系统初始化
# ============================================================
hook_registry = HookRegistry()

# 注册 Hook：每次工具调用后记录到审计日志
hook_registry.register(CommandHookDefinition(
    event=HookEvent.POST_TOOL_USE,
    command='echo "Tool used" >> tool_usage.log',
    block_on_failure=False,
))


# ============================================================
# 3. 权限配置
# ============================================================
permissions = PermissionSettings(
    mode=PermissionMode.DEFAULT,
    allowed_tools=["read_file", "glob", "grep", "web_search"],  # 只允许读取类工具
    denied_tools=["bash"],  # 禁止执行 shell 命令（生产环境建议）
    denied_paths=["**/.env*", "**/secrets/**", "**/*.key"],  # 禁止访问敏感文件
)


# ============================================================
# 4. 自定义中间件（注入业务上下文）
# ============================================================
class BusinessContextMiddleware(AgentMiddleware):
    """注入用户画像和业务环境到每次模型调用。"""

    def __init__(self, user_info: dict):
        self.user_info = user_info

    def wrap_model_call(self, request, handler):
        # 构造业务上下文文本
        context = (
            f"\n\n## 当前用户信息\n"
            f"- 用户名: {self.user_info.get('name', '未知')}\n"
            f"- 角色: {self.user_info.get('role', '普通用户')}\n"
            f"- 环境: 生产环境\n"
        )
        # 注入到系统提示词
        enriched = (request.system_prompt or "") + context
        return handler(request.override(system_prompt=enriched))


# ============================================================
# 5. 多 Agent 编排（Worker 定义）
# ============================================================
workers = [
    WorkerConfig(
        name="researcher",
        prompt="你是研究助手，负责搜索、查找和总结信息。回答要引用来源。",
        team="analysis",
        color="green",
    ),
    WorkerConfig(
        name="writer",
        prompt="你是写作助手，负责把研究结果整理为清晰易读的文档。",
        team="analysis",
        color="blue",
    ),
]


# ============================================================
# 6. 创建 Agent（组装所有模块）
# ============================================================
agent = create_agent(
    # 模型（不传则使用 .env 中的 DEFAULT_MODEL）
    model=None,
    # 提示词
    system_prompt="你是综合助手，负责协调多个子 Agent 完成任务。",
    # 权限
    permissions=permissions,
    # Hook
    hooks=hook_registry,
    # 记忆（跨会话持久化）
    memory_path=".memory/",
    # 知识库（RAG 检索）
    retriever=DemoRetriever(),
    knowledge_top_k=3,
    # 文件审计
    filesystem=True,
    # 多 Agent 编排
    workers=workers,
    # 自定义中间件
    middleware=[BusinessContextMiddleware({
        "name": "张三",
        "role": "高级工程师",
    })],
    # 安全后端（内存隔离，不污染服务器文件系统）
    backend=StateBackend(),
)


# ============================================================
# 7. 多用户演示
# ============================================================
def simulate_multi_user():
    """模拟两个用户同时使用同一个 Agent 实例。"""
    print("=" * 60)
    print("多用户演示开始...")
    print("=" * 60)

    # 用户 A：查询知识库中的内容
    result_a = run_agent(
        agent,
        "Python 有什么特点？",
        thread_id="user-a",
        user_id="alice",
    )
    reply_a = _extract_reply(result_a)
    print(f"\n[用户 A (alice)]: Python 有什么特点？")
    print(f"[Agent]: {reply_a[:100]}...")

    # 用户 B：完全独立的上下文
    result_b = run_agent(
        agent,
        "你好，我叫 bob",
        thread_id="user-b",
        user_id="bob",
    )
    reply_b = _extract_reply(result_b)
    print(f"\n[用户 B (bob)]: 你好，我叫 bob")
    print(f"[Agent]: {reply_b[:100]}...")

    print("\n" + "=" * 60)
    print("多用户演示结束。")
    print("注意：用户 A 和 B 的对话完全隔离，互不影响。")
    print("=" * 60)


# ============================================================
# 8. 多 Agent 协作演示
# ============================================================
def simulate_multi_agent_task():
    """演示 Coordinator 协调多个 worker 完成任务。"""
    print("\n" + "=" * 60)
    print("多 Agent 协作演示开始...")
    print("=" * 60)

    result = run_agent(
        agent,
        "研究 Python logging 的最佳实践，然后写一份简短的总结",
        thread_id="coordinator-demo",
    )
    reply = _extract_reply(result)
    print(f"\n[Coordinator]: 研究 Python logging 的最佳实践，然后写一份简短的总结")
    print(f"[Agent]: {reply[:200]}...")

    print("\n" + "=" * 60)
    print("多 Agent 协作演示结束。")
    print("=" * 60)


def _extract_reply(result: dict) -> str:
    """从 Agent 响应中提取文本回复。"""
    for msg in result.get("messages", []):
        if hasattr(msg, "type") and msg.type == "ai":
            content = msg.content
            if isinstance(content, str):
                return content
            if isinstance(content, list) and content:
                return str(content[0])
    return "(无回复)"


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("HZAgentBase 全功能示例")
    print("=" * 60)
    print("已启用模块：")
    print("  1. 权限系统 — DEFAULT 模式，只允许读取类工具")
    print("  2. Hook 系统 — POST_TOOL_USE 事件记录")
    print("  3. 记忆系统 — 持久化到 .memory/")
    print("  4. 知识库 RAG — DemoRetriever")
    print("  5. 文件审计 — 写入 .audit/audit.jsonl")
    print("  6. 提示词管理 — load_prompt() 自动解析")
    print("  7. 自定义中间件 — BusinessContextMiddleware")
    print("  8. 多 Agent 编排 — Coordinator + 2 Workers")
    print("  9. 多用户隔离 — 独立 thread_id")
    print("  10. 安全后端 — StateBackend（内存隔离）")
    print("=" * 60)

    # 运行演示
    simulate_multi_user()
