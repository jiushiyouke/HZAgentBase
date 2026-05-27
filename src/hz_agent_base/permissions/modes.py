"""Permission modes."""

from enum import Enum


class PermissionMode(Enum):
    """Permission modes for tool execution."""

    DEFAULT = "default"
    """Confirm mutating operations (writes, edits, shell commands)."""

    PLAN = "plan"
    """Block all mutating operations. Read-only mode."""

    FULL_AUTO = "full_auto"
    """Allow all operations without confirmation."""
