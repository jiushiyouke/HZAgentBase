"""Worker configuration for multi-agent orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WorkerConfig:
    """Configuration for a worker agent.

    Attributes:
        name: Unique name for this worker.
        prompt: System prompt string (直接传入提示词文本)。
        prompt_dir: 提示词目录路径（自动加载 base.md + rules/）。
                   和 prompt 二选一，同时存在时 prompt_dir 优先。
        tools: List of tool names this worker can use.
        model: LLM model to use (defaults to coordinator's model).
        team: Team name for grouping workers.
        color: Color for terminal output.
    """

    name: str
    prompt: str = ""
    prompt_dir: str = ""
    tools: list[str] = field(default_factory=list)
    model: str | None = None
    team: str = "default"
    color: str = "blue"
    skills: list[str] = field(default_factory=list)
