"""权限系统包。

提供三种权限模式（DEFAULT / PLAN / FULL_AUTO），
通过 PermissionChecker 评估工具调用是否被允许。
"""

from .settings import PermissionSettings, PermissionMode
from .checker import PermissionChecker, PermissionDecision

__all__ = [
    "PermissionSettings",
    "PermissionMode",
    "PermissionChecker",
    "PermissionDecision",
]
