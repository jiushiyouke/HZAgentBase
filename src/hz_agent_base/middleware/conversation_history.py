"""对话历史管理中间件 — 防止 token 超限。

支持三种策略：
- truncate: 保留最近 N 条消息
- sliding_window: 保留最近 N tokens 的消息
- summary: 旧消息压缩为摘要（调用 LLM）

使用方式：
    from hz_agent_base.middleware.conversation_history import ConversationHistoryMiddleware

    agent = create_agent(
        middleware=[ConversationHistoryMiddleware(strategy="sliding_window", max_tokens=16000)]
    )
"""

from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import HumanMessage

from ..conversation_history import (
    estimate_tokens,
    estimate_message_tokens,
    format_message_for_summary,
    SUMMARY_PROMPT,
)

logger = logging.getLogger(__name__)


class ConversationHistoryMiddleware(AgentMiddleware):
    """对话历史管理中间件。

    在模型调用前裁剪或压缩对话历史，防止 token 超限。

    Args:
        strategy: 管理策略。
            - "truncate": 保留最近 N 条消息
            - "sliding_window": 保留最近 N tokens 的消息
            - "summary": 旧消息压缩为摘要（调用 LLM）
        max_messages: truncate 策略的最大消息数，默认 50。
        max_tokens: sliding_window 和 summary 策略的最大 token 数，默认 16000。
        keep_system: 是否保留第一条 system message，默认 True。
        summary_threshold: summary 策略触发压缩的 token 阈值，默认为 max_tokens 的 80%。
        model: 用于生成摘要的模型，None 时使用当前请求的模型。
    """

    def __init__(
        self,
        strategy: str = "sliding_window",
        max_messages: int = 50,
        max_tokens: int = 16000,
        keep_system: bool = True,
        summary_threshold: float = 0.8,
        model: Any = None,
    ):
        if strategy not in ("truncate", "sliding_window", "summary"):
            raise ValueError(
                f"Unknown strategy: {strategy!r}, expected 'truncate', 'sliding_window', or 'summary'"
            )
        self.strategy = strategy
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.keep_system = keep_system
        self.summary_threshold = int(max_tokens * summary_threshold)
        self.model = model

    def wrap_model_call(self, request, handler) -> Any:
        """在模型调用前管理对话历史。"""
        messages = list(request.messages or [])
        if not messages:
            return handler(request)

        original_count = len(messages)
        original_tokens = sum(estimate_message_tokens(m) for m in messages)

        if self.strategy == "truncate":
            messages = self._truncate(messages)
        elif self.strategy == "sliding_window":
            messages = self._sliding_window(messages)
        elif self.strategy == "summary":
            messages = self._summarize(messages, request)

        # 记录裁剪情况
        new_count = len(messages)
        new_tokens = sum(estimate_message_tokens(m) for m in messages)
        if new_count < original_count or new_tokens < original_tokens:
            logger.info(
                "Conversation history managed: %d msgs (%d tokens) -> %d msgs (%d tokens) [%s]",
                original_count, original_tokens,
                new_count, new_tokens,
                self.strategy,
            )

        return handler(request.override(messages=messages))

    def _extract_system_message(self, messages: list) -> tuple[Any | None, list]:
        """分离 system message 和其他消息。"""
        if not self.keep_system or not messages:
            return None, messages

        first = messages[0]
        msg_type = getattr(first, "type", None) or getattr(first, "role", None)
        if msg_type in ("system", "SystemMessage"):
            return first, messages[1:]

        return None, messages

    def _truncate(self, messages: list) -> list:
        """截断策略：保留最近 N 条消息。"""
        if len(messages) <= self.max_messages:
            return messages

        system_msg, other_messages = self._extract_system_message(messages)
        kept = other_messages[-self.max_messages:]

        if system_msg:
            return [system_msg] + kept
        return kept

    def _sliding_window(self, messages: list) -> list:
        """滑动窗口策略：保留最近 N tokens 的消息。"""
        total_tokens = sum(estimate_message_tokens(m) for m in messages)

        if total_tokens <= self.max_tokens:
            return messages

        system_msg, other_messages = self._extract_system_message(messages)
        system_tokens = estimate_message_tokens(system_msg) if system_msg else 0

        available_tokens = self.max_tokens - system_tokens
        kept = []
        used_tokens = 0

        for msg in reversed(other_messages):
            msg_tokens = estimate_message_tokens(msg)
            if used_tokens + msg_tokens > available_tokens:
                break
            kept.append(msg)
            used_tokens += msg_tokens

        kept.reverse()

        if system_msg:
            return [system_msg] + kept
        return kept

    def _summarize(self, messages: list, request: Any) -> list:
        """摘要策略：将旧消息压缩为摘要。"""
        total_tokens = sum(estimate_message_tokens(m) for m in messages)

        # 未超过阈值，不需要压缩
        if total_tokens <= self.summary_threshold:
            return messages

        system_msg, other_messages = self._extract_system_message(messages)
        system_tokens = estimate_message_tokens(system_msg) if system_msg else 0

        # 从后往前找保留的消息（最近的 40% token 空间）
        keep_tokens = int(self.max_tokens * 0.4)
        kept = []
        used_tokens = 0

        for msg in reversed(other_messages):
            msg_tokens = estimate_message_tokens(msg)
            if used_tokens + msg_tokens > keep_tokens:
                break
            kept.append(msg)
            used_tokens += msg_tokens

        kept.reverse()

        # 需要压缩的旧消息
        old_messages = other_messages[:len(other_messages) - len(kept)]

        if not old_messages:
            if system_msg:
                return [system_msg] + kept
            return kept

        # 生成摘要
        summary = self._generate_summary(old_messages, request)

        # 组装结果：system + summary + 最近消息
        result = []
        if system_msg:
            result.append(system_msg)
        result.append(HumanMessage(content=f"[对话历史摘要]\n{summary}"))
        result.extend(kept)

        return result

    def _generate_summary(self, messages: list, request: Any) -> str:
        """调用 LLM 生成对话摘要。"""
        history_text = "\n".join(format_message_for_summary(m) for m in messages)
        prompt = SUMMARY_PROMPT.format(history=history_text)

        model = self.model
        if not model:
            logger.warning("No model available for summarization, using fallback")
            return self._fallback_summary(messages)

        try:
            response = model.invoke([HumanMessage(content=prompt)])
            summary = getattr(response, "content", "")
            if summary:
                return summary
        except Exception as e:
            logger.error("Failed to generate summary: %s", e)

        return self._fallback_summary(messages)

    def _fallback_summary(self, messages: list) -> str:
        """降级摘要：保留最后几条消息的文本。"""
        recent = messages[-3:]
        lines = []
        for msg in recent:
            lines.append(format_message_for_summary(msg))
        return "(摘要生成失败，显示最近消息)\n" + "\n".join(lines)
