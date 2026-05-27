"""测试 agent 创建和运行（mock 模式，不调用真实 API）。"""

import pytest
from unittest.mock import MagicMock, patch

from hz_agent_base.agent import _get_model, create_agent
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
        """传入 None 时应返回默认模型。"""
        with patch("hz_agent_base.agent.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            _get_model(None)
            # 应该用默认模型名创建
            mock_cls.assert_called()

    def test_deepseek_model_uses_base_url(self):
        """deepseek 模型应使用专用 base_url。"""
        with patch("hz_agent_base.agent.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            _get_model("deepseek-v4-flash")
            call_kwargs = mock_cls.call_args[1]
            assert "deepseek" in call_kwargs.get("base_url", "").lower()
            assert call_kwargs.get("model") == "deepseek-v4-flash"

    def test_non_deepseek_model_uses_default_url(self):
        """非 deepseek 模型不应设置 base_url。"""
        with patch("hz_agent_base.agent.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            _get_model("gpt-4")
            call_kwargs = mock_cls.call_args[1]
            assert "base_url" not in call_kwargs


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

        mock_get_model.assert_called_once_with("deepseek-v4-flash")

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
