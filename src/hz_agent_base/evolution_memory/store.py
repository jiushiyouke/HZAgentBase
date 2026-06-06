"""Agent 进化 — 经验存储和检索。

存储任务经验，检索相关经验用于进化。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .types import TaskExperience

logger = logging.getLogger(__name__)


class ExperienceStore:
    """经验存储 — 管理任务经验的持久化和检索。

    Args:
        store_path: 存储路径。
        max_experiences: 最大经验数。
    """

    def __init__(
        self,
        store_path: str = ".agent_evolution/",
        max_experiences: int = 1000,
    ):
        self.path = Path(store_path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.max_experiences = max_experiences
        self._experiences_file = self.path / "experiences.jsonl"

    def save_experience(self, experience: TaskExperience) -> None:
        """保存任务经验。

        Args:
            experience: 任务经验记录。
        """
        entry = {
            "id": experience.id,
            "task": experience.task[:200],
            "task_type": experience.task_type,
            "strategy": experience.strategy[:500],
            "tools_used": experience.tools_used,
            "result": experience.result,
            "duration": experience.duration,
            "issues": experience.issues,
            "lessons": experience.lessons,
            "timestamp": experience.timestamp,
            "tags": experience.tags,
        }

        with open(self._experiences_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_experiences(
        self,
        task_type: str | None = None,
        limit: int = 100,
    ) -> list[TaskExperience]:
        """获取经验列表。

        Args:
            task_type: 按任务类型过滤。
            limit: 最大返回数。

        Returns:
            经验列表。
        """
        if not self._experiences_file.exists():
            return []

        experiences = []
        with open(self._experiences_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if task_type and entry.get("task_type") != task_type:
                        continue
                    experiences.append(TaskExperience(**entry))
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

        # 按时间倒序
        experiences.sort(key=lambda x: x.timestamp, reverse=True)
        return experiences[:limit]

    def get_similar_experiences(
        self,
        task: str,
        task_type: str | None = None,
        limit: int = 5,
    ) -> list[TaskExperience]:
        """获取类似任务的经验。

        Args:
            task: 当前任务描述。
            task_type: 任务类型。
            limit: 最大返回数。

        Returns:
            按相关性排序的经验列表。
        """
        experiences = self.get_experiences(task_type=task_type)
        if not experiences:
            return []

        # 计算相似度（关键词重叠）
        task_words = set(task.lower().split())
        scored = []
        for exp in experiences:
            exp_words = set(exp.task.lower().split())
            overlap = len(task_words & exp_words)
            # 成功经验权重更高
            score = overlap * (1.5 if exp.result == "success" else 1.0)
            if score > 0:
                scored.append((score, exp))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [exp for _, exp in scored[:limit]]

    def get_successful_strategies(self, task_type: str) -> list[str]:
        """获取某类任务的成功策略。

        Args:
            task_type: 任务类型。

        Returns:
            成功策略列表。
        """
        experiences = self.get_experiences(task_type=task_type)
        strategies = []
        for exp in experiences:
            if exp.result == "success" and exp.strategy:
                strategies.append(exp.strategy)
        return strategies[:10]  # 最多返回 10 条

    def get_common_lessons(self, task_type: str | None = None) -> list[str]:
        """获取常见教训。

        Args:
            task_type: 任务类型（可选）。

        Returns:
            教训列表。
        """
        experiences = self.get_experiences(task_type=task_type)
        lessons = []
        for exp in experiences:
            lessons.extend(exp.lessons)
        # 去重
        return list(set(lessons))[:10]

    def format_experiences_for_prompt(self, experiences: list[TaskExperience]) -> str:
        """格式化经验用于注入系统提示词。

        Args:
            experiences: 经验列表。

        Returns:
            格式化的经验文本。
        """
        if not experiences:
            return ""

        lines = ["## 历史经验（Agent 进化记忆）\n"]
        for i, exp in enumerate(experiences, 1):
            lines.append(f"### 经验 {i}: {exp.task_type}")
            lines.append(f"- 任务：{exp.task[:100]}")
            if exp.strategy:
                lines.append(f"- 策略：{exp.strategy[:200]}")
            if exp.tools_used:
                lines.append(f"- 工具：{', '.join(exp.tools_used)}")
            lines.append(f"- 结果：{exp.result}")
            if exp.lessons:
                lines.append(f"- 教训：{', '.join(exp.lessons)}")
            lines.append("")

        return "\n".join(lines)
