"""测试中间件：PermissionMiddleware、HookMiddleware、MemoryMiddleware。"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from hz_agent_base.permissions.settings import PermissionSettings, PermissionMode
from hz_agent_base.middleware.permission import PermissionMiddleware
from hz_agent_base.middleware.hook import HookMiddleware
from hz_agent_base.middleware.memory import MemoryMiddleware
from hz_agent_base.hooks.registry import HookRegistry
from hz_agent_base.hooks.events import HookEvent
from hz_agent_base.hooks.schemas import HookDefinition


# ============================================================
# 辅助函数：构造 mock ModelRequest
# ============================================================

def make_mock_request(tools=None, messages=None, system_prompt="You are helpful."):
    """创建一个模拟的 ModelRequest 对象。"""
    request = MagicMock()
    request.tools = tools or []
    request.messages = messages or [HumanMessage(content="hello")]
    request.system_prompt = system_prompt
    request.system_message = SystemMessage(content=system_prompt) if system_prompt else None

    # override() 返回一个新的 mock，记录调用参数
    def mock_override(**kwargs):
        new_req = make_mock_request(
            tools=kwargs.get("tools", request.tools),
            messages=request.messages,
            system_prompt=kwargs.get("system_prompt", request.system_prompt),
        )
        return new_req

    request.override = MagicMock(side_effect=mock_override)
    return request


def make_mock_tool(name):
    """创建一个模拟工具对象。"""
    tool = MagicMock()
    tool.name = name
    return tool


# ============================================================
# PermissionMiddleware 测试
# ============================================================

class TestPermissionMiddleware:
    """测试权限中间件。"""

    def test_full_auto_passes_through(self):
        """FULL_AUTO 模式不应过滤任何工具。"""
        settings = PermissionSettings(mode=PermissionMode.FULL_AUTO)
        middleware = PermissionMiddleware(settings)

        tools = [make_mock_tool("bash"), make_mock_tool("eval")]
        request = make_mock_request(tools=tools)
        handler = MagicMock(return_value="response")

        result = middleware.wrap_model_call(request, handler)

        # FULL_AUTO 直接调用 handler，不过滤
        handler.assert_called_once_with(request)
        assert result == "response"

    def test_filters_denied_tools(self):
        """应过滤掉被禁止的工具。"""
        settings = PermissionSettings(denied_tools=["eval"])
        middleware = PermissionMiddleware(settings)

        bash_tool = make_mock_tool("bash")
        eval_tool = make_mock_tool("eval")
        request = make_mock_request(tools=[bash_tool, eval_tool])
        handler = MagicMock(return_value="response")

        middleware.wrap_model_call(request, handler)

        # handler 应收到过滤后的请求（只有 bash）
        filtered_request = handler.call_args[0][0]
        tool_names = [t.name for t in filtered_request.tools]
        assert "bash" in tool_names
        assert "eval" not in tool_names

    def test_filters_by_allow_list(self):
        """应只保留允许名单中的工具。"""
        settings = PermissionSettings(allowed_tools=["read_file"])
        middleware = PermissionMiddleware(settings)

        tools = [make_mock_tool("read_file"), make_mock_tool("bash"), make_mock_tool("eval")]
        request = make_mock_request(tools=tools)
        handler = MagicMock(return_value="response")

        middleware.wrap_model_call(request, handler)

        filtered_request = handler.call_args[0][0]
        tool_names = [t.name for t in filtered_request.tools]
        assert tool_names == ["read_file"]

    def test_all_tools_allowed_when_no_lists(self):
        """没有允许/禁止名单时，所有工具都应通过。"""
        settings = PermissionSettings()
        middleware = PermissionMiddleware(settings)

        tools = [make_mock_tool("a"), make_mock_tool("b")]
        request = make_mock_request(tools=tools)
        handler = MagicMock(return_value="response")

        middleware.wrap_model_call(request, handler)

        filtered_request = handler.call_args[0][0]
        assert len(filtered_request.tools) == 2


# ============================================================
# HookMiddleware 测试
# ============================================================

class TestHookMiddleware:
    """测试钩子中间件。"""

    def test_passes_through_with_no_hooks(self):
        """没有钩子时应直接调用 handler。"""
        registry = HookRegistry()
        middleware = HookMiddleware(registry)

        request = make_mock_request()
        handler = MagicMock(return_value="response")

        result = middleware.wrap_model_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "response"

    def test_fires_user_prompt_submit_hook(self):
        """应触发 USER_PROMPT_SUBMIT 事件。"""
        registry = HookRegistry()
        fired_events = []

        # 用 CommandHookDefinition 来检测事件触发
        hook = HookDefinition(event=HookEvent.USER_PROMPT_SUBMIT)
        registry.register(hook)

        middleware = HookMiddleware(registry)

        request = make_mock_request(
            messages=[HumanMessage(content="test message")]
        )
        handler = MagicMock(return_value="response")

        # 通过 mock executor 来检测事件
        with patch.object(middleware.executor, "execute") as mock_exec:
            mock_exec.return_value = MagicMock(blocked=False)
            middleware.wrap_model_call(request, handler)

            # 确认 USER_PROMPT_SUBMIT 事件被触发
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args
            assert call_args[0][0] == HookEvent.USER_PROMPT_SUBMIT
            assert call_args[0][1]["prompt"] == "test message"

    def test_blocked_hook_prevents_handler_call(self):
        """被阻止的钩子应阻止 handler 被调用。"""
        registry = HookRegistry()
        registry.register(HookDefinition(event=HookEvent.USER_PROMPT_SUBMIT))

        middleware = HookMiddleware(registry)

        request = make_mock_request(
            messages=[HumanMessage(content="blocked message")]
        )
        handler = MagicMock(return_value="response")

        with patch.object(middleware.executor, "execute") as mock_exec:
            mock_exec.return_value = MagicMock(blocked=True, reason="forbidden")

            result = middleware.wrap_model_call(request, handler)

            # handler 不应被调用
            handler.assert_not_called()
            # 返回值应包含阻止信息
            assert result is not None


# ============================================================
# MemoryMiddleware 测试
# ============================================================

class TestMemoryMiddleware:
    """测试记忆中间件。"""

    def test_passes_through_when_no_memories(self, tmp_memory_dir):
        """没有相关记忆时应直接调用 handler。"""
        middleware = MemoryMiddleware(str(tmp_memory_dir))

        request = make_mock_request(
            messages=[HumanMessage(content="hello")]
        )
        handler = MagicMock(return_value="response")

        result = middleware.wrap_model_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "response"

    def test_injects_relevant_memories(self, tmp_memory_dir):
        """应将相关记忆注入系统提示词。"""
        # 先写入一条记忆
        from hz_agent_base.memory.manager import MemoryManager
        manager = MemoryManager(str(tmp_memory_dir))
        manager.add_memory("python-tips", "Python logging 最佳实践")

        middleware = MemoryMiddleware(str(tmp_memory_dir))

        request = make_mock_request(
            messages=[HumanMessage(content="Python logging 怎么用")],
            system_prompt="You are helpful.",
        )
        handler = MagicMock(return_value="response")

        middleware.wrap_model_call(request, handler)

        # handler 应收到被修改过的请求（包含记忆注入）
        filtered_request = handler.call_args[0][0]
        # override 应被调用以注入记忆
        request.override.assert_called()

    def test_skips_memory_for_non_human_messages(self, tmp_memory_dir):
        """非用户消息不应触发记忆搜索。"""
        middleware = MemoryMiddleware(str(tmp_memory_dir))

        # 只有 AI 消息，没有用户消息
        request = make_mock_request(
            messages=[AIMessage(content="I am AI")]
        )
        handler = MagicMock(return_value="response")

        middleware.wrap_model_call(request, handler)

        # 应直接调用 handler，不修改请求
        handler.assert_called_once_with(request)
