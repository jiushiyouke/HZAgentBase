"""Permission checker - evaluates whether tool calls are allowed."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .modes import PermissionMode
from .settings import PermissionSettings, SENSITIVE_PATH_PATTERNS


@dataclass(frozen=True)
class PermissionDecision:
    """Result of a permission check."""

    allowed: bool
    requires_confirmation: bool = False
    reason: str = ""


class PermissionChecker:
    """Evaluates tool calls against permission rules.

    Evaluation order:
    1. Sensitive path patterns → always deny
    2. Tool deny list → deny
    3. Tool allow list → allow
    4. Path rules (denied_paths, allowed_paths)
    5. Command deny patterns
    6. Mode-based fallback
    """

    def __init__(self, settings: PermissionSettings):
        self.settings = settings

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Quick check if a tool is allowed by deny/allow lists.

        Args:
            tool_name: Name of the tool.

        Returns:
            True if the tool is not denied and either in the allow list
            or the allow list is empty.
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
        """Evaluate whether a tool call is allowed.

        Args:
            tool_name: Name of the tool being called.
            is_read_only: Whether the tool call is read-only.
            file_path: File path if the tool operates on files.
            command: Shell command if the tool executes commands.

        Returns:
            PermissionDecision with allowed, requires_confirmation, and reason.
        """
        # 1. Check sensitive paths (always deny, cannot be overridden)
        if file_path and self._is_sensitive_path(file_path):
            return PermissionDecision(
                allowed=False,
                reason=f"Access to sensitive path denied: {file_path}",
            )

        # 2. Check tool deny list
        if tool_name in self.settings.denied_tools:
            return PermissionDecision(
                allowed=False,
                reason=f"Tool '{tool_name}' is in deny list",
            )

        # 3. Check tool allow list
        if tool_name in self.settings.allowed_tools:
            return PermissionDecision(allowed=True)

        # 4. Check path rules
        if file_path:
            path_decision = self._check_path_rules(file_path)
            if path_decision is not None:
                return path_decision

        # 5. Check command deny patterns
        if command and self._is_denied_command(command):
            return PermissionDecision(
                allowed=False,
                reason=f"Command matches deny pattern",
            )

        # 6. Mode-based fallback
        return self._mode_fallback(tool_name, is_read_only)

    def _is_sensitive_path(self, file_path: str) -> bool:
        """Check if path matches sensitive path patterns."""
        expanded = str(Path(file_path).expanduser())
        for pattern in SENSITIVE_PATH_PATTERNS:
            expanded_pattern = str(Path(pattern).expanduser())
            if fnmatch.fnmatch(expanded, expanded_pattern):
                return True
            # Also check basename match
            if fnmatch.fnmatch(file_path, pattern):
                return True
        return False

    def _check_path_rules(self, file_path: str) -> PermissionDecision | None:
        """Check path-based allow/deny rules. Returns None if no match."""
        # Check denied paths first
        for pattern in self.settings.denied_paths:
            if fnmatch.fnmatch(file_path, pattern):
                return PermissionDecision(
                    allowed=False,
                    reason=f"Path matches denied pattern: {pattern}",
                )

        # Check allowed paths
        for pattern in self.settings.allowed_paths:
            if fnmatch.fnmatch(file_path, pattern):
                return PermissionDecision(allowed=True)

        return None

    def _is_denied_command(self, command: str) -> bool:
        """Check if command matches deny patterns."""
        for pattern in self.settings.denied_commands:
            if pattern in command:
                return True
        return False

    def _mode_fallback(self, tool_name: str, is_read_only: bool) -> PermissionDecision:
        """Apply mode-based fallback rules."""
        mode = self.settings.mode

        if mode == PermissionMode.FULL_AUTO:
            return PermissionDecision(allowed=True)

        if mode == PermissionMode.PLAN:
            if is_read_only:
                return PermissionDecision(allowed=True)
            return PermissionDecision(
                allowed=False,
                reason="Plan mode: write operations are blocked",
            )

        # DEFAULT mode
        if is_read_only:
            return PermissionDecision(allowed=True)

        return PermissionDecision(
            allowed=True,
            requires_confirmation=True,
            reason=f"Write operation requires confirmation",
        )
