"""中间件包。

HZAgentBase 的中间件管道按以下顺序执行（数字越小越先执行）：

执行顺序：
    BEFORE_ALL(0)
    → PERMISSION(5)          # 权限检查
    → HUMAN_APPROVAL(8)      # Human-in-the-loop 人工审批
    → HOOKS(10)              # 生命周期事件
    → MEMORY(20)             # 记忆注入/提取
    → AGENT_MEMORY(22)       # 跨会话 Agent 记忆
    → KNOWLEDGE(25)          # 知识库 RAG 检索
    → CONVERSATION_HISTORY(28) # 对话历史管理
    → DEFAULT(30)            # 用户自定义（默认位置）
    → GUARDRAILS(32)         # Guardrails 内容审核
    → SANITIZER(33)          # 输出清洗 PII 过滤
    → REFLECTION(34)         # Agent 自我反思
    → AUDIT(35)              # 文件审计
    → RESILIENT(40)          # 重试/取消/终止
    → COORDINATOR(50)        # 多 Agent 编排
    → AFTER_ALL(100)
"""

from langchain.agents.middleware.types import AgentMiddleware

from .permission import PermissionMiddleware
from .hook import HookMiddleware
from .memory import MemoryMiddleware
from .knowledge import KnowledgeMiddleware
from .filesystem import FileAuditMiddleware
from .resilient import ResilientMiddleware
from .conversation_history import ConversationHistoryMiddleware
from .sanitizer import OutputSanitizerMiddleware
from .human_approval import HumanApprovalMiddleware
from .guardrails import GuardrailsMiddleware
from .evolution_memory import EvolutionMemoryMiddleware
from ..human_approval import ApprovalRule, ApprovalCallback
from ..guardrails import ContentModerator, FactChecker, OutputValidator
from ..utils.constants import (
    BEFORE_ALL, PERMISSION, HUMAN_APPROVAL, HOOKS,
    MEMORY, AGENT_MEMORY, KNOWLEDGE, CONVERSATION_HISTORY,
    DEFAULT, GUARDRAILS, SANITIZER, REFLECTION,
    AUDIT, RESILIENT, COORDINATOR, AFTER_ALL,
)

__all__ = [
    # 中间件类
    "AgentMiddleware",
    "PermissionMiddleware",
    "HookMiddleware",
    "MemoryMiddleware",
    "KnowledgeMiddleware",
    "FileAuditMiddleware",
    "ResilientMiddleware",
    "ConversationHistoryMiddleware",
    "OutputSanitizerMiddleware",
    "HumanApprovalMiddleware",
    "GuardrailsMiddleware",
    "EvolutionMemoryMiddleware",
    # 辅助类
    "ApprovalRule",
    "ApprovalCallback",
    "ContentModerator",
    "FactChecker",
    "OutputValidator",
    # 优先级常量
    "BEFORE_ALL", "PERMISSION", "HUMAN_APPROVAL", "HOOKS",
    "MEMORY", "AGENT_MEMORY", "KNOWLEDGE", "CONVERSATION_HISTORY",
    "DEFAULT", "GUARDRAILS", "SANITIZER", "REFLECTION",
    "AUDIT", "RESILIENT", "COORDINATOR", "AFTER_ALL",
]
