"""中间件包。

HZAgentBase 的中间件管道按以下顺序执行（数字越小越先执行）：
- BEFORE_ALL=0   — 用户自定义（最前面）
- PERMISSION=5   — 权限检查
- HOOKS=10       — 生命周期事件
- MEMORY=20      — 记忆注入/提取
- KNOWLEDGE=25   — 知识库 RAG 检索
- DEFAULT=30     — 用户自定义（默认位置）
- AUDIT=35       — 文件审计
- RESILIENT=40   — 重试/取消/终止
- COORDINATOR=50 — 多 Agent 编排
- AFTER_ALL=100  — 用户自定义（最后面）
"""

from langchain.agents.middleware.types import AgentMiddleware

from .permission import PermissionMiddleware
from .hook import HookMiddleware
from .memory import MemoryMiddleware
from .knowledge import KnowledgeMiddleware
from .filesystem import FileAuditMiddleware
from .resilient import ResilientMiddleware
from ..utils.constants import (
    BEFORE_ALL, PERMISSION, HOOKS, MEMORY, KNOWLEDGE,
    DEFAULT, AUDIT, RESILIENT, COORDINATOR, AFTER_ALL,
)

__all__ = [
    "AgentMiddleware",
    "PermissionMiddleware",
    "HookMiddleware",
    "MemoryMiddleware",
    "KnowledgeMiddleware",
    "FileAuditMiddleware",
    "ResilientMiddleware",
    "BEFORE_ALL", "PERMISSION", "HOOKS", "MEMORY", "KNOWLEDGE",
    "DEFAULT", "AUDIT", "RESILIENT", "COORDINATOR", "AFTER_ALL",
]
