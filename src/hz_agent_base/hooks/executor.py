"""Hook executor - runs hooks and aggregates results."""

from __future__ import annotations

import json
import subprocess
import fnmatch
from dataclasses import dataclass
from typing import Any

from .events import HookEvent
from .registry import HookRegistry
from .schemas import (
    HookDefinition,
    CommandHookDefinition,
    HttpHookDefinition,
    PromptHookDefinition,
    AgentHookDefinition,
)


@dataclass
class HookResult:
    """Result of a single hook execution."""

    success: bool
    blocked: bool = False
    reason: str = ""
    output: str = ""


@dataclass
class AggregatedHookResult:
    """Aggregated result of all hooks for an event."""

    results: list[HookResult]

    @property
    def blocked(self) -> bool:
        """Whether any hook blocked the operation."""
        return any(r.blocked for r in self.results)

    @property
    def reasons(self) -> list[str]:
        """List of blocking reasons."""
        return [r.reason for r in self.results if r.blocked]


class HookExecutor:
    """Executes hooks and aggregates results."""

    def __init__(self, registry: HookRegistry):
        self.registry = registry

    def execute(
        self,
        event: HookEvent,
        payload: dict[str, Any],
        tool_name: str | None = None,
    ) -> AggregatedHookResult:
        """Execute all matching hooks for an event.

        Args:
            event: The event to execute hooks for.
            payload: The event payload.
            tool_name: Tool name for matcher filtering.

        Returns:
            AggregatedHookResult with results from all hooks.
        """
        hooks = self.registry.get_hooks(event)
        results: list[HookResult] = []

        for hook in hooks:
            # Check matcher pattern
            if hook.matcher and tool_name:
                if not fnmatch.fnmatch(tool_name, hook.matcher):
                    continue

            result = self._execute_single(hook, payload)
            results.append(result)

            # Short-circuit if blocked
            if result.blocked and hook.block_on_failure:
                break

        return AggregatedHookResult(results=results)

    def _execute_single(
        self,
        hook: HookDefinition,
        payload: dict[str, Any],
    ) -> HookResult:
        """Execute a single hook."""
        if isinstance(hook, CommandHookDefinition):
            return self._execute_command(hook, payload)
        elif isinstance(hook, HttpHookDefinition):
            return self._execute_http(hook, payload)
        elif isinstance(hook, PromptHookDefinition):
            return self._execute_prompt(hook, payload)
        elif isinstance(hook, AgentHookDefinition):
            return self._execute_agent(hook, payload)
        else:
            return HookResult(success=False, reason=f"Unknown hook type: {type(hook)}")

    def _execute_command(
        self,
        hook: CommandHookDefinition,
        payload: dict[str, Any],
    ) -> HookResult:
        """Execute a shell command hook."""
        import os

        env = os.environ.copy()
        env["HZ_HOOK_EVENT"] = hook.event.value
        env["HZ_HOOK_PAYLOAD"] = json.dumps(payload)

        try:
            result = subprocess.run(
                hook.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=hook.timeout_seconds,
                env=env,
            )

            if result.returncode != 0:
                blocked = hook.block_on_failure
                return HookResult(
                    success=False,
                    blocked=blocked,
                    reason=f"Command hook failed: {result.stderr}",
                    output=result.stderr,
                )

            return HookResult(success=True, output=result.stdout)

        except subprocess.TimeoutExpired:
            return HookResult(
                success=False,
                blocked=hook.block_on_failure,
                reason=f"Command hook timed out after {hook.timeout_seconds}s",
            )
        except Exception as e:
            return HookResult(
                success=False,
                blocked=hook.block_on_failure,
                reason=f"Command hook error: {str(e)}",
            )

    def _execute_http(
        self,
        hook: HttpHookDefinition,
        payload: dict[str, Any],
    ) -> HookResult:
        """Execute an HTTP hook."""
        try:
            import httpx

            response = httpx.post(
                hook.url,
                json=payload,
                headers=hook.headers,
                timeout=hook.timeout_seconds,
            )

            if response.status_code >= 400:
                return HookResult(
                    success=False,
                    blocked=hook.block_on_failure,
                    reason=f"HTTP hook returned {response.status_code}",
                )

            # Check response body for blocking
            try:
                data = response.json()
                if isinstance(data, dict) and data.get("ok") is False:
                    return HookResult(
                        success=True,
                        blocked=True,
                        reason=data.get("reason", "HTTP hook blocked"),
                    )
            except Exception:
                pass

            return HookResult(success=True)

        except Exception as e:
            return HookResult(
                success=False,
                blocked=hook.block_on_failure,
                reason=f"HTTP hook error: {str(e)}",
            )

    def _execute_prompt(
        self,
        hook: PromptHookDefinition,
        payload: dict[str, Any],
    ) -> HookResult:
        """Execute a prompt-based hook (placeholder - needs LLM integration)."""
        # TODO: Integrate with LLM to validate
        return HookResult(success=True)

    def _execute_agent(
        self,
        hook: AgentHookDefinition,
        payload: dict[str, Any],
    ) -> HookResult:
        """Execute an agent-based hook (placeholder - needs agent integration)."""
        # TODO: Integrate with sub-agent for validation
        return HookResult(success=True)
