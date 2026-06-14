"""测试 agent 创建和运行（mock 模式，不调用真实 API）。"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from hz_agent_base.agent import (
    _get_model, create_agent, run_agent, arun_agent,
    run_agent_stream, arun_agent_stream,
)
from hz_agent_base.permissions.settings import PermissionSettings


class TestGetModel:
    """测试 _get_model 模型解析函数。"""

    def test_returns_model_instance_as_is(self):
        """传入已有模型实例时应原样返回。"""
        mock_model = MagicMock()
        mock_model.invoke = MagicMock()
        result = _get_model(mock_model)
        assert result is mock_model

    def test_returns_default_when_none(self):
        """传入 None 时应返回默认模型（使用 ChatDeepSeek）。"""
        with patch("langchain_deepseek.ChatDeepSeek") as mock_cls:
            mock_cls.return_value = MagicMock()
            _get_model(None)
            # 应该用默认模型名创建
            mock_cls.assert_called()

    def test_deepseek_model_uses_base_url(self):
        """deepseek 模型应使用 ChatDeepSeek 和专用 base_url。"""
        with patch("langchain_deepseek.ChatDeepSeek") as mock_cls:
            mock_cls.return_value = MagicMock()
            _get_model("deepseek-v4-flash")
            call_kwargs = mock_cls.call_args[1]
            assert "deepseek" in call_kwargs.get("base_url", "").lower()
            assert call_kwargs.get("model") == "deepseek-v4-flash"

    def test_non_deepseek_model_uses_openai_url(self):
        """gpt-* 模型应使用 OPENAI_BASE_URL。"""
        with patch("hz_agent_base.agent.ChatOpenAI") as mock_cls, \
             patch("hz_agent_base.agent.MODEL_BASE_URL", ""):
            mock_cls.return_value = MagicMock()
            _get_model("gpt-4")
            call_kwargs = mock_cls.call_args[1]
            assert "base_url" in call_kwargs
            assert "openai" in call_kwargs["base_url"]


class TestCreateAgent:
    """测试 create_agent 函数。"""

    @patch("hz_agent_base.agent.create_deep_agent")
    @patch("hz_agent_base.agent._get_model")
    def test_creates_agent_with_default_settings(self, mock_get_model, mock_create):
        """默认设置应能创建 agent。"""
        mock_get_model.return_value = MagicMock()
        mock_create.return_value = MagicMock()

        agent = create_agent()

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        # 应包含权限中间件
        assert "middleware" in call_kwargs
        assert len(call_kwargs["middleware"]) >= 1

    @patch("hz_agent_base.agent.create_deep_agent")
    @patch("hz_agent_base.agent._get_model")
    def test_creates_agent_with_custom_permissions(self, mock_get_model, mock_create):
        """自定义权限应传递到中间件。"""
        mock_get_model.return_value = MagicMock()
        mock_create.return_value = MagicMock()

        settings = PermissionSettings(denied_tools=["eval"])
        create_agent(permissions=settings)

        call_kwargs = mock_create.call_args[1]
        middleware = call_kwargs["middleware"]
        # 第一个中间件应是 PermissionMiddleware
        assert len(middleware) >= 1

    @patch("hz_agent_base.agent.create_deep_agent")
    @patch("hz_agent_base.agent._get_model")
    def test_creates_agent_with_custom_model(self, mock_get_model, mock_create):
        """自定义模型应传递给 _get_model。"""
        mock_get_model.return_value = MagicMock()
        mock_create.return_value = MagicMock()

        create_agent(model="deepseek-v4-flash")

        mock_get_model.assert_called_once_with("deepseek-v4-flash", api_key=None, base_url=None, model_kwargs=None)

    @patch("hz_agent_base.agent.create_deep_agent")
    @patch("hz_agent_base.agent._get_model")
    def test_creates_agent_with_system_prompt(self, mock_get_model, mock_create):
        """系统提示词应传递给 create_deep_agent。"""
        mock_get_model.return_value = MagicMock()
        mock_create.return_value = MagicMock()

        create_agent(system_prompt="You are a coder.")

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["system_prompt"] == "You are a coder."

    @patch("hz_agent_base.agent.create_deep_agent")
    @patch("hz_agent_base.agent._get_model")
    def test_passes_tools_to_deep_agent(self, mock_get_model, mock_create):
        """工具列表应传递给 create_deep_agent。"""
        mock_get_model.return_value = MagicMock()
        mock_create.return_value = MagicMock()

        tools = [MagicMock(), MagicMock()]
        create_agent(tools=tools)

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["tools"] is tools

    @patch("hz_agent_base.agent.create_deep_agent")
    @patch("hz_agent_base.agent._get_model")
    def test_middleware_priority_sorting(self, mock_get_model, mock_create):
        """中间件应按优先级排序。"""
        from hz_agent_base.utils.constants import BEFORE_ALL, AFTER_ALL

        mock_get_model.return_value = MagicMock()
        mock_create.return_value = MagicMock()

        mw_first = MagicMock(name="First")
        mw_last = MagicMock(name="Last")

        create_agent(middleware=[
            (mw_last, AFTER_ALL),
            (mw_first, BEFORE_ALL),
        ])

        call_kwargs = mock_create.call_args[1]
        middleware = call_kwargs["middleware"]
        # BEFORE_ALL 的中间件应排在最前面（Permission 之前）
        assert middleware[0] is mw_first
        # AFTER_ALL 的中间件应排在最后面
        assert middleware[-1] is mw_last


class TestRunAgent:
    """测试 run_agent 函数。"""

    def test_raises_on_none_agent(self):
        """agent 为 None 时应抛 ValueError。"""
        with pytest.raises(ValueError, match="agent must not be None"):
            run_agent(None, "hello")

    def test_raises_on_empty_message(self):
        """message 为空时应抛 ValueError。"""
        with pytest.raises(ValueError, match="message must be a non-empty string"):
            run_agent(MagicMock(), "")

    def test_raises_on_none_message(self):
        """message 为 None 时应抛 ValueError。"""
        with pytest.raises(ValueError, match="message must be a non-empty string"):
            run_agent(MagicMock(), None)

    def test_calls_invoke_with_correct_args(self):
        """应调用 agent.invoke 并传入正确的参数。"""
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": []}

        result = run_agent(mock_agent, "hello", thread_id="test-thread", user_id="test-user")

        mock_agent.invoke.assert_called_once()
        call_args = mock_agent.invoke.call_args
        # 检查 input_state
        input_state = call_args[0][0]
        assert input_state["messages"][0]["content"] == "hello"
        # 检查 config
        config = call_args[1]["config"]
        assert config["configurable"]["thread_id"] == "test-thread"
        assert config["configurable"]["user_id"] == "test-user"

    def test_auto_generates_thread_id(self):
        """不传 thread_id 时应自动生成。"""
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": []}

        run_agent(mock_agent, "hello")

        call_args = mock_agent.invoke.call_args
        config = call_args[1]["config"]
        assert config["configurable"]["thread_id"]  # 非空


class TestArunAgent:
    """测试 arun_agent 异步函数。"""

    @pytest.mark.asyncio
    async def test_raises_on_none_agent(self):
        """agent 为 None 时应抛 ValueError。"""
        with pytest.raises(ValueError, match="agent must not be None"):
            await arun_agent(None, "hello")

    @pytest.mark.asyncio
    async def test_raises_on_empty_message(self):
        """message 为空时应抛 ValueError。"""
        with pytest.raises(ValueError, match="message must be a non-empty string"):
            await arun_agent(MagicMock(), "")

    @pytest.mark.asyncio
    async def test_calls_ainvoke(self):
        """应调用 agent.ainvoke。"""
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={"messages": []})

        result = await arun_agent(mock_agent, "hello", thread_id="test-thread")

        mock_agent.ainvoke.assert_called_once()
        call_args = mock_agent.ainvoke.call_args
        input_state = call_args[0][0]
        assert input_state["messages"][0]["content"] == "hello"


class TestRunAgentStream:
    """测试 run_agent_stream 流式函数。"""

    def test_raises_on_none_agent(self):
        """agent 为 None 时应抛 ValueError。"""
        with pytest.raises(ValueError, match="agent must not be None"):
            list(run_agent_stream(None, "hello"))

    def test_raises_on_empty_message(self):
        """message 为空时应抛 ValueError。"""
        with pytest.raises(ValueError, match="message must be a non-empty string"):
            list(run_agent_stream(MagicMock(), ""))

    def test_yields_tokens_from_stream_events(self):
        """应从 stream_events 中提取 token 并 yield。"""
        mock_agent = MagicMock()
        # 模拟 stream_events 返回的事件
        mock_agent.stream_events.return_value = iter([
            {"event": "on_chat_model_start", "data": {}},
            {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="你")}},
            {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="好")}},
            {"event": "on_chat_model_end", "data": {}},
        ])

        tokens = list(run_agent_stream(mock_agent, "hello"))

        assert tokens == ["你", "好"]

    def test_skips_empty_content(self):
        """应跳过空内容的 chunk。"""
        mock_agent = MagicMock()
        mock_agent.stream_events.return_value = iter([
            {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="hello")}},
            {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="")}},
            {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="world")}},
        ])

        tokens = list(run_agent_stream(mock_agent, "hello"))

        assert tokens == ["hello", "world"]


class TestArunAgentStream:
    """测试 arun_agent_stream 异步流式函数。"""

    @pytest.mark.asyncio
    async def test_raises_on_none_agent(self):
        """agent 为 None 时应抛 ValueError。"""
        with pytest.raises(ValueError, match="agent must not be None"):
            async for _ in arun_agent_stream(None, "hello"):
                pass

    @pytest.mark.asyncio
    async def test_raises_on_empty_message(self):
        """message 为空时应抛 ValueError。"""
        with pytest.raises(ValueError, match="message must be a non-empty string"):
            async for _ in arun_agent_stream(MagicMock(), ""):
                pass

    @pytest.mark.asyncio
    async def test_yields_tokens_from_astream_events(self):
        """应从 astream_events 中提取 token 并 yield。"""

        async def mock_astream_events(*args, **kwargs):
            events = [
                {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="数")}},
                {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="据")}},
                {"event": "on_chat_model_end", "data": {}},
            ]
            for e in events:
                yield e

        mock_agent = MagicMock()
        mock_agent.astream_events = mock_astream_events

        tokens = []
        async for token in arun_agent_stream(mock_agent, "hello"):
            tokens.append(token)

        assert tokens == ["数", "据"]
