"""测试对话历史管理中间件 ConversationHistoryMiddleware。"""

import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from hz_agent_base.middleware.conversation_history import ConversationHistoryMiddleware
from hz_agent_base.conversation_history import (
    estimate_tokens,
    estimate_message_tokens,
    format_message_for_summary,
)


# ============================================================
# 辅助函数
# ============================================================

def make_mock_request(messages=None, system_prompt="You are helpful."):
    """创建一个模拟的 ModelRequest 对象。"""
    request = MagicMock()
    request.messages = messages or [HumanMessage(content="hello")]
    request.system_prompt = system_prompt

    def mock_override(**kwargs):
        new_req = MagicMock()
        new_req.messages = kwargs.get("messages", request.messages)
        new_req.system_prompt = kwargs.get("system_prompt", request.system_prompt)
        return new_req

    request.override = MagicMock(side_effect=mock_override)
    return request


def make_messages(count: int, content_prefix: str = "message") -> list:
    """创建指定数量的消息。"""
    messages = []
    for i in range(count):
        if i % 2 == 0:
            messages.append(HumanMessage(content=f"{content_prefix} {i}"))
        else:
            messages.append(AIMessage(content=f"{content_prefix} {i}"))
    return messages


def make_long_messages(count: int, content_length: int = 1000) -> list:
    """创建指定数量的长消息。"""
    messages = []
    for i in range(count):
        content = "x" * content_length
        if i % 2 == 0:
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))
    return messages


# ============================================================
# 工具函数测试
# ============================================================

class TestEstimateTokens:
    """测试 token 估算函数。"""

    def test_empty_text(self):
        assert estimate_tokens("") == 0

    def test_short_text(self):
        # 4 个字符 ≈ 1 token
        assert estimate_tokens("hello") == 1

    def test_chinese_text(self):
        # 中文字符也是按字符数估算
        text = "你好世界"  # 4 个字符
        assert estimate_tokens(text) == 1

    def test_long_text(self):
        text = "a" * 1000
        assert estimate_tokens(text) == 250  # 1000 / 4 = 250


class TestEstimateMessageTokens:
    """测试消息 token 估算函数。"""

    def test_empty_message(self):
        msg = MagicMock()
        msg.content = ""
        assert estimate_message_tokens(msg) == 0

    def test_text_message(self):
        msg = HumanMessage(content="hello world")  # 11 字符
        assert estimate_message_tokens(msg) == 2  # 11 // 4 = 2

    def test_list_content_message(self):
        msg = MagicMock()
        msg.content = ["hello", "world"]
        assert estimate_message_tokens(msg) == 2  # 10 // 4 = 2


class TestFormatMessageForSummary:
    """测试消息格式化函数。"""

    def test_human_message(self):
        msg = HumanMessage(content="你好")
        result = format_message_for_summary(msg)
        assert result == "用户: 你好"

    def test_ai_message(self):
        msg = AIMessage(content="你好")
        result = format_message_for_summary(msg)
        assert result == "Agent: 你好"

    def test_system_message(self):
        msg = SystemMessage(content="系统提示")
        result = format_message_for_summary(msg)
        assert result == "系统: 系统提示"


# ============================================================
# ConversationHistoryMiddleware 测试
# ============================================================

class TestConversationHistoryMiddleware:
    """测试对话历史管理中间件。"""

    def test_invalid_strategy_raises_error(self):
        """无效策略应抛出 ValueError。"""
        with pytest.raises(ValueError, match="Unknown strategy"):
            ConversationHistoryMiddleware(strategy="invalid")

    def test_valid_strategies(self):
        """有效策略不应抛出错误。"""
        for strategy in ("truncate", "sliding_window", "summary"):
            mw = ConversationHistoryMiddleware(strategy=strategy)
            assert mw.strategy == strategy


class TestTruncateStrategy:
    """测试截断策略。"""

    def test_no_truncation_when_under_limit(self):
        """消息数未超过限制时不应截断。"""
        mw = ConversationHistoryMiddleware(strategy="truncate", max_messages=10)
        messages = make_messages(5)
        request = make_mock_request(messages=messages)
        handler = MagicMock(return_value={"messages": []})

        mw.wrap_model_call(request, handler)

        # 检查传给 handler 的消息数
        call_args = handler.call_args[0][0]
        assert len(call_args.messages) == 5

    def test_truncation_when_over_limit(self):
        """消息数超过限制时应截断。"""
        mw = ConversationHistoryMiddleware(strategy="truncate", max_messages=3)
        messages = make_messages(10)
        request = make_mock_request(messages=messages)
        handler = MagicMock(return_value={"messages": []})

        mw.wrap_model_call(request, handler)

        call_args = handler.call_args[0][0]
        assert len(call_args.messages) == 3

    def test_keeps_recent_messages(self):
        """应保留最近的消息。"""
        mw = ConversationHistoryMiddleware(strategy="truncate", max_messages=2)
        messages = [
            HumanMessage(content="first"),
            AIMessage(content="second"),
            HumanMessage(content="third"),
            AIMessage(content="fourth"),
        ]
        request = make_mock_request(messages=messages)
        handler = MagicMock(return_value={"messages": []})

        mw.wrap_model_call(request, handler)

        call_args = handler.call_args[0][0]
        assert call_args.messages[0].content == "third"
        assert call_args.messages[1].content == "fourth"

    def test_keeps_system_message(self):
        """应保留 system message。"""
        mw = ConversationHistoryMiddleware(
            strategy="truncate", max_messages=2, keep_system=True
        )
        messages = [
            SystemMessage(content="system prompt"),
            HumanMessage(content="first"),
            AIMessage(content="second"),
            HumanMessage(content="third"),
        ]
        request = make_mock_request(messages=messages)
        handler = MagicMock(return_value={"messages": []})

        mw.wrap_model_call(request, handler)

        call_args = handler.call_args[0][0]
        assert len(call_args.messages) == 3  # system + 2 recent
        assert call_args.messages[0].content == "system prompt"

    def test_no_keep_system(self):
        """不保留 system message 时应全部截断。"""
        mw = ConversationHistoryMiddleware(
            strategy="truncate", max_messages=2, keep_system=False
        )
        messages = [
            SystemMessage(content="system prompt"),
            HumanMessage(content="first"),
            AIMessage(content="second"),
            HumanMessage(content="third"),
        ]
        request = make_mock_request(messages=messages)
        handler = MagicMock(return_value={"messages": []})

        mw.wrap_model_call(request, handler)

        call_args = handler.call_args[0][0]
        assert len(call_args.messages) == 2
        assert call_args.messages[0].content == "second"


class TestSlidingWindowStrategy:
    """测试滑动窗口策略。"""

    def test_no_trimming_when_under_limit(self):
        """token 数未超过限制时不应裁剪。"""
        mw = ConversationHistoryMiddleware(
            strategy="sliding_window", max_tokens=10000
        )
        messages = make_long_messages(5, content_length=100)
        request = make_mock_request(messages=messages)
        handler = MagicMock(return_value={"messages": []})

        mw.wrap_model_call(request, handler)

        call_args = handler.call_args[0][0]
        assert len(call_args.messages) == 5

    def test_trimming_when_over_limit(self):
        """token 数超过限制时应裁剪。"""
        mw = ConversationHistoryMiddleware(
            strategy="sliding_window", max_tokens=100
        )
        messages = make_long_messages(10, content_length=100)
        request = make_mock_request(messages=messages)
        handler = MagicMock(return_value={"messages": []})

        mw.wrap_model_call(request, handler)

        call_args = handler.call_args[0][0]
        assert len(call_args.messages) < 10

    def test_keeps_recent_messages_within_token_limit(self):
        """应保留最近的消息直到 token 限制。"""
        # 每条消息约 25 tokens (100 chars / 4)
        mw = ConversationHistoryMiddleware(
            strategy="sliding_window", max_tokens=100
        )
        messages = make_long_messages(10, content_length=100)
        request = make_mock_request(messages=messages)
        handler = MagicMock(return_value={"messages": []})

        mw.wrap_model_call(request, handler)

        call_args = handler.call_args[0][0]
        # 应该保留约 4 条消息 (100 tokens / 25 tokens per msg)
        assert 3 <= len(call_args.messages) <= 5

    def test_keeps_system_message(self):
        """应保留 system message。"""
        mw = ConversationHistoryMiddleware(
            strategy="sliding_window", max_tokens=100, keep_system=True
        )
        messages = [
            SystemMessage(content="system"),  # ~6 tokens
        ] + make_long_messages(10, content_length=100)
        request = make_mock_request(messages=messages)
        handler = MagicMock(return_value={"messages": []})

        mw.wrap_model_call(request, handler)

        call_args = handler.call_args[0][0]
        assert call_args.messages[0].content == "system"


class TestSummaryStrategy:
    """测试摘要策略。"""

    def test_no_summary_when_under_threshold(self):
        """token 数未超过阈值时不应生成摘要。"""
        mw = ConversationHistoryMiddleware(
            strategy="summary", max_tokens=10000, summary_threshold=0.8
        )
        messages = make_long_messages(5, content_length=100)
        request = make_mock_request(messages=messages)
        handler = MagicMock(return_value={"messages": []})

        mw.wrap_model_call(request, handler)

        call_args = handler.call_args[0][0]
        assert len(call_args.messages) == 5

    def test_summary_triggered_when_over_threshold(self):
        """token 数超过阈值时应触发摘要。"""
        mw = ConversationHistoryMiddleware(
            strategy="summary", max_tokens=100, summary_threshold=0.8
        )
        messages = make_long_messages(10, content_length=100)
        request = make_mock_request(messages=messages)

        # Mock 模型
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "这是摘要"
        mock_model.invoke.return_value = mock_response
        mw.model = mock_model

        handler = MagicMock(return_value={"messages": []})
        mw.wrap_model_call(request, handler)

        call_args = handler.call_args[0][0]
        # 应该有 system + summary + 最近消息
        assert len(call_args.messages) < 10
        # 检查是否包含摘要
        contents = [m.content for m in call_args.messages]
        assert any("对话历史摘要" in c for c in contents)

    def test_fallback_when_no_model(self):
        """没有模型时应降级处理。"""
        mw = ConversationHistoryMiddleware(
            strategy="summary", max_tokens=100, summary_threshold=0.8
        )
        messages = make_long_messages(10, content_length=100)
        request = make_mock_request(messages=messages)
        mw.model = None  # 确保没有模型

        handler = MagicMock(return_value={"messages": []})
        mw.wrap_model_call(request, handler)

        call_args = handler.call_args[0][0]
        # 应该有消息（降级处理）
        assert len(call_args.messages) > 0

    def test_fallback_when_model_fails(self):
        """模型调用失败时应降级处理。"""
        mw = ConversationHistoryMiddleware(
            strategy="summary", max_tokens=100, summary_threshold=0.8
        )
        messages = make_long_messages(10, content_length=100)
        request = make_mock_request(messages=messages)

        # Mock 模型抛出异常
        mock_model = MagicMock()
        mock_model.invoke.side_effect = Exception("API error")
        mw.model = mock_model

        handler = MagicMock(return_value={"messages": []})
        mw.wrap_model_call(request, handler)

        call_args = handler.call_args[0][0]
        # 应该有消息（降级处理）
        assert len(call_args.messages) > 0


# ============================================================
# 集成测试
# ============================================================

class TestIntegration:
    """集成测试。"""

    def test_create_agent_with_conversation_history(self):
        """测试 create_agent 集成。"""
        from hz_agent_base import create_agent
        from hz_agent_base.middleware.conversation_history import ConversationHistoryMiddleware

        # 这个测试只验证中间件能被正确添加，不实际调用 LLM
        agent = create_agent(
            model="deepseek-v4-flash",
            middleware=[
                ConversationHistoryMiddleware(
                    strategy="sliding_window",
                    max_tokens=16000,
                )
            ],
        )
        # 如果没有抛出异常就算成功
        assert agent is not None

    def test_priority_constant_exists(self):
        """测试优先级常量存在。"""
        from hz_agent_base.utils.constants import CONVERSATION_HISTORY
        assert CONVERSATION_HISTORY == 28

    def test_middleware_exported(self):
        """测试中间件被正确导出。"""
        from hz_agent_base.middleware import ConversationHistoryMiddleware
        assert ConversationHistoryMiddleware is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
