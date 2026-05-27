"""Hook middleware - executes lifecycle hooks around model calls."""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware.types import AgentMiddleware

from ..hooks.registry import HookRegistry
from ..hooks.executor import HookExecutor
from ..hooks.events import HookEvent


class HookMiddleware(AgentMiddleware):
    """Executes registered hooks at lifecycle events.

    Events:
        - USER_PROMPT_SUBMIT: When user sends a message (before model call)
        - PRE_TOOL_USE / POST_TOOL_USE: Fired during tool execution (future)
    """

    def __init__(self, registry: HookRegistry):
        self.executor = HookExecutor(registry)

    def wrap_model_call(self, request, handler) -> Any:
        """Execute hooks around model call."""
        # Extract user message for hook context
        messages = request.messages or []
        user_content = ""
        for msg in messages:
            content = getattr(msg, "content", None)
            if content and getattr(msg, "type", "") == "human":
                user_content = content if isinstance(content, str) else str(content)

        # USER_PROMPT_SUBMIT hook
        if user_content:
            result = self.executor.execute(HookEvent.USER_PROMPT_SUBMIT, {
                "prompt": user_content,
            })
            if result.blocked:
                # Return a synthetic response if hook blocks
                from langchain_core.messages import AIMessage
                return {"messages": [AIMessage(content=f"Blocked by hook: {result.reason}")]}

        # Call the model
        response = handler(request)
        return response
