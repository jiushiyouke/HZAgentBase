"""Hook 中间件 — 在生命周期事件时执行已注册的钩子。

支持的事件：
- USER_PROMPT_SUBMIT: 用户提交消息时触发，Hook 可阻止后续处理
- PRE_TOOL_USE / POST_TOOL_USE: 工具执行前后触发
"""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware.types import AgentMiddleware

from ..hooks.registry import HookRegistry
from ..hooks.executor import HookExecutor
from ..hooks.events import HookEvent


class HookMiddleware(AgentMiddleware):
    """在生命周期事件时执行已注册 Hook 的中间件。

    Args:
        registry: Hook 注册表。
        model: LLM 模型实例，供 PromptHook 和 AgentHook 使用。可选。
    """

    def __init__(self, registry: HookRegistry, model: Any = None):
        self.executor = HookExecutor(registry, model=model)

    def wrap_model_call(self, request, handler) -> Any:
        """在模型调用前/后执行 Hook。"""
        # 提取用户消息用于 Hook 上下文
        messages = request.messages or []
        user_content = ""
        for msg in messages:
            content = getattr(msg, "content", None)
            if content and getattr(msg, "type", "") == "human":
                user_content = content if isinstance(content, str) else str(content)

        # 触发 USER_PROMPT_SUBMIT 事件
        if user_content:
            result = self.executor.execute(HookEvent.USER_PROMPT_SUBMIT, {
                "prompt": user_content,
            })
            if result.blocked:
                # Hook 阻止了操作，返回合成响应而不是调用模型
                from langchain_core.messages import AIMessage
                return {"messages": [AIMessage(content=f"Blocked by hook: {result.reason}")]}

        # 正常调用模型
        response = handler(request)
        return response
