"""Worker configuration for multi-agent orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WorkerConfig:
    """Configuration for a worker agent.

    Attributes:
        name: Unique name for this worker.
        prompt: System prompt for the worker.
        tools: List of tool names this worker can use.
        model: LLM model to use (defaults to coordinator's model).
        team: Team name for grouping workers.
        color: Color for terminal output.
    """

    name: str
    prompt: str = ""
    tools: list[str] = field(default_factory=list)
    model: str | None = None
    team: str = "default"
    color: str = "blue"
