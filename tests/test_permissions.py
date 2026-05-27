"""测试权限系统：PermissionSettings、PermissionChecker。"""

import pytest

from hz_agent_base.permissions.modes import PermissionMode
from hz_agent_base.permissions.settings import PermissionSettings, SENSITIVE_PATH_PATTERNS
from hz_agent_base.permissions.checker import PermissionChecker, PermissionDecision


class TestPermissionSettings:
    """测试 PermissionSettings 数据类。"""

    def test_default_mode(self):
        """默认模式应为 DEFAULT。"""
        settings = PermissionSettings()
        assert settings.mode == PermissionMode.DEFAULT

    def test_custom_mode(self):
        """应支持自定义模式。"""
        settings = PermissionSettings(mode=PermissionMode.FULL_AUTO)
        assert settings.mode == PermissionMode.FULL_AUTO

    def test_default_denied_commands(self):
        """默认应包含危险命令模式。"""
        settings = PermissionSettings()
        assert "rm -rf /" in settings.denied_commands
        assert "mkfs" in settings.denied_commands

    def test_sensitive_paths_not_empty(self):
        """敏感路径列表不应为空。"""
        assert len(SENSITIVE_PATH_PATTERNS) > 0


class TestPermissionChecker:
    """测试 PermissionChecker。"""

    # === is_tool_allowed ===

    def test_is_tool_allowed_when_no_lists(self):
        """没有允许/禁止名单时，所有工具都应允许。"""
        checker = PermissionChecker(PermissionSettings())
        assert checker.is_tool_allowed("any_tool") is True

    def test_is_tool_allowed_denied(self):
        """被禁止的工具应返回 False。"""
        settings = PermissionSettings(denied_tools=["bash", "eval"])
        checker = PermissionChecker(settings)
        assert checker.is_tool_allowed("bash") is False
        assert checker.is_tool_allowed("eval") is False

    def test_is_tool_allowed_not_in_allow_list(self):
        """不在允许名单中的工具应返回 False。"""
        settings = PermissionSettings(allowed_tools=["read_file", "glob"])
        checker = PermissionChecker(settings)
        assert checker.is_tool_allowed("bash") is False

    def test_is_tool_allowed_in_allow_list(self):
        """在允许名单中的工具应返回 True。"""
        settings = PermissionSettings(allowed_tools=["read_file", "glob"])
        checker = PermissionChecker(settings)
        assert checker.is_tool_allowed("read_file") is True

    def test_is_tool_allowed_deny_overrides_allow(self):
        """禁止名单优先于允许名单。"""
        settings = PermissionSettings(
            allowed_tools=["bash"],
            denied_tools=["bash"],
        )
        checker = PermissionChecker(settings)
        assert checker.is_tool_allowed("bash") is False

    # === evaluate ===

    def test_evaluate_sensitive_path_denied(self):
        """敏感路径应被拒绝。"""
        checker = PermissionChecker(PermissionSettings())
        decision = checker.evaluate("read_file", file_path="~/.ssh/id_rsa")
        assert decision.allowed is False
        assert "sensitive" in decision.reason.lower()

    def test_evaluate_denied_tool(self):
        """被禁止的工具应被拒绝。"""
        settings = PermissionSettings(denied_tools=["eval"])
        checker = PermissionChecker(settings)
        decision = checker.evaluate("eval")
        assert decision.allowed is False
        assert "deny list" in decision.reason

    def test_evaluate_allowed_tool(self):
        """在允许名单中的工具应被允许。"""
        settings = PermissionSettings(allowed_tools=["read_file"])
        checker = PermissionChecker(settings)
        decision = checker.evaluate("read_file")
        assert decision.allowed is True

    def test_evaluate_plan_mode_blocks_writes(self):
        """PLAN 模式应阻止写操作。"""
        settings = PermissionSettings(mode=PermissionMode.PLAN)
        checker = PermissionChecker(settings)
        decision = checker.evaluate("write_file", is_read_only=False)
        assert decision.allowed is False
        assert "plan" in decision.reason.lower()

    def test_evaluate_plan_mode_allows_reads(self):
        """PLAN 模式应允许读操作。"""
        settings = PermissionSettings(mode=PermissionMode.PLAN)
        checker = PermissionChecker(settings)
        decision = checker.evaluate("read_file", is_read_only=True)
        assert decision.allowed is True

    def test_evaluate_full_auto_allows_all(self):
        """FULL_AUTO 模式应允许所有操作。"""
        settings = PermissionSettings(mode=PermissionMode.FULL_AUTO)
        checker = PermissionChecker(settings)
        decision = checker.evaluate("any_tool", is_read_only=False)
        assert decision.allowed is True

    def test_evaluate_denied_command(self):
        """危险命令应被拒绝。"""
        checker = PermissionChecker(PermissionSettings())
        decision = checker.evaluate("bash", command="rm -rf /")
        assert decision.allowed is False

    def test_evaluate_default_mode_write_needs_confirmation(self):
        """DEFAULT 模式下写操作需要确认。"""
        checker = PermissionChecker(PermissionSettings())
        decision = checker.evaluate("write_file", is_read_only=False)
        assert decision.allowed is True
        assert decision.requires_confirmation is True

    def test_evaluate_default_mode_read_auto_allowed(self):
        """DEFAULT 模式下读操作自动允许。"""
        checker = PermissionChecker(PermissionSettings())
        decision = checker.evaluate("read_file", is_read_only=True)
        assert decision.allowed is True
        assert decision.requires_confirmation is False

    def test_evaluate_denied_path_pattern(self):
        """被禁止的路径模式应拒绝。"""
        settings = PermissionSettings(denied_paths=["*.pem"])
        checker = PermissionChecker(settings)
        decision = checker.evaluate("read_file", file_path="server.pem")
        assert decision.allowed is False
