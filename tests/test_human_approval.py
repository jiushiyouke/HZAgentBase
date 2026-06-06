"""测试 Human-in-the-loop 中间件 HumanApprovalMiddleware。"""

import pytest
from unittest.mock import MagicMock, patch
from io import StringIO

from langchain_core.messages import ToolMessage

from hz_agent_base.middleware.human_approval import HumanApprovalMiddleware
from hz_agent_base.human_approval import ApprovalRule, ConsoleApprovalCallback


# ============================================================
# 辅助函数
# ============================================================

def make_mock_tool_call(name: str, args: dict = None, call_id: str = "call-1"):
    """创建一个模拟的工具调用。"""
    tool_call = MagicMock()
    tool_call.name = name
    tool_call.args = args or {}
    tool_call.id = call_id
    return tool_call


def make_mock_request(tool_call=None):
    """创建一个模拟的 ModelRequest 对象。"""
    request = MagicMock()
    request.tool_call = tool_call or make_mock_tool_call("test_tool")
    return request


# ============================================================
# ApprovalRule 测试
# ============================================================

class TestApprovalRule:
    """测试审批规则。"""

    def test_matches_by_tool_name(self):
        """按工具名匹配。"""
        rule = ApprovalRule(tools=["bash", "delete_file"])
        assert rule.matches("bash", {}) is True
        assert rule.matches("delete_file", {}) is True
        assert rule.matches("read_file", {}) is False

    def test_matches_with_patterns(self):
        """按参数模式匹配。"""
        rule = ApprovalRule(
            tools=["write_file"],
            patterns=[".env*", "secrets/*"],
        )
        assert rule.matches("write_file", {"file_path": ".env"}) is True
        assert rule.matches("write_file", {"file_path": ".env.local"}) is True
        assert rule.matches("write_file", {"file_path": "secrets/key.pem"}) is True
        assert rule.matches("write_file", {"file_path": "main.py"}) is False

    def test_matches_no_patterns(self):
        """无模式时只匹配工具名。"""
        rule = ApprovalRule(tools=["bash"])
        assert rule.matches("bash", {"command": "rm -rf /"}) is True

    def test_matches_empty_args(self):
        """空参数且有模式时不匹配。"""
        rule = ApprovalRule(tools=["bash"], patterns=["rm *"])
        assert rule.matches("bash", {}) is False

    def test_matches_command_in_args(self):
        """检查 command 参数。"""
        rule = ApprovalRule(tools=["bash"], patterns=["rm *"])
        assert rule.matches("bash", {"command": "rm -rf /"}) is True
        assert rule.matches("bash", {"command": "ls -la"}) is False


# ============================================================
# ConsoleApprovalCallback 测试
# ============================================================

class TestConsoleApprovalCallback:
    """测试控制台审批回调。"""

    def test_approve_with_y(self):
        """输入 y 批准。"""
        callback = ConsoleApprovalCallback()
        with patch("builtins.input", return_value="y"):
            assert callback.request_approval("bash", {}, "") is True

    def test_approve_with_yes(self):
        """输入 yes 批准。"""
        callback = ConsoleApprovalCallback()
        with patch("builtins.input", return_value="yes"):
            assert callback.request_approval("bash", {}, "") is True

    def test_reject_with_n(self):
        """输入 n 拒绝。"""
        callback = ConsoleApprovalCallback()
        with patch("builtins.input", return_value="n"):
            assert callback.request_approval("bash", {}, "") is False

    def test_reject_with_no(self):
        """输入 no 拒绝。"""
        callback = ConsoleApprovalCallback()
        with patch("builtins.input", return_value="no"):
            assert callback.request_approval("bash", {}, "") is False


# ============================================================
# HumanApprovalMiddleware 测试
# ============================================================

class TestHumanApprovalMiddleware:
    """测试 Human-in-the-loop 中间件。"""

    def test_no_rules_passes_through(self):
        """无规则时直接通过。"""
        mw = HumanApprovalMiddleware(rules=[])
        request = make_mock_request(make_mock_tool_call("bash"))
        handler = MagicMock(return_value="response")

        result = mw.wrap_tool_call(request, handler)
        handler.assert_called_once_with(request)
        assert result == "response"

    def test_matching_rule_requests_approval(self):
        """匹配规则时请求审批。"""
        mock_callback = MagicMock()
        mock_callback.request_approval.return_value = True

        mw = HumanApprovalMiddleware(
            rules=[ApprovalRule(tools=["bash"])],
            callback=mock_callback,
        )
        request = make_mock_request(make_mock_tool_call("bash"))
        handler = MagicMock(return_value="response")

        mw.wrap_tool_call(request, handler)
        mock_callback.request_approval.assert_called_once()

    def test_approved_executes_tool(self):
        """批准后执行工具。"""
        mock_callback = MagicMock()
        mock_callback.request_approval.return_value = True

        mw = HumanApprovalMiddleware(
            rules=[ApprovalRule(tools=["bash"])],
            callback=mock_callback,
        )
        request = make_mock_request(make_mock_tool_call("bash"))
        handler = MagicMock(return_value="response")

        result = mw.wrap_tool_call(request, handler)
        handler.assert_called_once_with(request)
        assert result == "response"

    def test_rejected_blocks_tool(self):
        """拒绝后阻止工具执行。"""
        mock_callback = MagicMock()
        mock_callback.request_approval.return_value = False

        mw = HumanApprovalMiddleware(
            rules=[ApprovalRule(tools=["bash"])],
            callback=mock_callback,
        )
        tool_call = make_mock_tool_call("bash", call_id="call-123")
        request = make_mock_request(tool_call)
        handler = MagicMock(return_value="response")

        result = mw.wrap_tool_call(request, handler)
        handler.assert_not_called()
        assert isinstance(result, ToolMessage)
        assert "拒绝" in result.content
        assert result.tool_call_id == "call-123"

    def test_non_matching_tool_passes_through(self):
        """不匹配的工具直接通过。"""
        mock_callback = MagicMock()

        mw = HumanApprovalMiddleware(
            rules=[ApprovalRule(tools=["bash"])],
            callback=mock_callback,
        )
        request = make_mock_request(make_mock_tool_call("read_file"))
        handler = MagicMock(return_value="response")

        result = mw.wrap_tool_call(request, handler)
        handler.assert_called_once_with(request)
        mock_callback.request_approval.assert_not_called()

    def test_multiple_rules(self):
        """多个规则。"""
        mock_callback = MagicMock()
        mock_callback.request_approval.return_value = True

        mw = HumanApprovalMiddleware(
            rules=[
                ApprovalRule(tools=["bash"]),
                ApprovalRule(tools=["delete_file"]),
            ],
            callback=mock_callback,
        )

        # bash 匹配第一个规则
        request = make_mock_request(make_mock_tool_call("bash"))
        handler = MagicMock(return_value="response")
        mw.wrap_tool_call(request, handler)
        assert mock_callback.request_approval.call_count == 1

        # delete_file 匹配第二个规则
        request = make_mock_request(make_mock_tool_call("delete_file"))
        mw.wrap_tool_call(request, handler)
        assert mock_callback.request_approval.call_count == 2

    def test_pattern_matching(self):
        """模式匹配。"""
        mock_callback = MagicMock()
        mock_callback.request_approval.return_value = True

        mw = HumanApprovalMiddleware(
            rules=[
                ApprovalRule(
                    tools=["write_file"],
                    patterns=[".env*"],
                    description="写入敏感文件需确认",
                )
            ],
            callback=mock_callback,
        )

        # 匹配 .env
        request = make_mock_request(
            make_mock_tool_call("write_file", {"file_path": ".env"})
        )
        handler = MagicMock(return_value="response")
        mw.wrap_tool_call(request, handler)
        mock_callback.request_approval.assert_called_once()
        # 检查描述是否传递
        call_args = mock_callback.request_approval.call_args
        assert call_args[0][2] == "写入敏感文件需确认"

    def test_pattern_not_matching(self):
        """模式不匹配时直接通过。"""
        mock_callback = MagicMock()

        mw = HumanApprovalMiddleware(
            rules=[
                ApprovalRule(tools=["write_file"], patterns=[".env*"])
            ],
            callback=mock_callback,
        )

        request = make_mock_request(
            make_mock_tool_call("write_file", {"file_path": "main.py"})
        )
        handler = MagicMock(return_value="response")
        mw.wrap_tool_call(request, handler)
        mock_callback.request_approval.assert_not_called()

    def test_default_approve_on_error(self):
        """异常时默认批准。"""
        mock_callback = MagicMock()
        mock_callback.request_approval.side_effect = Exception("error")

        mw = HumanApprovalMiddleware(
            rules=[ApprovalRule(tools=["bash"])],
            callback=mock_callback,
            default_approve=True,
        )
        request = make_mock_request(make_mock_tool_call("bash"))
        handler = MagicMock(return_value="response")

        result = mw.wrap_tool_call(request, handler)
        handler.assert_called_once_with(request)

    def test_default_reject_on_error(self):
        """异常时默认拒绝。"""
        mock_callback = MagicMock()
        mock_callback.request_approval.side_effect = Exception("error")

        mw = HumanApprovalMiddleware(
            rules=[ApprovalRule(tools=["bash"])],
            callback=mock_callback,
            default_approve=False,
        )
        request = make_mock_request(make_mock_tool_call("bash"))
        handler = MagicMock(return_value="response")

        result = mw.wrap_tool_call(request, handler)
        handler.assert_not_called()


# ============================================================
# 集成测试
# ============================================================

class TestIntegration:
    """集成测试。"""

    def test_create_agent_with_human_approval(self):
        """测试 create_agent 集成。"""
        from hz_agent_base import create_agent
        from hz_agent_base.middleware.human_approval import HumanApprovalMiddleware, ApprovalRule

        mock_callback = MagicMock()
        mock_callback.request_approval.return_value = True

        agent = create_agent(
            model="deepseek-v4-flash",
            middleware=[
                HumanApprovalMiddleware(
                    rules=[ApprovalRule(tools=["bash"])],
                    callback=mock_callback,
                )
            ],
        )
        assert agent is not None

    def test_priority_constant_exists(self):
        """测试优先级常量存在。"""
        from hz_agent_base.utils.constants import HUMAN_APPROVAL
        assert HUMAN_APPROVAL == 8

    def test_middleware_exported(self):
        """测试中间件被正确导出。"""
        from hz_agent_base.middleware import HumanApprovalMiddleware, ApprovalRule
        assert HumanApprovalMiddleware is not None
        assert ApprovalRule is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
