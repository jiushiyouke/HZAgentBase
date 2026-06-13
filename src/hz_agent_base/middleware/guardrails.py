"""Guardrails 中间件 — 内容审核、事实检查、输出格式校验。

功能：
- 内容审核：调用审核 API 检测违规内容
- 事实检查：对比知识库验证输出
- 格式校验：验证输出是否符合预期格式

使用方式：
    from hz_agent_base.middleware.guardrails import GuardrailsMiddleware
    from hz_agent_base.guardrails import ContentModerator

    agent = create_agent(
        middleware=[
            GuardrailsMiddleware(content_moderator=my_moderator)
        ]
    )
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable, Sequence

from langchain.agents.middleware.types import AgentMiddleware

from ..guardrails import ContentModerator, FactChecker, OutputValidator

logger = logging.getLogger(__name__)


class GuardrailsMiddleware(AgentMiddleware):
    """Guardrails 中间件。

    在模型调用后验证输出内容。

    Args:
        content_moderator: 内容审核器（可选）。
        fact_checker: 事实检查器（可选）。
        output_validator: 输出校验器（可选）。
        block_on_failure: 校验失败时是否阻止输出，默认 True。
        fallback_message: 校验失败时的替代消息。
    """

    def __init__(
        self,
        content_moderator: ContentModerator | None = None,
        fact_checker: FactChecker | None = None,
        output_validator: OutputValidator | None = None,
        block_on_failure: bool = True,
        fallback_message: str = "内容审核未通过，请重新组织语言。",
    ):
        self.content_moderator = content_moderator
        self.fact_checker = fact_checker
        self.output_validator = output_validator
        self.block_on_failure = block_on_failure
        self.fallback_message = fallback_message

    def wrap_model_call(self, request, handler) -> Any:
        """调用模型后验证输出。"""
        response = handler(request)
        messages = response.get("messages", []) if isinstance(response, dict) else []

        for msg in messages:
            content = getattr(msg, "content", None)
            if not content or not isinstance(content, str):
                continue

            # 内容审核
            if self.content_moderator:
                if not self._check_content_safety(content):
                    if self.block_on_failure:
                        msg.content = self.fallback_message
                    continue

            # 事实检查
            if self.fact_checker:
                if not self._check_fact_accuracy(content, request.messages):
                    if self.block_on_failure:
                        msg.content = "检测到可能的不准确信息，请核实。"
                    continue

            # 格式校验
            if self.output_validator:
                if not self._check_output_format(content):
                    if self.block_on_failure:
                        msg.content = "输出格式不符合要求，请重新生成。"

        return response

    async def awrap_model_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """调用模型后验证输出（异步版本）。"""
        response = await handler(request)
        messages = response.get("messages", []) if isinstance(response, dict) else []

        for msg in messages:
            content = getattr(msg, "content", None)
            if not content or not isinstance(content, str):
                continue

            # 内容审核
            if self.content_moderator:
                if not self._check_content_safety(content):
                    if self.block_on_failure:
                        msg.content = self.fallback_message
                    continue

            # 事实检查
            if self.fact_checker:
                if not self._check_fact_accuracy(content, request.messages):
                    if self.block_on_failure:
                        msg.content = "检测到可能的不准确信息，请核实。"
                    continue

            # 格式校验
            if self.output_validator:
                if not self._check_output_format(content):
                    if self.block_on_failure:
                        msg.content = "输出格式不符合要求，请重新生成。"

        return response

    def _check_content_safety(self, content: str) -> bool:
        """检查内容安全性。"""
        try:
            return self.content_moderator.is_safe(content)
        except Exception as e:
            logger.error("Content moderation failed: %s", e)
            return True  # 审核失败时默认放行

    def _check_fact_accuracy(self, content: str, context: Sequence[Any]) -> bool:
        """检查事实准确性。"""
        try:
            return self.fact_checker.is_accurate(content, context)
        except Exception as e:
            logger.error("Fact checking failed: %s", e)
            return True  # 检查失败时默认放行

    def _check_output_format(self, content: str) -> bool:
        """检查输出格式。"""
        try:
            return self.output_validator.is_valid(content)
        except Exception as e:
            logger.error("Output validation failed: %s", e)
            return True  # 校验失败时默认放行
