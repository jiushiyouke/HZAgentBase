"""
HZAgentBase - Reusable Agent Harness infrastructure library.

Usage:
    from hz_agent_base import create_agent, run_agent

    # 创建 agent（全局只需一次，线程安全）
    agent = create_agent()

    # 多用户调用（通过 thread_id 隔离）
    result_user_a = run_agent(agent, "你好", thread_id="user-a-session-1")
    result_user_b = run_agent(agent, "帮我分析代码", thread_id="user-b-session-1")
"""

from .agent import create_agent, run_agent
from .permissions import PermissionSettings, PermissionMode
from .hooks import HookRegistry, HookEvent
from .middleware import AgentMiddleware
from .knowledge import Retriever, RetrievalResult
from .coordinator.worker import WorkerConfig

__version__ = "0.1.0"

__all__ = [
    "create_agent",
    "run_agent",
    "PermissionSettings",
    "PermissionMode",
    "HookRegistry",
    "HookEvent",
    "AgentMiddleware",
    "Retriever",
    "RetrievalResult",
    "WorkerConfig",
]
