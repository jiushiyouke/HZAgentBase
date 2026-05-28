"""中间件包。

HZAgentBase 的中间件管道按以下顺序执行：
1. PermissionMiddleware — 权限检查
2. HookMiddleware — 生命周期事件
3. MemoryMiddleware — 记忆注入/提取
4. KnowledgeMiddleware — 知识库 RAG 检索
5. FileAuditMiddleware — 文件审计
6. [用户自定义 Middleware]
7. CoordinatorMiddleware — 多 Agent 编排
"""

from langchain.agents.middleware.types import AgentMiddleware

from .permission import PermissionMiddleware
from .hook import HookMiddleware
from .memory import MemoryMiddleware
from .knowledge import KnowledgeMiddleware
from .filesystem import FileAuditMiddleware

__all__ = [
    "AgentMiddleware",
    "PermissionMiddleware",
    "HookMiddleware",
    "MemoryMiddleware",
    "KnowledgeMiddleware",
    "FileAuditMiddleware",
]
