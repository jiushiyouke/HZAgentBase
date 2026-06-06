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
- 对话历史管理（防止 token 超限）
- 输出清洗（PII 过滤、敏感词）
- Human-in-the-loop（危险操作需确认）
- Guardrails（内容审核、格式校验）
- 进化记忆（从任务中学习，持续进化）

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
from hz_agent_base.middleware.conversation_history import ConversationHistoryMiddleware
from hz_agent_base.middleware.sanitizer import OutputSanitizerMiddleware
from hz_agent_base.middleware.human_approval import HumanApprovalMiddleware
from hz_agent_base.human_approval import ApprovalRule
from hz_agent_base.middleware.guardrails import GuardrailsMiddleware
from hz_agent_base.middleware.evolution_memory import EvolutionMemoryMiddleware


# ============================================================
# 1. 知识库检索器（Mock 实现，生产环境替换为 ChromaRetriever）
# ============================================================


class DemoRetriever:
    """演示用检索器，根据查询关键词返回预设文档片段。"""

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
                        "支持 DEBUG / INFO / WARNING / ERROR / CRITICAL 五个级别。",
                source="logging_guide.md",
                score=0.88,
            ),
        }

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        results = []
        for keyword, doc in self._docs.items():
            if keyword.lower() in query.lower():
                results.append(doc)
        return results[:top_k]


# ============================================================
# 2. 内容审核器（Mock 实现）
# ============================================================

class DemoContentModerator:
    """演示用内容审核器。"""

    BLOCKED_WORDS = ["密码", "秘密", "内部"]

    def is_safe(self, content: str) -> bool:
        for word in self.BLOCKED_WORDS:
            if word in content:
                return False
        return True


# ============================================================
# 3. 输出格式校验器（Mock 实现）
# ============================================================

class DemoOutputValidator:
    """演示用输出校验器。"""

    def is_valid(self, content: str) -> bool:
        # 简单检查：回答不能太短
        return len(content) > 20


# ============================================================
# 4. Hook 系统初始化
# ============================================================
hook_registry = HookRegistry()

hook_registry.register(CommandHookDefinition(
    event=HookEvent.POST_TOOL_USE,
    command='echo "Tool used" >> tool_usage.log',
    block_on_failure=False,
))


# ============================================================
# 5. 权限配置
# ============================================================
permissions = PermissionSettings(
    mode=PermissionMode.DEFAULT,
    allowed_tools=["read_file", "glob", "grep", "web_search"],
    denied_tools=["bash"],
    denied_paths=["**/.env*", "**/secrets/**", "**/*.key"],
)


# ============================================================
# 6. 自定义中间件（注入业务上下文）
# ============================================================
class BusinessContextMiddleware(AgentMiddleware):
    """注入用户画像和业务环境到每次模型调用。"""

    def __init__(self, user_info: dict):
        self.user_info = user_info

    def wrap_model_call(self, request, handler):
        context = (
            f"\n\n## 当前用户信息\n"
            f"- 用户名: {self.user_info.get('name', '未知')}\n"
            f"- 角色: {self.user_info.get('role', '普通用户')}\n"
        )
        enriched = (request.system_prompt or "") + context
        return handler(request.override(system_prompt=enriched))


# ============================================================
# 7. 多 Agent 编排（Worker 定义）
# ============================================================
workers = [
    WorkerConfig(
        name="researcher",
        prompt="你是研究助手，负责搜索、查找和总结信息。",
        team="analysis",
    ),
    WorkerConfig(
        name="writer",
        prompt="你是写作助手，负责把研究结果整理为清晰易读的文档。",
        team="analysis",
    ),
]


# ============================================================
# 8. 创建 Agent（组装所有模块）
# ============================================================
agent = create_agent(
    # 模型
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
    # 中间件管道
    middleware=[
        # 1. 对话历史管理（防止 token 超限）
        ConversationHistoryMiddleware(
            strategy="sliding_window",
            max_tokens=16000,
        ),
        # 2. 输出清洗（PII 过滤、敏感词）
        OutputSanitizerMiddleware(
            mask_pii=True,
            sensitive_words=["密码", "秘密"],
        ),
        # 3. Human-in-the-loop（危险操作需确认）
        HumanApprovalMiddleware(
            rules=[
                ApprovalRule(
                    tools=["bash", "delete_file"],
                    description="危险操作需确认",
                ),
            ],
        ),
        # 4. Guardrails（内容审核、格式校验）
        GuardrailsMiddleware(
            content_moderator=DemoContentModerator(),
            output_validator=DemoOutputValidator(),
            block_on_failure=True,
        ),
        # 5. 进化记忆（从任务中学习，持续进化）
        EvolutionMemoryMiddleware(
            memory_path=".evolution_memory/",
            max_attempts=2,
            quality_threshold=0.7,
            auto_classify=True,
            auto_evaluate=True,
            inject_experience=True,
        ),
        # 6. 自定义中间件
        BusinessContextMiddleware({
            "name": "张三",
            "role": "高级工程师",
        }),
    ],
    # 安全后端
    backend=StateBackend(),
)


# ============================================================
# 9. 演示函数
# ============================================================

def _extract_reply(result: dict) -> str:
    """从 Agent 响应中提取文本回复。"""
    for msg in result.get("messages", []):
        if hasattr(msg, "type") and msg.type == "ai":
            content = msg.content
            if isinstance(content, str):
                return content
    return "(无回复)"


def demo_basic():
    """基础演示。"""
    print("\n" + "=" * 60)
    print("基础演示")
    print("=" * 60)

    result = run_agent(agent, "你好", thread_id="demo-basic")
    reply = _extract_reply(result)
    print(f"[用户]: 你好")
    print(f"[Agent]: {reply[:100]}...")


def demo_multi_user():
    """多用户演示。"""
    print("\n" + "=" * 60)
    print("多用户演示")
    print("=" * 60)

    result_a = run_agent(agent, "Python 有什么特点？", thread_id="user-a")
    print(f"\n[用户 A]: Python 有什么特点？")
    print(f"[Agent]: {_extract_reply(result_a)[:100]}...")

    result_b = run_agent(agent, "你好，我叫 bob", thread_id="user-b")
    print(f"\n[用户 B]: 你好，我叫 bob")
    print(f"[Agent]: {_extract_reply(result_b)[:100]}...")

    print("\n注意：用户 A 和 B 的对话完全隔离。")


def demo_multi_agent():
    """多 Agent 协作演示。"""
    print("\n" + "=" * 60)
    print("多 Agent 协作演示")
    print("=" * 60)

    result = run_agent(
        agent,
        "研究 Python logging 的最佳实践，然后写一份简短的总结",
        thread_id="coordinator-demo",
    )
    print(f"[Coordinator]: 研究 Python logging 的最佳实践")
    print(f"[Agent]: {_extract_reply(result)[:200]}...")


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("HZAgentBase 全功能示例")
    print("=" * 60)
    print("已启用模块：")
    print("  1.  权限系统 — DEFAULT 模式")
    print("  2.  Hook 系统 — POST_TOOL_USE 事件记录")
    print("  3.  记忆系统 — 持久化到 .memory/")
    print("  4.  知识库 RAG — DemoRetriever")
    print("  5.  文件审计 — JSONL 持久化")
    print("  6.  多 Agent 编排 — Coordinator + 2 Workers")
    print("  7.  对话历史管理 — sliding_window, 16K tokens")
    print("  8.  输出清洗 — PII 过滤 + 敏感词")
    print("  9.  Human-in-the-loop — 危险操作需确认")
    print("  10. Guardrails — 内容审核 + 格式校验")
    print("  11. 进化记忆 — 从任务中学习，持续进化")
    print("  12. 自定义中间件 — 业务上下文注入")
    print("=" * 60)

    demo_basic()
    demo_multi_user()
    demo_multi_agent()
