"""Hook registry - stores and manages hook definitions."""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from .events import HookEvent
from .schemas import HookDefinition


class HookRegistry:
    """Registry that stores hooks grouped by event type."""

    def __init__(self):
        self._hooks: dict[HookEvent, list[HookDefinition]] = defaultdict(list)

    def register(self, hook: HookDefinition) -> None:
        """Register a hook definition.

        Args:
            hook: The hook definition to register.
        """
        self._hooks[hook.event].append(hook)

    def register_many(self, hooks: Sequence[HookDefinition]) -> None:
        """Register multiple hook definitions."""
        for hook in hooks:
            self.register(hook)

    def get_hooks(self, event: HookEvent) -> list[HookDefinition]:
        """Get all hooks for a given event.

        Args:
            event: The event to get hooks for.

        Returns:
            List of hook definitions for the event.
        """
        return list(self._hooks.get(event, []))

    def clear(self, event: HookEvent | None = None) -> None:
        """Clear hooks for a specific event, or all hooks if event is None."""
        if event is None:
            self._hooks.clear()
        else:
            self._hooks.pop(event, None)
