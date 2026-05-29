"""Hook 定义数据类。

定义 4 种 Hook 类型：
- CommandHookDefinition: 执行 shell 命令
- HttpHookDefinition: 发送 HTTP POST 请求
- PromptHookDefinition: LLM 验证条件
- AgentHookDefinition: 子 Agent 深度验证
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .events import HookEvent


@dataclass
class HookDefinition:
    """Hook 基类定义。

    Attributes:
        event: 触发此 Hook 的事件类型。
        matcher: fnmatch 模式，用于匹配工具名。None 表示匹配所有。
        timeout_seconds: 最大执行时间（秒）。
        block_on_failure: Hook 执行失败时是否阻止操作。
    """

    event: HookEvent
    matcher: str | None = None
    timeout_seconds: float = 30.0
    block_on_failure: bool = False


@dataclass
class CommandHookDefinition(HookDefinition):
    """执行 shell 命令的 Hook。

    命令通过环境变量接收 Hook 上下文：
    - HZ_HOOK_EVENT: 事件名称
    - HZ_HOOK_PAYLOAD: JSON 编码的事件数据

    安全说明：
    - shell=False（默认）：命令通过 shlex.split() 拆分为参数列表，安全执行
    - shell=True：命令直接传给 shell，支持管道/重定向等，但有注入风险
    """

    command: str = ""
    """要执行的 shell 命令。"""

    shell: bool = False
    """是否使用 shell 模式执行。默认 False（安全模式）。"""


@dataclass
class HttpHookDefinition(HookDefinition):
    """发送 HTTP POST 请求的 Hook。

    安全说明：
    - allowed_hosts 为空时允许所有 host
    - 设置 allowed_hosts 后只允许白名单内的 host
    """

    url: str = ""
    """POST 请求的目标 URL。"""

    headers: dict[str, str] = field(default_factory=dict)
    """额外的 HTTP 请求头。"""

    allowed_hosts: list[str] = field(default_factory=list)
    """允许的 host 白名单。为空时不限制。"""


@dataclass
class PromptHookDefinition(HookDefinition):
    """使用 LLM 验证条件的 Hook。

    LLM 应返回 {"ok": true} 或 {"ok": false} 来决定是否放行。
    """

    prompt: str = ""
    """发送给 LLM 的验证提示词。"""


@dataclass
class AgentHookDefinition(HookDefinition):
    """使用子 Agent 进行深度验证的 Hook。"""

    agent_prompt: str = ""
    """验证子 Agent 的系统提示词。"""
