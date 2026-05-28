"""Coordinator middleware for multi-agent orchestration."""

from __future__ import annotations

from typing import Any, Sequence

from langchain.agents.middleware.types import AgentMiddleware
from deepagents import SubAgent

from .worker import WorkerConfig
from .team import TeamRegistry
from ..prompts.manager import load_prompt


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

    def __init__(
        self,
        workers: list[WorkerConfig],
        shared_rules: list[str] | None = None,
    ):
        self.workers = workers
        self.shared_rules = shared_rules or []
        self.team_registry = TeamRegistry()

        # 将 worker 注册到对应的 team
        for worker in workers:
            self.team_registry.add_member(worker.team, worker.name)

        # 构建 Deep Agents 的 subagent 列表
        # 注意：model 为 None 时不传入，让 deepagents 使用主 agent 的 model
        self.subagents: list[SubAgent] = []
        for w in workers:
            sub: SubAgent = SubAgent(
                name=w.name,
                description=w.prompt[:80] if w.prompt else w.name,
                system_prompt=self._resolve_prompt(w),
                tools=w.tools if w.tools else None,
            )
            if w.model is not None:
                sub["model"] = w.model
            self.subagents.append(sub)

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

    def _resolve_prompt(self, worker: WorkerConfig) -> str:
        """解析 worker 的提示词。

        优先级：prompt_dir > prompt 字符串。
        prompt_dir 模式下自动加载 base.md + rules/ + 共享规则。
        """
        if worker.prompt_dir:
            return load_prompt(worker.prompt_dir, shared_rules=self.shared_rules)
        return worker.prompt

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
