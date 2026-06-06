"""反思中间件 — Agent 自我评估，持续进化。

功能：
- 多维度评估回答质量
- 评估结果持久化
- 自动注入历史经验

使用方式：
    from hz_agent_base.middleware.reflection import ReflectionMiddleware

    agent = create_agent(
        middleware=[
            ReflectionMiddleware(
                max_attempts=3,
                quality_threshold=0.7,
                memory_path=".reflection/",
            )
        ]
    )
"""

from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import HumanMessage

from ..reflection import (
    ReflectionCriteria,
    ReflectionEvaluator,
    ReflectionMemory,
)

logger = logging.getLogger(__name__)


class ReflectionMiddleware(AgentMiddleware):
    """反思中间件。

    在模型调用后评估回答质量，不满意则要求改进。

    Args:
        max_attempts: 最大重试次数，默认 3。
        quality_threshold: 质量阈值（0-1），默认 0.7。
        memory_path: 反思记忆存储路径，None 时不存储。
        task_type: 任务类型（自动选择评估维度）。
        dimensions: 自定义评估维度列表。
        model: 用于评估的模型，None 时使用主模型。
        inject_experience: 是否注入历史经验，默认 True。
    """

    def __init__(
        self,
        max_attempts: int = 3,
        quality_threshold: float = 0.7,
        memory_path: str | None = None,
        task_type: str | None = None,
        dimensions: list[str] | None = None,
        model: Any = None,
        inject_experience: bool = True,
    ):
        self.max_attempts = max_attempts
        self.quality_threshold = quality_threshold
        self.inject_experience = inject_experience
        self.model = model

        # 评估标准
        self.criteria = ReflectionCriteria(
            dimensions=dimensions,
            task_type=task_type,
            threshold=quality_threshold,
        )

        # 评估器
        self.evaluator = ReflectionEvaluator(
            criteria=self.criteria,
            model=model,
        )

        # 反思记忆
        self.memory = ReflectionMemory(memory_path) if memory_path else None

    def wrap_model_call(self, request, handler) -> Any:
        """调用模型后进行自我反思。"""
        # 注入历史经验
        if self.inject_experience and self.memory:
            request = self._inject_experience(request)

        # 提取用户问题
        question = self._extract_question(request.messages)

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

            # 评估回答质量
            result = self.evaluator.evaluate(question, answer)

            # 保存反思结果
            if self.memory:
                self.memory.save_reflection(
                    question=question,
                    answer=answer,
                    evaluation={
                        "dimensions": result.dimensions,
                        "overall": result.overall,
                        "issues": result.issues,
                        "suggestions": result.suggestions,
                    },
                    general_advice=result.suggestions,
                )

            # 质量达标，直接返回
            if result.passed:
                logger.info(
                    "Reflection passed (attempt %d/%d): %.2f >= %.2f",
                    attempt + 1, self.max_attempts,
                    result.overall, self.quality_threshold,
                )
                return response

            # 质量不达标，要求改进
            if attempt < self.max_attempts - 1:
                feedback = self._build_feedback(result)
                logger.info(
                    "Reflection failed (attempt %d/%d): %.2f < %.2f, issues: %s",
                    attempt + 1, self.max_attempts,
                    result.overall, self.quality_threshold,
                    result.issues,
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
            "Reflection max attempts reached (%d), returning last response",
            self.max_attempts,
        )
        return response

    def _extract_question(self, messages: list) -> str:
        """提取用户问题。"""
        for msg in reversed(messages):
            if getattr(msg, "type", "") == "human":
                content = getattr(msg, "content", "")
                if isinstance(content, str):
                    return content
        return ""

    def _inject_experience(self, request: Any) -> Any:
        """注入历史经验到系统提示词。"""
        if not self.memory:
            return request

        # 获取通用建议
        general_advice = self.memory.get_general_advice()
        if not general_advice:
            return request

        # 获取类似问题的反思
        question = self._extract_question(request.messages)
        similar = self.memory.get_similar_reflections(question, limit=2)

        # 构建经验文本
        experience_parts = []

        if general_advice:
            experience_parts.append("## 通用改进建议")
            for advice in general_advice[-5:]:  # 只取最近 5 条
                experience_parts.append(f"- {advice}")

        if similar:
            experience_parts.append("\n## 类似问题的历史反思")
            experience_parts.append(self.memory.format_similar_reflections(similar))

        if not experience_parts:
            return request

        # 注入系统提示词
        experience_text = "\n".join(experience_parts)
        current_system = request.system_prompt or ""
        return request.override(
            system_prompt=f"{current_system}\n\n{experience_text}"
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
