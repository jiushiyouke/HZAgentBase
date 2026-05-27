"""
HZAgentBase - Reusable Agent Harness infrastructure library.

Usage:
    from hz_agent_base import create_agent

    agent = create_agent(model="claude-sonnet-4-6")
    response = agent.run("Hello, world!")
"""

from .agent import create_agent
from .permissions import PermissionSettings, PermissionMode
from .hooks import HookRegistry, HookEvent
from .middleware import AgentMiddleware

__version__ = "0.1.0"

__all__ = [
    "create_agent",
    "PermissionSettings",
    "PermissionMode",
    "HookRegistry",
    "HookEvent",
    "AgentMiddleware",
]
