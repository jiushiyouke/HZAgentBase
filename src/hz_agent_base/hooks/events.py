"""Hook event types."""

from enum import Enum


class HookEvent(Enum):
    """Events that trigger hooks."""

    SESSION_START = "session_start"
    """Fired when a new session begins."""

    SESSION_END = "session_end"
    """Fired when the session ends."""

    PRE_TOOL_USE = "pre_tool_use"
    """Fired before a tool is executed."""

    POST_TOOL_USE = "post_tool_use"
    """Fired after a tool is executed."""

    USER_PROMPT_SUBMIT = "user_prompt_submit"
    """Fired when the user submits a message."""

    STOP = "stop"
    """Fired when the agent stops."""
