"""测试 Guardrails 中间件 GuardrailsMiddleware。"""

import pytest
from unittest.mock import MagicMock

from langchain_core.messages import HumanMessage, AIMessage

from hz_agent_base.middleware.guardrails import GuardrailsMiddleware
from hz_agent_base.guardrails import ContentModerator, FactChecker, OutputValidator


# ============================================================
# 辅助函数
# ============================================================

def make_mock_request(messages=None, system_prompt="You are helpful."):
    """创建一个模拟的 ModelRequest 对象。"""
    request = MagicMock()
    request.messages = messages or [HumanMessage(content="hello")]
    request.system_prompt = system_prompt
    return request


def make_mock_response(content: str):
    """创建一个模拟的响应。"""
    msg = AIMessage(content=content)
    return {"messages": [msg]}


# ============================================================
# Mock 实现
# ============================================================

class MockSafeModerator:
    """总是返回安全的审核器。"""

    def is_safe(self, content: str) -> bool:
        return True


class MockUnsafeModerator:
    """总是返回不安全的审核器。"""

    def is_safe(self, content: str) -> bool:
        return False


class MockAccurateChecker:
    """总是返回准确的事实检查器。"""

    def is_accurate(self, content: str, context) -> bool:
        return True


class MockInaccurateChecker:
    """总是返回不准确的事实检查器。"""

    def is_accurate(self, content: str, context) -> bool:
        return False


class MockValidValidator:
    """总是返回有效的格式校验器。"""

    def is_valid(self, content: str) -> bool:
        return True


class MockInvalidValidator:
    """总是返回无效的格式校验器。"""

    def is_valid(self, content: str) -> bool:
        return False


class FailingModerator:
    """总是抛出异常的审核器。"""

    def is_safe(self, content: str) -> bool:
        raise Exception("API error")


# ============================================================
# ContentModerator 协议测试
# ============================================================

class TestContentModeratorProtocol:
    """测试 ContentModerator 协议。"""

    def test_protocol_check(self):
        """检查是否符合协议。"""
        assert isinstance(MockSafeModerator(), ContentModerator)
        assert isinstance(MockUnsafeModerator(), ContentModerator)

    def test_non_protocol(self):
        """检查不符合协议的对象。"""
        class NotAModerator:
            pass
        assert not isinstance(NotAModerator(), ContentModerator)


# ============================================================
# FactChecker 协议测试
# ============================================================

class TestFactCheckerProtocol:
    """测试 FactChecker 协议。"""

    def test_protocol_check(self):
        """检查是否符合协议。"""
        assert isinstance(MockAccurateChecker(), FactChecker)
        assert isinstance(MockInaccurateChecker(), FactChecker)


# ============================================================
# OutputValidator 协议测试
# ============================================================

class TestOutputValidatorProtocol:
    """测试 OutputValidator 协议。"""

    def test_protocol_check(self):
        """检查是否符合协议。"""
        assert isinstance(MockValidValidator(), OutputValidator)
        assert isinstance(MockInvalidValidator(), OutputValidator)


# ============================================================
# GuardrailsMiddleware 测试
# ============================================================

class TestGuardrailsMiddleware:
    """测试 Guardrails 中间件。"""

    def test_no_validators_passes_through(self):
        """无校验器时直接通过。"""
        mw = GuardrailsMiddleware()
        request = make_mock_request()
        response = make_mock_response("Hello")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert result["messages"][0].content == "Hello"

    def test_content_moderator_safe(self):
        """内容审核通过。"""
        mw = GuardrailsMiddleware(content_moderator=MockSafeModerator())
        request = make_mock_request()
        response = make_mock_response("Hello")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert result["messages"][0].content == "Hello"

    def test_content_moderator_unsafe(self):
        """内容审核不通过。"""
        mw = GuardrailsMiddleware(content_moderator=MockUnsafeModerator())
        request = make_mock_request()
        response = make_mock_response("Unsafe content")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert result["messages"][0].content == "内容审核未通过，请重新组织语言。"

    def test_content_moderator_unsafe_no_block(self):
        """内容审核不通过但不阻止。"""
        mw = GuardrailsMiddleware(
            content_moderator=MockUnsafeModerator(),
            block_on_failure=False,
        )
        request = make_mock_request()
        response = make_mock_response("Unsafe content")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert result["messages"][0].content == "Unsafe content"

    def test_fact_checker_accurate(self):
        """事实检查通过。"""
        mw = GuardrailsMiddleware(fact_checker=MockAccurateChecker())
        request = make_mock_request()
        response = make_mock_response("Accurate info")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert result["messages"][0].content == "Accurate info"

    def test_fact_checker_inaccurate(self):
        """事实检查不通过。"""
        mw = GuardrailsMiddleware(fact_checker=MockInaccurateChecker())
        request = make_mock_request()
        response = make_mock_response("Inaccurate info")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert "不准确" in result["messages"][0].content

    def test_output_validator_valid(self):
        """格式校验通过。"""
        mw = GuardrailsMiddleware(output_validator=MockValidValidator())
        request = make_mock_request()
        response = make_mock_response("Valid format")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert result["messages"][0].content == "Valid format"

    def test_output_validator_invalid(self):
        """格式校验不通过。"""
        mw = GuardrailsMiddleware(output_validator=MockInvalidValidator())
        request = make_mock_request()
        response = make_mock_response("Invalid format")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert "格式" in result["messages"][0].content

    def test_custom_fallback_message(self):
        """自定义降级消息。"""
        mw = GuardrailsMiddleware(
            content_moderator=MockUnsafeModerator(),
            fallback_message="自定义错误消息",
        )
        request = make_mock_request()
        response = make_mock_response("Unsafe")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert result["messages"][0].content == "自定义错误消息"

    def test_multiple_validators(self):
        """多个校验器组合。"""
        mw = GuardrailsMiddleware(
            content_moderator=MockSafeModerator(),
            fact_checker=MockAccurateChecker(),
            output_validator=MockValidValidator(),
        )
        request = make_mock_request()
        response = make_mock_response("All good")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        assert result["messages"][0].content == "All good"

    def test_content_moderator_failure_graceful(self):
        """审核器异常时优雅降级。"""
        mw = GuardrailsMiddleware(content_moderator=FailingModerator())
        request = make_mock_request()
        response = make_mock_response("Hello")
        handler = MagicMock(return_value=response)

        result = mw.wrap_model_call(request, handler)
        # 异常时默认放行
        assert result["messages"][0].content == "Hello"


# ============================================================
# 集成测试
# ============================================================

class TestIntegration:
    """集成测试。"""

    def test_create_agent_with_guardrails(self):
        """测试 create_agent 集成。"""
        from hz_agent_base import create_agent

        agent = create_agent(
            model="deepseek-v4-flash",
            middleware=[
                GuardrailsMiddleware(content_moderator=MockSafeModerator())
            ],
        )
        assert agent is not None

    def test_priority_constant_exists(self):
        """测试优先级常量存在。"""
        from hz_agent_base.utils.constants import GUARDRAILS
        assert GUARDRAILS == 32

    def test_middleware_exported(self):
        """测试中间件被正确导出。"""
        from hz_agent_base.middleware import GuardrailsMiddleware
        assert GuardrailsMiddleware is not None

    def test_protocols_exported(self):
        """测试协议被正确导出。"""
        from hz_agent_base.guardrails import ContentModerator, FactChecker, OutputValidator
        assert ContentModerator is not None
        assert FactChecker is not None
        assert OutputValidator is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
