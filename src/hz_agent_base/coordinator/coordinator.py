"""Coordinator middleware for multi-agent orchestration."""

from __future__ import annotations

from typing import Any, Sequence

from langchain.agents.middleware.types import AgentMiddleware
from deepagents import SubAgent

from .worker import WorkerConfig
from .team import TeamRegistry


class CoordinatorMiddleware(AgentMiddleware):
    """Middleware that enables multi-agent coordination.

    Injects worker agent information into the coordinator's context
    and manages team-based orchestration.

    使用方式：
        workers = [
            WorkerConfig(name="researcher", prompt="研究助手", tools=["web_search"]),
            WorkerConfig(name="coder", prompt="编程助手", tools=["write_file"]),
        ]
        agent = create_agent(workers=workers)
    """

    def __init__(self, workers: list[WorkerConfig]):
        self.workers = workers
        self.team_registry = TeamRegistry()

        # 将 worker 注册到对应的 team
        for worker in workers:
            self.team_registry.add_member(worker.team, worker.name)

        # 构建 Deep Agents 的 subagent 列表
        self.subagents: list[SubAgent] = [
            SubAgent(
                name=w.name,
                prompt=w.prompt,
                tools=w.tools if w.tools else None,
                model=w.model,
            )
            for w in workers
        ]

    def wrap_model_call(self, request, handler) -> Any:
        """将 worker 信息注入协调者的系统提示词。"""
        worker_desc = self._build_worker_description()
        team_status = self.team_registry.get_status()

        current_system = request.system_prompt or ""
        new_request = request.override(
            system_prompt=(
                f"{current_system}\n\n"
                f"## Available Workers\n"
                f"{worker_desc}\n\n"
                f"## Team Status\n"
                f"{team_status}"
            )
        )
        return handler(new_request)

    def _build_worker_description(self) -> str:
        """构建 worker 描述文本。"""
        lines = []
        for w in self.workers:
            tools_str = ", ".join(w.tools) if w.tools else "all tools"
            # 截断过长的 prompt，避免注入过多内容
            short_prompt = w.prompt[:100] + "..." if len(w.prompt) > 100 else w.prompt
            lines.append(
                f"- **{w.name}**: {short_prompt} "
                f"(tools: {tools_str}, team: {w.team})"
            )
        return "\n".join(lines)
