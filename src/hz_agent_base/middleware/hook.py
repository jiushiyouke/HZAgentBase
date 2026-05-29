"""Hook 中间件 — 在生命周期事件时执行已注册的钩子。

支持的事件：
- SESSION_START: Agent 执行开始前触发（before_agent）
- SESSION_END: Agent 执行结束后触发（after_agent）
- USER_PROMPT_SUBMIT: 用户提交消息时触发（wrap_model_call）
- PRE_TOOL_USE: 工具执行前触发（wrap_tool_call）
- POST_TOOL_USE: 工具执行后触发（wrap_tool_call）
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

from langchain.agents.middleware.types import AgentMiddleware

from ..hooks.registry import HookRegistry
from ..hooks.executor import HookExecutor
from ..hooks.events import HookEvent


class HookMiddleware(AgentMiddleware):
    """在生命周期事件时执行已注册 Hook 的中间件。

    通过 AgentMiddleware 的生命周期方法实现全部 HookEvent 触发：
    - before_agent → SESSION_START
    - after_agent → SESSION_END
    - wrap_model_call → USER_PROMPT_SUBMIT
    - wrap_tool_call → PRE_TOOL_USE / POST_TOOL_USE

    Args:
        registry: Hook 注册表。
        model: LLM 模型实例，供 PromptHook 和 AgentHook 使用。可选。
    """

    def __init__(self, registry: HookRegistry, model: Any = None):
        self.executor = HookExecutor(registry, model=model)

    # ================================================================
    # SESSION_START / SESSION_END
    # ================================================================

    def before_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        """Agent 执行开始前触发 SESSION_START。"""
        try:
            self.executor.execute(HookEvent.SESSION_START, {
                "state_keys": list(state.keys()) if isinstance(state, dict) else [],
            })
        except Exception as e:
            logger.warning("SESSION_START hook failed: %s", e)
        return None  # 不修改状态

    def after_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        """Agent 执行结束后触发 SESSION_END。"""
        try:
            self.executor.execute(HookEvent.SESSION_END, {
                "state_keys": list(state.keys()) if isinstance(state, dict) else [],
            })
        except Exception as e:
            logger.warning("SESSION_END hook failed: %s", e)
        return None

    # ================================================================
    # USER_PROMPT_SUBMIT
    # ================================================================

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        """用户提交消息时触发 USER_PROMPT_SUBMIT。"""
        # 提取用户消息
        messages = request.messages or []
        user_content = ""
        for msg in messages:
            content = getattr(msg, "content", None)
            if content and getattr(msg, "type", "") == "human":
                user_content = content if isinstance(content, str) else str(content)

        # 触发 USER_PROMPT_SUBMIT 事件
        if user_content:
            try:
                result = self.executor.execute(HookEvent.USER_PROMPT_SUBMIT, {
                    "prompt": user_content,
                })
                if result.blocked:
                    from langchain_core.messages import AIMessage
                    return {"messages": [AIMessage(content=f"Blocked by hook: {result.reason}")]}
            except Exception as e:
                logger.warning("USER_PROMPT_SUBMIT hook failed: %s", e)

        return handler(request)

    # ================================================================
    # PRE_TOOL_USE / POST_TOOL_USE
    # ================================================================

    def wrap_tool_call(self, request: Any, handler: Any) -> Any:
        """工具执行前后触发 PRE_TOOL_USE 和 POST_TOOL_USE。

        wrap_tool_call 接收 ToolCallRequest，包含：
        - tool_call: dict（name, args, id）
        - tool: BaseTool 实例或 None
        - state: Agent 状态
        - runtime: 运行时上下文
        """
        tool_call = request.tool_call
        tool_name = tool_call.get("name", "") if isinstance(tool_call, dict) else getattr(tool_call, "name", "")
        tool_args = tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, "args", {})

        # 触发 PRE_TOOL_USE
        pre_result = self.executor.execute(
            HookEvent.PRE_TOOL_USE,
            {"tool_name": tool_name, "args": tool_args},
            tool_name=tool_name,
        )
        if pre_result.blocked:
            # Hook 阻止了工具执行，返回错误消息
            from langchain_core.messages import ToolMessage
            return ToolMessage(
                content=f"Blocked by hook: {pre_result.reason}",
                tool_call_id=tool_call.get("id", "") if isinstance(tool_call, dict) else getattr(tool_call, "id", ""),
            )

        # 正常执行工具
        response = handler(request)

        # 触发 POST_TOOL_USE
        output = ""
        if hasattr(response, "content"):
            output = str(response.content)[:500]  # 截断避免 payload 过大

        self.executor.execute(
            HookEvent.POST_TOOL_USE,
            {"tool_name": tool_name, "args": tool_args, "output": output},
            tool_name=tool_name,
        )

        return response
