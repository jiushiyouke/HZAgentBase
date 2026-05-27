"""Hook definition schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .events import HookEvent


@dataclass
class HookDefinition:
    """Base hook definition.

    Attributes:
        event: The event that triggers this hook.
        matcher: fnmatch pattern to match tool names. None matches all.
        timeout_seconds: Maximum execution time.
        block_on_failure: Whether to block the operation if the hook fails.
    """

    event: HookEvent
    matcher: str | None = None
    timeout_seconds: float = 30.0
    block_on_failure: bool = False


@dataclass
class CommandHookDefinition(HookDefinition):
    """Hook that executes a shell command.

    The command receives the hook payload as environment variables:
    - HZ_HOOK_EVENT: The event name
    - HZ_HOOK_PAYLOAD: JSON-encoded payload
    """

    command: str = ""
    """Shell command to execute."""


@dataclass
class HttpHookDefinition(HookDefinition):
    """Hook that sends an HTTP POST request."""

    url: str = ""
    """URL to POST the payload to."""

    headers: dict[str, str] = field(default_factory=dict)
    """Additional HTTP headers."""


@dataclass
class PromptHookDefinition(HookDefinition):
    """Hook that uses an LLM to validate a condition.

    The LLM should respond with {"ok": true} or {"ok": false}.
    """

    prompt: str = ""
    """Prompt to send to the LLM for validation."""


@dataclass
class AgentHookDefinition(HookDefinition):
    """Hook that uses a sub-agent for deeper validation."""

    agent_prompt: str = ""
    """System prompt for the validation agent."""
