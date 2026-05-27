"""Coordinator middleware for multi-agent orchestration."""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from deepagents import SubAgent

from .worker import WorkerConfig
from .team import TeamRegistry


class CoordinatorMiddleware(AgentMiddleware):
    """Middleware that enables multi-agent coordination.

    Injects worker agent information into the coordinator's context
    and manages team-based orchestration.
    """

    def __init__(self, workers: list[WorkerConfig]):
        self.workers = workers
        self.team_registry = TeamRegistry()

        # Register workers into teams
        for worker in workers:
            self.team_registry.add_member(worker.team, worker.name)

        # Build sub-agents for Deep Agents
        self.subagents = [
            SubAgent(
                name=w.name,
                prompt=w.prompt,
                tools=w.tools if w.tools else None,
                model=w.model,
            )
            for w in workers
        ]

    def wrap_model_call(self, request: dict[str, Any], handler) -> dict[str, Any]:
        """Inject team context into the coordinator's system prompt."""
        # Build worker description
        worker_desc = self._build_worker_description()

        # Inject into system prompt
        current_system = request.get("system", "")
        request["system"] = (
            f"{current_system}\n\n"
            f"## Available Workers\n"
            f"{worker_desc}\n\n"
            f"## Team Status\n"
            f"{self.team_registry.get_status()}"
        )

        return handler(request)

    def _build_worker_description(self) -> str:
        """Build a description of available workers."""
        lines = []
        for w in self.workers:
            tools_str = ", ".join(w.tools) if w.tools else "all tools"
            lines.append(
                f"- **{w.name}**: {w.prompt[:100]}... "
                f"(tools: {tools_str}, team: {w.team})"
            )
        return "\n".join(lines)
