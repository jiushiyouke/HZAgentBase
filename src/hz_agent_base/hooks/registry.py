"""Hook 注册表 — 存储和管理 Hook 定义。"""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from .events import HookEvent
from .schemas import HookDefinition


class HookRegistry:
    """按事件类型分组存储 Hook 定义的注册表。"""

    def __init__(self):
        # 按事件类型分组存储
        self._hooks: dict[HookEvent, list[HookDefinition]] = defaultdict(list)

    def register(self, hook: HookDefinition) -> None:
        """注册一个 Hook 定义。

        Args:
            hook: 要注册的 Hook 定义。
        """
        self._hooks[hook.event].append(hook)

    def register_many(self, hooks: Sequence[HookDefinition]) -> None:
        """批量注册多个 Hook 定义。"""
        for hook in hooks:
            self.register(hook)

    def get_hooks(self, event: HookEvent) -> list[HookDefinition]:
        """获取指定事件的所有 Hook。

        Args:
            event: 事件类型。

        Returns:
            该事件对应的 Hook 定义列表。
        """
        return list(self._hooks.get(event, []))

    def clear(self, event: HookEvent | None = None) -> None:
        """清除指定事件的 Hook，或清除所有 Hook（event=None 时）。"""
        if event is None:
            self._hooks.clear()
        else:
            self._hooks.pop(event, None)
