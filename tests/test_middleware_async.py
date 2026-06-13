"""测试所有中间件的异步方法。

验证每个中间件都正确实现了 awrap_model_call 和/或 awrap_tool_call。
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

from hz_agent_base.permissions.settings import PermissionSettings, PermissionMode
from hz_agent_base.middleware.permission import PermissionMiddleware
from hz_agent_base.middleware.hook import HookMiddleware
from hz_agent_base.middleware.memory import MemoryMiddleware
from hz_agent_base.middleware.knowledge import KnowledgeMiddleware
from hz_agent_base.middleware.filesystem import FileAuditMiddleware
from hz_agent_base.middleware.resilient import ResilientMiddleware
from hz_agent_base.middleware.conversation_history import ConversationHistoryMiddleware
from hz_agent_base.middleware.sanitizer import OutputSanitizerMiddleware
from hz_agent_base.middleware.human_approval import HumanApprovalMiddleware
from hz_agent_base.middleware.guardrails import GuardrailsMiddleware
from hz_agent_base.middleware.evolution_memory import EvolutionMemoryMiddleware
from hz_agent_base.hooks.registry import HookRegistry
from hz_agent_base.hooks.events import HookEvent
from hz_agent_base.hooks.schemas import HookDefinition
from hz_agent_base.human_approval import ApprovalRule


# ============================================================
# 辅助函数
# ============================================================

def make_mock_request(tools=None, messages=None, system_prompt="You are helpful."):
    """创建一个模拟的 ModelRequest 对象。"""
    request = MagicMock()
    request.tools = tools or []
    request.messages = messages or [HumanMessage(content="hello")]
    request.system_prompt = system_prompt
    request.system_message = SystemMessage(content=system_prompt) if system_prompt else None

    def mock_override(**kwargs):
        new_req = MagicMock()
        new_req.tools = kwargs.get("tools", request.tools)
        new_req.messages = kwargs.get("messages", request.messages)
        new_req.system_prompt = kwargs.get("system_prompt", request.system_prompt)
        new_req.system_message = SystemMessage(content=new_req.system_prompt) if new_req.system_prompt else None
        return new_req

    request.override = MagicMock(side_effect=mock_override)
    return request


def make_mock_tool_call(name, args=None, tool_call_id="test-id"):
    """创建一个模拟的 tool_call。"""
    return {
        "name": name,
        "args": args or {},
        "id": tool_call_id,
    }


def make_mock_tool_request(tool_call, tool=None):
    """创建一个模拟的 ToolCallRequest。"""
    request = MagicMock()
    request.tool_call = tool_call
    request.tool = tool
    request.state = MagicMock()
    request.runtime = MagicMock()
    return request


def make_mock_tool(name):
    """创建一个模拟工具对象。"""
    tool = MagicMock()
    tool.name = name
    return tool


# ============================================================
# PermissionMiddleware 异步测试
# ============================================================

class TestPermissionMiddlewareAsync:
    """测试权限中间件的异步方法。"""

    @pytest.mark.asyncio
    async def test_awrap_model_call_full_auto(self):
        """FULL_AUTO 模式下 awrap_model_call 应直接透传。"""
        settings = PermissionSettings(mode=PermissionMode.FULL_AUTO)
        middleware = PermissionMiddleware(settings)

        tools = [make_mock_tool("bash"), make_mock_tool("eval")]
        request = make_mock_request(tools=tools)
        handler = AsyncMock(return_value="response")

        result = await middleware.awrap_model_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "response"

    @pytest.mark.asyncio
    async def test_awrap_model_call_filters_tools(self):
        """awrap_model_call 应过滤被禁止的工具。"""
        settings = PermissionSettings(denied_tools=["eval"])
        middleware = PermissionMiddleware(settings)

        bash_tool = make_mock_tool("bash")
        eval_tool = make_mock_tool("eval")
        request = make_mock_request(tools=[bash_tool, eval_tool])
        handler = AsyncMock(return_value="response")

        await middleware.awrap_model_call(request, handler)

        # handler 应收到过滤后的请求
        filtered_request = handler.call_args[0][0]
        tool_names = [t.name for t in filtered_request.tools]
        assert "bash" in tool_names
        assert "eval" not in tool_names

    @pytest.mark.asyncio
    async def test_awrap_tool_call_full_auto(self):
        """FULL_AUTO 模式下 awrap_tool_call 应直接透传。"""
        settings = PermissionSettings(mode=PermissionMode.FULL_AUTO)
        middleware = PermissionMiddleware(settings)

        tool_call = make_mock_tool_call("bash", {"command": "ls"})
        request = make_mock_tool_request(tool_call)
        handler = AsyncMock(return_value=ToolMessage(content="ok", tool_call_id="test-id"))

        result = await middleware.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_awrap_tool_call_blocks_denied(self):
        """awrap_tool_call 应阻止被禁止的工具。"""
        settings = PermissionSettings(denied_tools=["eval"])
        middleware = PermissionMiddleware(settings)

        tool_call = make_mock_tool_call("eval", {"code": "1+1"})
        request = make_mock_tool_request(tool_call)
        handler = AsyncMock()

        result = await middleware.awrap_tool_call(request, handler)

        # handler 不应被调用
        handler.assert_not_called()
        # 返回应是 ToolMessage 且包含 "Permission denied"
        assert "Permission denied" in result.content


# ============================================================
# MemoryMiddleware 异步测试
# ============================================================

class TestMemoryMiddlewareAsync:
    """测试记忆中间件的异步方法。"""

    @pytest.mark.asyncio
    async def test_awrap_model_call_no_memories(self, tmp_memory_dir):
        """没有相关记忆时应直接调用 handler。"""
        middleware = MemoryMiddleware(str(tmp_memory_dir), isolate_by_user=False)

        request = make_mock_request(
            messages=[HumanMessage(content="hello")]
        )
        handler = AsyncMock(return_value="response")

        result = await middleware.awrap_model_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "response"

    @pytest.mark.asyncio
    async def test_awrap_model_call_injects_memories(self, tmp_memory_dir):
        """应将相关记忆注入系统提示词。"""
        from hz_agent_base.memory.manager import MemoryManager
        manager = MemoryManager(str(tmp_memory_dir))
        manager.add_memory("python-tips", "Python logging 最佳实践")

        middleware = MemoryMiddleware(str(tmp_memory_dir), isolate_by_user=False)

        request = make_mock_request(
            messages=[HumanMessage(content="Python logging 怎么用")],
            system_prompt="You are helpful.",
        )
        handler = AsyncMock(return_value="response")

        await middleware.awrap_model_call(request, handler)

        # handler 应收到被修改过的请求
        handler.assert_called_once()
        filtered_request = handler.call_args[0][0]
        # 应包含记忆注入
        assert "Relevant Memories" in filtered_request.system_prompt or "Memory" in filtered_request.system_prompt


# ============================================================
# KnowledgeMiddleware 异步测试
# ============================================================

class TestKnowledgeMiddlewareAsync:
    """测试知识库中间件的异步方法。"""

    @pytest.mark.asyncio
    async def test_awrap_model_call_no_query(self):
        """没有用户消息时应直接调用 handler。"""
        retriever = MagicMock()
        middleware = KnowledgeMiddleware(retriever)

        request = make_mock_request(messages=[AIMessage(content="I am AI")])
        handler = AsyncMock(return_value="response")

        result = await middleware.awrap_model_call(request, handler)

        handler.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_awrap_model_call_injects_knowledge(self):
        """应将检索结果注入系统提示词。"""
        from hz_agent_base.knowledge.protocol import RetrievalResult

        # 创建 mock retriever
        retriever = MagicMock()
        mock_result = RetrievalResult(
            content="Python is a programming language",
            source="wiki",
            score=0.9,
        )
        retriever.retrieve.return_value = [mock_result]

        middleware = KnowledgeMiddleware(retriever)

        # 使用真实的 HumanMessage
        messages = [HumanMessage(content="What is Python?")]
        request = make_mock_request(
            messages=messages,
            system_prompt="You are helpful.",
        )
        handler = AsyncMock(return_value="response")

        # 显式设置 request 属性，确保 _get_user_id 返回 None
        request.configurable = {}
        request.user_id = None
        request.thread_id = None

        await middleware.awrap_model_call(request, handler)

        # retriever.retrieve 应被调用
        retriever.retrieve.assert_called_once()
        # handler 应收到包含知识的请求
        handler.assert_called_once()
        filtered_request = handler.call_args[0][0]
        assert "Knowledge Base" in filtered_request.system_prompt


# ============================================================
# HookMiddleware 异步测试
# ============================================================

class TestHookMiddlewareAsync:
    """测试钩子中间件的异步方法。"""

    @pytest.mark.asyncio
    async def test_awrap_model_call_no_hooks(self):
        """没有钩子时应直接调用 handler。"""
        registry = HookRegistry()
        middleware = HookMiddleware(registry)

        request = make_mock_request()
        handler = AsyncMock(return_value="response")

        result = await middleware.awrap_model_call(request, handler)

        handler.assert_called_once_with(request)
        assert result == "response"

    @pytest.mark.asyncio
    async def test_awrap_model_call_fires_hook(self):
        """应触发 USER_PROMPT_SUBMIT 事件。"""
        registry = HookRegistry()
        registry.register(HookDefinition(event=HookEvent.USER_PROMPT_SUBMIT))

        middleware = HookMiddleware(registry)

        request = make_mock_request(
            messages=[HumanMessage(content="test message")]
        )
        handler = AsyncMock(return_value="response")

        with patch.object(middleware.executor, "execute") as mock_exec:
            mock_exec.return_value = MagicMock(blocked=False)
            await middleware.awrap_model_call(request, handler)

            mock_exec.assert_called_once()
            call_args = mock_exec.call_args
            assert call_args[0][0] == HookEvent.USER_PROMPT_SUBMIT
            assert call_args[0][1]["prompt"] == "test message"

    @pytest.mark.asyncio
    async def test_awrap_model_call_blocked(self):
        """被阻止的钩子应阻止 handler 被调用。"""
        registry = HookRegistry()
        registry.register(HookDefinition(event=HookEvent.USER_PROMPT_SUBMIT))

        middleware = HookMiddleware(registry)

        request = make_mock_request(
            messages=[HumanMessage(content="blocked message")]
        )
        handler = AsyncMock(return_value="response")

        with patch.object(middleware.executor, "execute") as mock_exec:
            mock_exec.return_value = MagicMock(blocked=True, reason="forbidden")

            result = await middleware.awrap_model_call(request, handler)

            handler.assert_not_called()
            assert result is not None

    @pytest.mark.asyncio
    async def test_awrap_tool_call_fires_hooks(self):
        """应触发 PRE_TOOL_USE 和 POST_TOOL_USE 事件。"""
        registry = HookRegistry()
        middleware = HookMiddleware(registry)

        tool_call = make_mock_tool_call("bash", {"command": "ls"})
        request = make_mock_tool_request(tool_call)
        mock_response = ToolMessage(content="ok", tool_call_id="test-id")
        handler = AsyncMock(return_value=mock_response)

        with patch.object(middleware.executor, "execute") as mock_exec:
            mock_exec.return_value = MagicMock(blocked=False)
            result = await middleware.awrap_tool_call(request, handler)

            # 应被调用两次：PRE_TOOL_USE 和 POST_TOOL_USE
            assert mock_exec.call_count == 2
            calls = mock_exec.call_args_list
            assert calls[0][0][0] == HookEvent.PRE_TOOL_USE
            assert calls[1][0][0] == HookEvent.POST_TOOL_USE

    @pytest.mark.asyncio
    async def test_awrap_tool_call_blocked(self):
        """被阻止的工具调用应返回 ToolMessage。"""
        registry = HookRegistry()
        middleware = HookMiddleware(registry)

        tool_call = make_mock_tool_call("bash", {"command": "rm -rf /"})
        request = make_mock_tool_request(tool_call)
        handler = AsyncMock()

        with patch.object(middleware.executor, "execute") as mock_exec:
            mock_exec.return_value = MagicMock(blocked=True, reason="dangerous command")

            result = await middleware.awrap_tool_call(request, handler)

            handler.assert_not_called()
            assert "Blocked by hook" in result.content


# ============================================================
# FileAuditMiddleware 异步测试
# ============================================================

class TestFileAuditMiddlewareAsync:
    """测试文件审计中间件的异步方法。"""

    @pytest.mark.asyncio
    async def test_awrap_model_call_no_file_tools(self):
        """没有文件工具时应直接透传。"""
        middleware = FileAuditMiddleware(audit=True, track_changes=True)

        request = make_mock_request(tools=[make_mock_tool("bash")])
        handler = AsyncMock(return_value="response")

        result = await middleware.awrap_model_call(request, handler)

        handler.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_awrap_model_call_with_file_tools(self):
        """有文件工具时应记录操作。"""
        middleware = FileAuditMiddleware(audit=True, track_changes=True)

        tools = [make_mock_tool("read_file"), make_mock_tool("write_file")]
        request = make_mock_request(tools=tools)
        handler = AsyncMock(return_value="response")

        result = await middleware.awrap_model_call(request, handler)

        handler.assert_called_once_with(request)


# ============================================================
# ResilientMiddleware 异步测试
# ============================================================

class TestResilientMiddlewareAsync:
    """测试容错中间件的异步方法。"""

    @pytest.mark.asyncio
    async def test_awrap_model_call_success(self):
        """正常调用应直接返回结果。"""
        middleware = ResilientMiddleware(max_retries=2)

        request = make_mock_request()
        handler = AsyncMock(return_value="response")

        result = await middleware.awrap_model_call(request, handler)

        handler.assert_called_once()
        assert result == "response"

    @pytest.mark.asyncio
    async def test_awrap_model_call_retry_on_failure(self):
        """失败时应重试。"""
        middleware = ResilientMiddleware(max_retries=2, retry_base_delay=0.01)

        request = make_mock_request()
        handler = AsyncMock(side_effect=[Exception("fail"), "response"])

        result = await middleware.awrap_model_call(request, handler)

        # 应被调用两次（第一次失败，第二次成功）
        assert handler.call_count == 2
        assert result == "response"

    @pytest.mark.asyncio
    async def test_awrap_model_call_all_retries_fail(self):
        """所有重试都失败时应返回友好错误。"""
        middleware = ResilientMiddleware(max_retries=1, retry_base_delay=0.01)

        request = make_mock_request()
        handler = AsyncMock(side_effect=Exception("persistent failure"))

        result = await middleware.awrap_model_call(request, handler)

        # 应被调用两次（初始 + 1次重试）
        assert handler.call_count == 2
        # 应返回包含错误信息的响应
        messages = result.get("messages", [])
        assert len(messages) > 0
        assert "重试" in messages[0].content

    @pytest.mark.asyncio
    async def test_awrap_model_call_cancelled(self):
        """取消信号应立即返回。"""
        cancellation_checker = MagicMock()
        cancellation_checker.is_cancelled.return_value = True

        middleware = ResilientMiddleware(cancellation_checker=cancellation_checker)

        request = make_mock_request()
        handler = AsyncMock(return_value="response")

        # 需要模拟 request 中的 thread_id
        request.configurable = {"thread_id": "test-thread"}

        result = await middleware.awrap_model_call(request, handler)

        handler.assert_not_called()
        messages = result.get("messages", [])
        assert "取消" in messages[0].content


# ============================================================
# ConversationHistoryMiddleware 异步测试
# ============================================================

class TestConversationHistoryMiddlewareAsync:
    """测试对话历史管理中间件的异步方法。"""

    @pytest.mark.asyncio
    async def test_awrap_model_call_truncate(self):
        """truncate 策略应裁剪消息。"""
        middleware = ConversationHistoryMiddleware(
            strategy="truncate",
            max_messages=3,
        )

        # 创建 5 条消息
        messages = [
            HumanMessage(content=f"message {i}")
            for i in range(5)
        ]
        request = make_mock_request(messages=messages)
        handler = AsyncMock(return_value="response")

        result = await middleware.awrap_model_call(request, handler)

        handler.assert_called_once()
        filtered_request = handler.call_args[0][0]
        # 应只保留 3 条消息
        assert len(filtered_request.messages) == 3

    @pytest.mark.asyncio
    async def test_awrap_model_call_sliding_window(self):
        """sliding_window 策略应按 token 裁剪。"""
        middleware = ConversationHistoryMiddleware(
            strategy="sliding_window",
            max_tokens=100,  # 设置较小的 token 限制
        )

        # 创建多条长消息
        messages = [
            HumanMessage(content=f"This is a long message number {i} " * 20)
            for i in range(10)
        ]
        request = make_mock_request(messages=messages)
        handler = AsyncMock(return_value="response")

        result = await middleware.awrap_model_call(request, handler)

        handler.assert_called_once()
        filtered_request = handler.call_args[0][0]
        # 消息数应少于原始数量
        assert len(filtered_request.messages) < 10


# ============================================================
# OutputSanitizerMiddleware 异步测试
# ============================================================

class TestOutputSanitizerMiddlewareAsync:
    """测试输出清洗中间件的异步方法。"""

    @pytest.mark.asyncio
    async def test_awrap_model_call_masks_pii(self):
        """应遮盖 PII 信息。"""
        middleware = OutputSanitizerMiddleware(mask_pii=True)

        request = make_mock_request()
        # 模拟包含手机号的响应
        response = {
            "messages": [AIMessage(content="联系方式：13812345678")]
        }
        handler = AsyncMock(return_value=response)

        result = await middleware.awrap_model_call(request, handler)

        handler.assert_called_once()
        # 手机号应被遮盖
        content = result["messages"][0].content
        assert "13812345678" not in content
        assert "***" in content

    @pytest.mark.asyncio
    async def test_awrap_model_call_filters_sensitive_words(self):
        """应过滤敏感词。"""
        middleware = OutputSanitizerMiddleware(
            sensitive_words=["密码", "秘密"]
        )

        request = make_mock_request()
        response = {
            "messages": [AIMessage(content="请输入密码")]
        }
        handler = AsyncMock(return_value=response)

        result = await middleware.awrap_model_call(request, handler)

        content = result["messages"][0].content
        assert "密码" not in content
        assert "**" in content


# ============================================================
# HumanApprovalMiddleware 异步测试
# ============================================================

class TestHumanApprovalMiddlewareAsync:
    """测试人工审批中间件的异步方法。"""

    @pytest.mark.asyncio
    async def test_awrap_tool_call_no_matching_rule(self):
        """不匹配规则时应直接放行。"""
        rules = [ApprovalRule(tools=["delete_file"])]
        middleware = HumanApprovalMiddleware(rules=rules)

        tool_call = make_mock_tool_call("read_file", {"path": "/tmp/test.txt"})
        request = make_mock_tool_request(tool_call)
        handler = AsyncMock(return_value=ToolMessage(content="ok", tool_call_id="test-id"))

        result = await middleware.awrap_tool_call(request, handler)

        handler.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_awrap_tool_call_approved(self):
        """批准时应继续执行。"""
        rules = [ApprovalRule(tools=["bash"])]
        callback = MagicMock()
        callback.request_approval.return_value = True

        middleware = HumanApprovalMiddleware(rules=rules, callback=callback)

        tool_call = make_mock_tool_call("bash", {"command": "ls"})
        request = make_mock_tool_request(tool_call)
        handler = AsyncMock(return_value=ToolMessage(content="ok", tool_call_id="test-id"))

        result = await middleware.awrap_tool_call(request, handler)

        callback.request_approval.assert_called_once()
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_awrap_tool_call_rejected(self):
        """拒绝时应阻止执行。"""
        rules = [ApprovalRule(tools=["bash"])]
        callback = MagicMock()
        callback.request_approval.return_value = False

        middleware = HumanApprovalMiddleware(rules=rules, callback=callback)

        tool_call = make_mock_tool_call("bash", {"command": "rm -rf /"})
        request = make_mock_tool_request(tool_call)
        handler = AsyncMock()

        result = await middleware.awrap_tool_call(request, handler)

        handler.assert_not_called()
        assert "拒绝" in result.content


# ============================================================
# GuardrailsMiddleware 异步测试
# ============================================================

class TestGuardrailsMiddlewareAsync:
    """测试内容护栏中间件的异步方法。"""

    @pytest.mark.asyncio
    async def test_awrap_model_call_no_moderator(self):
        """没有审核器时应直接透传。"""
        middleware = GuardrailsMiddleware()

        request = make_mock_request()
        response = {"messages": [AIMessage(content="normal response")]}
        handler = AsyncMock(return_value=response)

        result = await middleware.awrap_model_call(request, handler)

        handler.assert_called_once()
        assert result == response

    @pytest.mark.asyncio
    async def test_awrap_model_call_content_blocked(self):
        """内容审核失败时应替换消息。"""
        from hz_agent_base.guardrails import ContentModerator

        moderator = MagicMock(spec=ContentModerator)
        moderator.is_safe.return_value = False

        middleware = GuardrailsMiddleware(
            content_moderator=moderator,
            block_on_failure=True,
        )

        request = make_mock_request()
        response = {"messages": [AIMessage(content="unsafe content")]}
        handler = AsyncMock(return_value=response)

        result = await middleware.awrap_model_call(request, handler)

        content = result["messages"][0].content
        assert "审核未通过" in content


# ============================================================
# EvolutionMemoryMiddleware 异步测试
# ============================================================

class TestEvolutionMemoryMiddlewareAsync:
    """测试进化记忆中间件的异步方法。"""

    @pytest.mark.asyncio
    async def test_awrap_model_call_injects_experience(self, tmp_path):
        """应注入历史经验。"""
        memory_path = str(tmp_path / "evolution")
        middleware = EvolutionMemoryMiddleware(
            memory_path=memory_path,
            inject_experience=True,
            auto_evaluate=False,  # 禁用自动评估简化测试
        )

        request = make_mock_request(
            messages=[HumanMessage(content="Write a Python function")]
        )
        response = {"messages": [AIMessage(content="def hello(): pass")]}
        handler = AsyncMock(return_value=response)

        result = await middleware.awrap_model_call(request, handler)

        handler.assert_called_once()
        # 应该正常返回结果
        assert result == response

    @pytest.mark.asyncio
    async def test_awrap_model_call_evaluates_and_stores(self, tmp_path):
        """应评估结果并存储经验。"""
        memory_path = str(tmp_path / "evolution")

        # Mock 评估器
        with patch("hz_agent_base.middleware.evolution_memory.TaskEvaluator") as MockEvaluator:
            mock_evaluator = MagicMock()
            mock_evaluator.evaluate.return_value = MagicMock(
                success=True,
                summary="Task completed",
                tools_used=["python"],
                issues=[],
                lessons=["lesson 1"],
            )
            MockEvaluator.return_value = mock_evaluator

            middleware = EvolutionMemoryMiddleware(
                memory_path=memory_path,
                auto_evaluate=True,
                auto_classify=False,
            )

            request = make_mock_request(
                messages=[HumanMessage(content="Write code")]
            )
            response = {"messages": [AIMessage(content="def hello(): pass")]}
            handler = AsyncMock(return_value=response)

            result = await middleware.awrap_model_call(request, handler)

            handler.assert_called_once()
            # 评估器应被调用
            mock_evaluator.evaluate.assert_called_once()
