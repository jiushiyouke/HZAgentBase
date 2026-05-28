"""Hook 系统包。

提供生命周期事件钩子，支持 4 种类型：
- CommandHook: 执行 shell 命令
- HttpHook: 发送 HTTP POST 请求
- PromptHook: LLM 验证条件
- AgentHook: 子 Agent 深度验证
"""

from .events import HookEvent
from .schemas import (
    HookDefinition,
    CommandHookDefinition,
    HttpHookDefinition,
    PromptHookDefinition,
    AgentHookDefinition,
)
from .registry import HookRegistry
from .executor import HookExecutor, AggregatedHookResult, get_hook_pool, set_hook_pool

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
    "get_hook_pool",
    "set_hook_pool",
]
