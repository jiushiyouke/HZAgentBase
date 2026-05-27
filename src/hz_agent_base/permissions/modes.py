"""权限模式定义。"""

from enum import Enum


class PermissionMode(Enum):
    """工具执行的权限模式。"""

    DEFAULT = "default"
    """默认模式：写操作需要用户确认。"""

    PLAN = "plan"
    """计划模式：阻止所有写操作，只读。"""

    FULL_AUTO = "full_auto"
    """全自动模式：允许所有操作，无需确认。"""
