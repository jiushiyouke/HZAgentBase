"""Hook 事件类型定义。"""

from enum import Enum


class HookEvent(Enum):
    """触发 Hook 的生命周期事件。"""

    SESSION_START = "session_start"
    """新会话开始时触发。"""

    SESSION_END = "session_end"
    """会话结束时触发。"""

    PRE_TOOL_USE = "pre_tool_use"
    """工具执行前触发。"""

    POST_TOOL_USE = "post_tool_use"
    """工具执行后触发。"""

    USER_PROMPT_SUBMIT = "user_prompt_submit"
    """用户提交消息时触发。"""
