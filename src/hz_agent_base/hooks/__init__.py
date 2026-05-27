"""Hooks package."""

from .events import HookEvent
from .schemas import (
    HookDefinition,
    CommandHookDefinition,
    HttpHookDefinition,
    PromptHookDefinition,
    AgentHookDefinition,
)
from .registry import HookRegistry
from .executor import HookExecutor, AggregatedHookResult

__all__ = [
    "HookEvent",
    "HookDefinition",
    "CommandHookDefinition",
    "HttpHookDefinition",
    "PromptHookDefinition",
    "AgentHookDefinition",
    "HookRegistry",
    "HookExecutor",
    "AggregatedHookResult",
]
