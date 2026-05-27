"""后端抽象包 — 由 Deep Agents 提供。

后端决定 Agent 工具（bash、文件读写等）在哪里执行：
- StateBackend: 文件存在对话状态中，会话内隔离，关闭即丢失（推荐 Web 多用户场景）
- StoreBackend: 文件存在 LangGraph Store 中，可跨会话持久化
- ContextHubBackend: 文件存到 LangSmith Hub，适合团队共享
- CompositeBackend: 按路径前缀路由到不同后端
- LangSmithSandbox: LangSmith 云端沙箱，进程隔离

注意：FilesystemBackend 和 LocalShellBackend 未导出，因为它们直接操作宿主机文件系统，
在多用户 Web 场景下有安全风险。需要时可从 deepagents.backends 直接导入。
"""

from deepagents.backends import (
    BackendProtocol,
    StateBackend,
    StoreBackend,
    ContextHubBackend,
    CompositeBackend,
    LangSmithSandbox,
)

__all__ = [
    "BackendProtocol",
    "StateBackend",
    "StoreBackend",
    "ContextHubBackend",
    "CompositeBackend",
    "LangSmithSandbox",
]
