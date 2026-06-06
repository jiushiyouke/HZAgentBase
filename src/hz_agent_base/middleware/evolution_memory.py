"""进化记忆中间件 — 从任务中学习，持续提升能力。

功能：
- 任务前：注入历史经验
- 任务后：评估结果 + 存储经验
- 质量不达标：重试（最多 N 次）

使用方式：
    from hz_agent_base.middleware.evolution_memory import EvolutionMemoryMiddleware

    agent = create_agent(
        middleware=[
            EvolutionMemoryMiddleware(
                memory_path=".evolution_memory/",
                max_attempts=3,
                quality_threshold=0.7,
            )
        ]
    )
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import HumanMessage

from ..evolution_memory import (
    TaskExperience,
    classify_task,
    ExperienceStore,
    TaskEvaluator,
    ReflectionEvaluator,
    ReflectionCriteria,
)

logger = logging.getLogger(__name__)


class EvolutionMemoryMiddleware(AgentMiddleware):
    """进化记忆中间件。

    从任务中学习，持续提升能力。

    Args:
        memory_path: 经验存储路径。
        retrieval_top_k: 检索相关经验数量。
        auto_classify: 是否自动分类任务。
        auto_evaluate: 是否自动评估结果。
        inject_experience: 是否注入历史经验。
        max_attempts: 质量不达标时的最大重试次数。
        quality_threshold: 质量阈值（0-1）。
        task_type: 任务类型（自动选择评估维度）。
        dimensions: 自定义评估维度列表。
        model: 用于评估和提取教训的模型（可选）。
    """

    def __init__(
        self,
        memory_path: str = ".evolution_memory/",
        retrieval_top_k: int = 5,
        auto_classify: bool = True,
        auto_evaluate: bool = True,
        inject_experience: bool = True,
        max_attempts: int = 3,
        quality_threshold: float = 0.7,
        task_type: str | None = None,
        dimensions: list[str] | None = None,
        model: Any = None,
    ):
        self.store = ExperienceStore(store_path=memory_path)
        self.task_evaluator = TaskEvaluator(model=model)
        self.retrieval_top_k = retrieval_top_k
        self.auto_classify = auto_classify
        self.auto_evaluate = auto_evaluate
        self.inject_experience = inject_experience
        self.max_attempts = max_attempts
        self.quality_threshold = quality_threshold
        self._start_time: float = 0.0
        self._current_task: str = ""

        # 反思评估器（用于质量评估和重试）
        self.reflection_criteria = ReflectionCriteria(
            dimensions=dimensions,
            task_type=task_type,
            threshold=quality_threshold,
        )
        self.reflection_evaluator = ReflectionEvaluator(
            criteria=self.reflection_criteria,
            model=model,
        )

    def wrap_model_call(self, request, handler) -> Any:
        """模型调用前注入经验，调用后评估并存储。"""
        # 提取当前任务
        self._current_task = self._extract_task(request.messages)

        # 自动分类任务类型
        task_type = "general"
        if self.auto_classify and self._current_task:
            task_type = classify_task(self._current_task)

        # 注入历史经验
        if self.inject_experience and self._current_task:
            request = self._inject_experience(request, task_type)

        # 记录开始时间
        self._start_time = time.time()

        # 调用模型（带重试）
        response = self._call_with_retry(request, handler)

        # 计算耗时
        duration = time.time() - self._start_time

        # 评估并存储经验
        if self.auto_evaluate and self._current_task:
            self._evaluate_and_store(
                task=self._current_task,
                task_type=task_type,
                messages=request.messages,
                response=response,
                duration=duration,
            )

        return response

    def _call_with_retry(self, request: Any, handler: Any) -> Any:
        """调用模型，质量不达标时重试。"""
        for attempt in range(self.max_attempts):
            # 调用模型
            response = handler(request)
            messages = response.get("messages", []) if isinstance(response, dict) else []

            if not messages:
                return response

            # 提取回答
            last_message = messages[-1]
            answer = getattr(last_message, "content", "")

            if not answer:
                return response

            # 评估质量
            result = self.reflection_evaluator.evaluate(self._current_task, answer)

            # 质量达标，直接返回
            if result.passed:
                logger.info(
                    "Quality check passed (attempt %d/%d): %.2f >= %.2f",
                    attempt + 1, self.max_attempts,
                    result.overall, self.quality_threshold,
                )
                return response

            # 质量不达标，要求改进
            if attempt < self.max_attempts - 1:
                feedback = self._build_feedback(result)
                logger.info(
                    "Quality check failed (attempt %d/%d): %.2f < %.2f",
                    attempt + 1, self.max_attempts,
                    result.overall, self.quality_threshold,
                )
                # 添加反馈让 Agent 改进
                request = request.override(
                    messages=[
                        *request.messages,
                        last_message,
                        HumanMessage(content=feedback),
                    ]
                )

        # 达到最大重试次数
        logger.warning(
            "Max attempts reached (%d), returning last response",
            self.max_attempts,
        )
        return response

    def _extract_task(self, messages: list) -> str:
        """从消息中提取任务描述。"""
        for msg in reversed(messages):
            if getattr(msg, "type", "") == "human":
                content = getattr(msg, "content", "")
                if isinstance(content, str):
                    return content
        return ""

    def _inject_experience(self, request: Any, task_type: str) -> Any:
        """注入历史经验到系统提示词。"""
        # 获取类似经验
        similar = self.store.get_similar_experiences(
            task=self._current_task,
            task_type=task_type,
            limit=self.retrieval_top_k,
        )

        # 获取成功策略
        strategies = self.store.get_successful_strategies(task_type)

        # 构建经验文本
        experience_parts = []

        if similar:
            experience_text = self.store.format_experiences_for_prompt(similar)
            experience_parts.append(experience_text)

        if strategies:
            experience_parts.append("## 成功策略\n")
            for i, strategy in enumerate(strategies[:3], 1):
                experience_parts.append(f"{i}. {strategy[:200]}")

        if not experience_parts:
            return request

        # 注入系统提示词
        experience_text = "\n".join(experience_parts)
        current_system = request.system_prompt or ""
        return request.override(
            system_prompt=f"{current_system}\n\n{experience_text}"
        )

    def _evaluate_and_store(
        self,
        task: str,
        task_type: str,
        messages: list,
        response: dict,
        duration: float,
    ) -> None:
        """评估任务结果并存储经验。"""
        # 评估任务结果
        result = self.task_evaluator.evaluate(
            task=task,
            messages=messages,
            response=response,
            duration=duration,
        )

        # 生成经验 ID
        experience_id = f"exp_{uuid.uuid4().hex[:8]}"

        # 创建经验记录
        experience = TaskExperience(
            id=experience_id,
            task=task,
            task_type=task_type,
            strategy=result.summary[:500],
            tools_used=result.tools_used,
            result="success" if result.success else "failure",
            duration=duration,
            issues=result.issues,
            lessons=result.lessons,
        )

        # 存储经验
        self.store.save_experience(experience)

        logger.info(
            "Task experience saved: id=%s, type=%s, result=%s, tools=%s",
            experience_id,
            task_type,
            experience.result,
            experience.tools_used,
        )

    def _build_feedback(self, result: Any) -> str:
        """构建改进反馈。"""
        lines = ["你的回答质量不达标，请改进：\n"]

        if result.issues:
            lines.append("扣分项：")
            for issue in result.issues:
                lines.append(f"- {issue}")

        if result.suggestions:
            lines.append("\n改进建议：")
            for suggestion in result.suggestions:
                lines.append(f"- {suggestion}")

        lines.append(f"\n当前分数：{result.overall:.2f}（阈值：{self.quality_threshold}）")
        lines.append("请重新回答，确保满足以上要求。")

        return "\n".join(lines)
