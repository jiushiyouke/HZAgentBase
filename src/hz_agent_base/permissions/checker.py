"""权限检查器 — 评估工具调用是否被允许。

按以下优先级顺序评估：
1. 敏感路径检查 → 始终拒绝
2. 工具黑名单 → 拒绝
3. 工具白名单 → 允许
4. 路径规则（denied_paths / allowed_paths）
5. 命令黑名单（子串匹配）
6. 模式兜底（DEFAULT 需确认，FULL_AUTO 放行，PLAN 阻止写操作）
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .modes import PermissionMode
from .settings import PermissionSettings, SENSITIVE_PATH_PATTERNS


@dataclass(frozen=True)
class PermissionDecision:
    """权限检查结果。"""

    allowed: bool
    """是否允许执行。"""

    requires_confirmation: bool = False
    """是否需要用户确认（DEFAULT 模式下的写操作）。"""

    reason: str = ""
    """拒绝或需要确认的原因。"""


class PermissionChecker:
    """根据权限规则评估工具调用。"""

    def __init__(self, settings: PermissionSettings):
        self.settings = settings

    def is_tool_allowed(self, tool_name: str) -> bool:
        """快速检查工具是否被白名单/黑名单允许。

        用于 PermissionMiddleware 批量过滤工具列表。

        Args:
            tool_name: 工具名称。

        Returns:
            True 表示工具可用（不在黑名单中，且在白名单中或白名单为空）。
        """
        if tool_name in self.settings.denied_tools:
            return False
        if self.settings.allowed_tools and tool_name not in self.settings.allowed_tools:
            return False
        return True

    def evaluate(
        self,
        tool_name: str,
        *,
        is_read_only: bool = False,
        file_path: str | None = None,
        command: str | None = None,
    ) -> PermissionDecision:
        """评估单次工具调用是否被允许。

        Args:
            tool_name: 工具名称。
            is_read_only: 是否为只读操作。
            file_path: 文件路径（文件操作类工具需要）。
            command: shell 命令（bash 类工具需要）。

        Returns:
            PermissionDecision，包含 allowed、requires_confirmation 和 reason。
        """
        # 1. 敏感路径检查（不可覆盖，始终拒绝）
        if file_path and self._is_sensitive_path(file_path):
            return PermissionDecision(
                allowed=False,
                reason=f"Access to sensitive path denied: {file_path}",
            )

        # 2. 工具黑名单
        if tool_name in self.settings.denied_tools:
            return PermissionDecision(
                allowed=False,
                reason=f"Tool '{tool_name}' is in deny list",
            )

        # 3. 工具白名单
        if tool_name in self.settings.allowed_tools:
            return PermissionDecision(allowed=True)

        # 4. 路径规则检查
        if file_path:
            path_decision = self._check_path_rules(file_path)
            if path_decision is not None:
                return path_decision

        # 5. 命令黑名单（子串匹配）
        if command and self._is_denied_command(command):
            return PermissionDecision(
                allowed=False,
                reason=f"Command matches deny pattern",
            )

        # 6. 模式兜底
        return self._mode_fallback(tool_name, is_read_only)

    def _is_sensitive_path(self, file_path: str) -> bool:
        """检查路径是否匹配敏感路径模式。

        使用 Path.resolve() 规范化路径，防止 ../ 穿越。
        """
        # 规范化路径：消除 ../、~、符号链接
        normalized = str(Path(file_path).expanduser().resolve())
        for pattern in SENSITIVE_PATH_PATTERNS:
            expanded_pattern = str(Path(pattern).expanduser())
            if fnmatch.fnmatch(normalized, expanded_pattern):
                return True
            # 同时检查文件名匹配
            if fnmatch.fnmatch(Path(normalized).name, pattern):
                return True
        return False

    def _check_path_rules(self, file_path: str) -> PermissionDecision | None:
        """检查路径的允许/拒绝规则。无匹配时返回 None。

        使用 Path.resolve() 规范化路径，防止 ../ 穿越。
        """
        normalized = str(Path(file_path).expanduser().resolve())

        # 先检查拒绝路径
        for pattern in self.settings.denied_paths:
            expanded_pattern = str(Path(pattern).expanduser())
            if fnmatch.fnmatch(normalized, expanded_pattern):
                return PermissionDecision(
                    allowed=False,
                    reason=f"Path matches denied pattern: {pattern}",
                )

        # 再检查允许路径
        for pattern in self.settings.allowed_paths:
            expanded_pattern = str(Path(pattern).expanduser())
            if fnmatch.fnmatch(normalized, expanded_pattern):
                return PermissionDecision(allowed=True)

        return None

    def _is_denied_command(self, command: str) -> bool:
        """检查命令是否匹配黑名单模式（正则匹配）。"""
        import re
        for pattern in self.settings.denied_commands:
            try:
                if re.search(pattern, command, re.IGNORECASE):
                    return True
            except re.error:
                # 正则无效时降级为子串匹配
                if pattern in command:
                    return True
        return False

    def _mode_fallback(self, tool_name: str, is_read_only: bool) -> PermissionDecision:
        """根据权限模式做兜底判断。"""
        mode = self.settings.mode

        # FULL_AUTO：放行所有操作
        if mode == PermissionMode.FULL_AUTO:
            return PermissionDecision(allowed=True)

        # PLAN：只允许只读操作
        if mode == PermissionMode.PLAN:
            if is_read_only:
                return PermissionDecision(allowed=True)
            return PermissionDecision(
                allowed=False,
                reason="Plan mode: write operations are blocked",
            )

        # DEFAULT：只读放行，写操作需要确认
        if is_read_only:
            return PermissionDecision(allowed=True)

        return PermissionDecision(
            allowed=True,
            requires_confirmation=True,
            reason=f"Write operation requires confirmation",
        )
