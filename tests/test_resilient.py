"""测试容错机制：ResilientMiddleware、CancellationChecker、StopCondition。"""

import time
import pytest
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage, AIMessage

from hz_agent_base.middleware.resilient import ResilientMiddleware
from hz_agent_base.resilience.protocols import CancellationChecker, StopCondition


# ============================================================
# 辅助函数：模拟 ModelRequest
# ============================================================

def make_mock_request(messages=None, thread_id="test-thread-1"):
    """创建模拟的 ModelRequest 对象。"""
    request = MagicMock()
    request.messages = messages or [HumanMessage(content="hello")]
    request.thread_id = thread_id
    return request


def make_handler(returns=None, fail_count=0):
    """创建模拟的 handler。

    Args:
        returns: 成功时的返回值。
        fail_count: 前 N 次调用时抛出异常的次数。
    """
    handler = MagicMock()
    if fail_count > 0:
        # 前 fail_count 次失败，之后成功
        side_effects = [Exception(f"Simulated error {i+1}") for i in range(fail_count)]
        side_effects.append(returns or {"messages": [AIMessage(content="success")]})
        handler.side_effect = side_effects
    else:
        handler.return_value = returns or {"messages": [AIMessage(content="success")]}
    return handler


# ============================================================
# CancellationChecker 实现
# ============================================================

class InMemoryCancellationChecker:
    """基于内存的取消检查器（用于测试）。"""

    def __init__(self):
        self._cancelled: set[str] = set()

    def cancel(self, thread_id: str):
        self._cancelled.add(thread_id)

    def is_cancelled(self, thread_id: str) -> bool:
        return thread_id in self._cancelled


class BrokenCancellationChecker:
    """会抛出异常的取消检查器（测试异常处理）。"""

    def is_cancelled(self, thread_id: str) -> bool:
        raise RuntimeError("Redis 连接失败")


# ============================================================
# StopCondition 实现
# ============================================================

class MaxRoundsCondition:
    """轮次限制终止条件。"""

    def __init__(self, max_rounds: int = 3):
        self.max_rounds = max_rounds

    def should_stop(self, messages: list) -> bool:
        ai_count = sum(1 for m in messages if getattr(m, "type", "") == "ai")
        return ai_count >= self.max_rounds


class AlwaysStopCondition:
    """始终终止的条件（用于测试）。"""

    def should_stop(self, messages: list) -> bool:
        return True


class NeverStopCondition:
    """永远不会终止的条件。"""

    def should_stop(self, messages: list) -> bool:
        return False


class BrokenStopCondition:
    """会抛出异常的终止条件（测试异常处理）。"""

    def should_stop(self, messages: list) -> bool:
        raise RuntimeError("规则引擎不可用")


# ============================================================
# 基础测试
# ============================================================

class TestResilientMiddlewareBasic:
    """测试容错中间件基础功能。"""

    def test_passes_through_with_no_options(self):
        """无任何配置时应直接调用 handler 并返回结果。"""
        middleware = ResilientMiddleware()
        request = make_mock_request()
        handler = make_handler()

        result = middleware.wrap_model_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == {"messages": [AIMessage(content="success")]}

    def test_zero_retries_calls_handler_once(self):
        """max_retries=0 时失败不重试，直接返回错误。"""
        middleware = ResilientMiddleware(max_retries=0)
        request = make_mock_request()
        handler = make_handler(fail_count=1)

        result = middleware.wrap_model_call(request, handler)

        # 只调用一次，不重试
        assert handler.call_count == 1
        # 返回错误消息
        assert "模型暂时不可用" in result["messages"][0].content


class TestCancellationChecker:
    """测试取消检查功能。"""

    def test_cancelled_request_returns_cancellation_message(self):
        """已取消的请求应返回取消消息，不调用 handler。"""
        checker = InMemoryCancellationChecker()
        checker.cancel("test-thread-1")

        middleware = ResilientMiddleware(cancellation_checker=checker)
        request = make_mock_request(thread_id="test-thread-1")
        handler = make_handler()

        result = middleware.wrap_model_call(request, handler)

        # handler 不应被调用
        handler.assert_not_called()
        assert "请求已被取消" in result["messages"][0].content

    def test_non_cancelled_request_proceeds(self):
        """未取消的请求应正常执行。"""
        checker = InMemoryCancellationChecker()

        middleware = ResilientMiddleware(cancellation_checker=checker)
        request = make_mock_request(thread_id="test-thread-1")
        handler = make_handler()

        result = middleware.wrap_model_call(request, handler)

        handler.assert_called_once_with(request)
        assert result["messages"][0].content == "success"

    def test_cancellation_checker_exception_does_not_crash(self):
        """取消检查异常不应崩溃，应继续正常执行。"""
        checker = BrokenCancellationChecker()

        middleware = ResilientMiddleware(cancellation_checker=checker)
        request = make_mock_request(thread_id="test-thread-1")
        handler = make_handler()

        result = middleware.wrap_model_call(request, handler)

        # 异常被捕获，正常继续
        handler.assert_called_once()
        assert result["messages"][0].content == "success"

    def test_empty_thread_id_skips_cancellation_check(self):
        """thread_id 为空时应跳过取消检查。"""
        checker = InMemoryCancellationChecker()
        checker.cancel("")  # 取消空 thread_id

        middleware = ResilientMiddleware(cancellation_checker=checker)
        request = make_mock_request(thread_id="")  # 空 thread_id
        handler = make_handler()

        result = middleware.wrap_model_call(request, handler)

        # 空 thread_id 跳过取消检查，正常执行
        handler.assert_called_once()
        assert result["messages"][0].content == "success"


class TestStopCondition:
    """测试终止条件功能。"""

    def test_pre_call_stop_returns_stop_message(self):
        """调用前满足终止条件应返回终止消息，不调用 handler。"""
        condition = AlwaysStopCondition()

        middleware = ResilientMiddleware(stop_condition=condition)
        request = make_mock_request()
        handler = make_handler()

        result = middleware.wrap_model_call(request, handler)

        handler.assert_not_called()
        assert "已满足终止条件" in result["messages"][0].content

    def test_pre_call_not_stop_proceeds(self):
        """调用前不满足终止条件应正常执行。"""
        condition = NeverStopCondition()

        middleware = ResilientMiddleware(stop_condition=condition)
        request = make_mock_request()
        handler = make_handler()

        result = middleware.wrap_model_call(request, handler)

        handler.assert_called_once()
        assert result["messages"][0].content == "success"

    def test_post_call_stop_returns_result(self):
        """调用后满足终止条件——正常返回结果，不抛异常。"""
        # 只有 AI 消息才触发停止，调用前只有 HumanMessage 不会停止
        class StopWhenAIExists:
            def should_stop(self, messages: list) -> bool:
                return any(getattr(m, "type", "") == "ai" for m in messages)

        condition = StopWhenAIExists()

        middleware = ResilientMiddleware(stop_condition=condition)
        request = make_mock_request()
        handler = make_handler()

        # 调用前只有 HumanMessage，不停止 → handler 被调用
        # handler 返回 {"messages": [AIMessage(...)]} → 调用后检查 → 有 AI，但不抛异常
        result = middleware.wrap_model_call(request, handler)

        handler.assert_called_once()
        assert result == {"messages": [AIMessage(content="success")]}

    def test_stop_condition_exception_does_not_crash(self):
        """终止条件检查异常不应崩溃，应继续正常执行。"""
        condition = BrokenStopCondition()

        middleware = ResilientMiddleware(stop_condition=condition)
        request = make_mock_request()
        handler = make_handler()

        result = middleware.wrap_model_call(request, handler)

        # 异常被捕获，正常继续
        handler.assert_called_once()
        assert result["messages"][0].content == "success"

    def test_max_rounds_condition(self):
        """测试轮次限制条件的具体逻辑。"""
        condition = MaxRoundsCondition(max_rounds=2)

        # 1 条 AI 消息 → 不停止
        messages1 = [HumanMessage("hi"), AIMessage("hello")]
        assert condition.should_stop(messages1) is False

        # 2 条 AI 消息 → 停止
        messages2 = [HumanMessage("hi"), AIMessage("a"), AIMessage("b")]
        assert condition.should_stop(messages2) is True


class TestRetry:
    """测试重试功能。"""

    def test_successful_call_no_retry(self):
        """成功调用不应触发重试。"""
        middleware = ResilientMiddleware(max_retries=2)
        request = make_mock_request()
        handler = make_handler()

        result = middleware.wrap_model_call(request, handler)

        assert handler.call_count == 1
        assert result["messages"][0].content == "success"

    def test_retry_on_failure_then_success(self):
        """第一次失败后重试，第二次成功。"""
        middleware = ResilientMiddleware(max_retries=2)
        request = make_mock_request()
        handler = make_handler(fail_count=1)  # 第 1 次失败，第 2 次成功

        with patch("time.sleep") as mock_sleep:
            result = middleware.wrap_model_call(request, handler)

        # 调用了 2 次（1 次失败 + 1 次成功）
        assert handler.call_count == 2
        assert result["messages"][0].content == "success"
        # 验证退避延迟：attempt 0 → delay = 1.0 * 2^0 = 1.0
        mock_sleep.assert_called_once_with(1.0)

    def test_all_retries_exhausted(self):
        """全部重试失败后返回友好错误消息。"""
        middleware = ResilientMiddleware(max_retries=2)
        request = make_mock_request()
        handler = make_handler(fail_count=3)  # 3 次全部失败

        with patch("time.sleep"):
            result = middleware.wrap_model_call(request, handler)

        # 调用了 3 次（max_retries + 1）
        assert handler.call_count == 3
        assert "模型暂时不可用" in result["messages"][0].content
        assert "已重试 2 次" in result["messages"][0].content

    def test_exponential_backoff_timing(self):
        """验证指数退避延迟时间。"""
        middleware = ResilientMiddleware(max_retries=3, retry_base_delay=1.0)
        request = make_mock_request()
        handler = make_handler(fail_count=3)

        with patch("time.sleep") as mock_sleep:
            middleware.wrap_model_call(request, handler)

        # attempt 0: delay = 1.0, attempt 1: delay = 2.0, attempt 2: delay = 4.0
        expected_delays = [1.0, 2.0, 4.0]
        actual_delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert actual_delays == expected_delays

    def test_custom_retry_count(self):
        """自定义重试次数生效。"""
        middleware = ResilientMiddleware(max_retries=5)
        request = make_mock_request()
        handler = make_handler(fail_count=6)  # 全部失败

        with patch("time.sleep"):
            result = middleware.wrap_model_call(request, handler)

        # max_retries=5 → 6 次调用（1 次原始 + 5 次重试）
        assert handler.call_count == 6
        assert "已重试 5 次" in result["messages"][0].content


class TestCombinedResilience:
    """测试多个容错机制组合。"""

    def test_cancellation_takes_priority_over_retry(self):
        """取消检查优先于重试，已取消则不调用 handler。"""
        checker = InMemoryCancellationChecker()
        checker.cancel("test-thread-1")

        middleware = ResilientMiddleware(
            cancellation_checker=checker,
            max_retries=3,
        )
        request = make_mock_request(thread_id="test-thread-1")
        handler = make_handler(fail_count=1)

        result = middleware.wrap_model_call(request, handler)

        handler.assert_not_called()
        assert "请求已被取消" in result["messages"][0].content

    def test_stop_before_call_takes_priority_over_retry(self):
        """终止条件（调用前）优先于重试。"""
        condition = AlwaysStopCondition()

        middleware = ResilientMiddleware(
            stop_condition=condition,
            max_retries=3,
        )
        request = make_mock_request()
        handler = make_handler(fail_count=0)

        result = middleware.wrap_model_call(request, handler)

        handler.assert_not_called()
        assert "已满足终止条件" in result["messages"][0].content

    def test_cancellation_and_stop_together(self):
        """同时配置取消检查和终止条件。"""
        checker = InMemoryCancellationChecker()
        # 不取消任何请求
        condition = NeverStopCondition()

        middleware = ResilientMiddleware(
            cancellation_checker=checker,
            stop_condition=condition,
            max_retries=1,
        )
        request = make_mock_request(thread_id="test-thread-1")
        handler = make_handler()

        result = middleware.wrap_model_call(request, handler)

        handler.assert_called_once()
        assert result["messages"][0].content == "success"

    def test_retry_with_stop_condition_mid_retry(self):
        """重试时每次都会检查终止条件（调用前）。"""
        condition = NeverStopCondition()

        middleware = ResilientMiddleware(
            stop_condition=condition,
            max_retries=2,
        )
        request = make_mock_request()
        handler = make_handler(fail_count=2)

        with patch("time.sleep"):
            result = middleware.wrap_model_call(request, handler)

        # 3 次调用：每次调用前都会检查 stop_condition
        assert handler.call_count == 3
        assert result["messages"][0].content == "success"


class TestResilientInCreateAgent:
    """测试 create_agent 集成容错机制。"""

    def test_create_agent_includes_resilient_middleware(self):
        """create_agent 应自动包含 ResilientMiddleware。"""
        from hz_agent_base.agent import create_agent
        from unittest.mock import patch

        with patch("hz_agent_base.agent.create_deep_agent") as mock_create:
            mock_create.return_value = MagicMock()
            create_agent()

            # 获取传给 create_deep_agent 的 middleware 列表
            middleware_list = mock_create.call_args[1]["middleware"]
            # 检查包含 ResilientMiddleware
            from hz_agent_base.middleware.resilient import ResilientMiddleware
            resilient = [m for m in middleware_list if isinstance(m, ResilientMiddleware)]
            assert len(resilient) == 1

    def test_max_retries_passed_to_middleware(self):
        """max_retries 参数应传递给 ResilientMiddleware。"""
        from hz_agent_base.agent import create_agent
        from unittest.mock import patch

        with patch("hz_agent_base.agent.create_deep_agent") as mock_create:
            mock_create.return_value = MagicMock()
            create_agent(max_retries=5)

            middleware_list = mock_create.call_args[1]["middleware"]
            from hz_agent_base.middleware.resilient import ResilientMiddleware
            resilient = [m for m in middleware_list if isinstance(m, ResilientMiddleware)]
            assert resilient[0].max_retries == 5

    def test_no_resilient_when_max_retries_zero_and_no_checkers(self):
        """没有取消/终止检查且 max_retries=0 时不应添加 ResilientMiddleware。"""
        from hz_agent_base.agent import create_agent
        from unittest.mock import patch

        with patch("hz_agent_base.agent.create_deep_agent") as mock_create:
            mock_create.return_value = MagicMock()
            create_agent(max_retries=0)

            middleware_list = mock_create.call_args[1]["middleware"]
            from hz_agent_base.middleware.resilient import ResilientMiddleware
            resilient = [m for m in middleware_list if isinstance(m, ResilientMiddleware)]
            assert len(resilient) == 0


class TestProtocolCompliance:
    """测试协议兼容性（duck typing）。"""

    def test_any_object_with_is_cancelled_is_valid_checker(self):
        """任何实现 is_cancelled 方法的对象都可以作为 CancellationChecker。"""
        # Python duck typing — 不需要显式继承 Protocol
        checker = InMemoryCancellationChecker()
        middleware = ResilientMiddleware(cancellation_checker=checker)
        request = make_mock_request(thread_id="test-thread-1")

        handler = make_handler()
        middleware.wrap_model_call(request, handler)
        handler.assert_called_once()

    def test_any_object_with_should_stop_is_valid_condition(self):
        """任何实现 should_stop 方法的对象都可以作为 StopCondition。"""
        # Python duck typing — 不需要显式继承 Protocol
        condition = MaxRoundsCondition(max_rounds=10)
        middleware = ResilientMiddleware(stop_condition=condition)
        request = make_mock_request(
            messages=[HumanMessage("hi"), AIMessage("a")]
        )

        handler = make_handler()
        middleware.wrap_model_call(request, handler)
        handler.assert_called_once()
