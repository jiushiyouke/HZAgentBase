"""进化记忆 — 评估器。

包含两个评估器：
- TaskEvaluator: 评估任务执行结果（成功/失败、使用的工具、教训）
- ReflectionEvaluator: 评估回答质量（多维度打分、是否达标）
"""

from __future__ import annotations

import json
import logging
from typing import Any, Sequence

from langchain_core.messages import HumanMessage

from .types import TaskResult, ReflectionResult, ReflectionCriteria

logger = logging.getLogger(__name__)


# ============================================================
# 任务评估器
# ============================================================

class TaskEvaluator:
    """任务评估器 — 评估任务执行结果。

    Args:
        model: 用于提取教训的 LLM 模型（可选）。
    """

    def __init__(self, model: Any = None):
        self.model = model

    def evaluate(
        self,
        task: str,
        messages: list,
        response: dict,
        duration: float = 0.0,
    ) -> TaskResult:
        """评估任务执行结果。"""
        tools_used = self._extract_tools(response)
        has_error = self._check_error(response)
        summary = self._extract_summary(response)

        lessons = []
        if self.model and not has_error:
            lessons = self._extract_lessons(task, summary)

        return TaskResult(
            success=not has_error,
            tools_used=tools_used,
            summary=summary,
            issues=[] if not has_error else ["任务执行出错"],
            lessons=lessons,
        )

    def _extract_tools(self, response: dict) -> list[str]:
        """从响应中提取使用的工具。"""
        tools = []
        messages = response.get("messages", []) if isinstance(response, dict) else []
        for msg in messages:
            tool_calls = getattr(msg, "tool_calls", None) or []
            for tc in tool_calls:
                name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                if name and name not in tools:
                    tools.append(name)
        return tools

    def _check_error(self, response: dict) -> bool:
        """检查响应中是否有错误。"""
        messages = response.get("messages", []) if isinstance(response, dict) else []
        for msg in messages:
            content = getattr(msg, "content", "")
            if isinstance(content, str):
                error_indicators = ["error", "Error", "错误", "失败", "failed"]
                if any(indicator in content for indicator in error_indicators):
                    if "no error" not in content.lower():
                        return True
        return False

    def _extract_summary(self, response: dict) -> str:
        """从响应中提取摘要。"""
        messages = response.get("messages", []) if isinstance(response, dict) else []
        for msg in reversed(messages):
            content = getattr(msg, "content", "")
            if content and getattr(msg, "type", "") == "ai":
                return content[:500] if isinstance(content, str) else str(content)[:500]
        return ""

    def _extract_lessons(self, task: str, summary: str) -> list[str]:
        """使用 LLM 提取教训。"""
        if not self.model or not summary:
            return []

        prompt = f"""根据以下任务执行情况，提取 1-3 条可复用的经验教训：

任务：{task}
执行摘要：{summary}

要求：
1. 教训要具体、可操作
2. 适用于类似任务
3. 每条教训不超过 50 字

请返回 JSON 数组：["教训1", "教训2"]"""

        try:
            response = self.model.invoke([HumanMessage(content=prompt)])
            content = getattr(response, "content", "")

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            lessons = json.loads(content.strip())
            if isinstance(lessons, list):
                return [str(l) for l in lessons[:3]]
        except Exception as e:
            logger.warning("Failed to extract lessons: %s", e)

        return []


# ============================================================
# 反思评估器
# ============================================================

# 评估提示词模板
REFLECTION_PROMPT = """请评估以下回答的质量。

{criteria}

用户问题：
{question}

Agent 回答：
{answer}

请严格按 JSON 格式返回评估结果，不要添加其他内容。
返回格式：{{"dimensions": {{"completeness": 0.8, ...}}, "overall": 0.76, "issues": ["问题1"], "suggestions": ["建议1"]}}"""


class ReflectionEvaluator:
    """反思评估器 — 调用 LLM 对回答进行多维度评估。

    Args:
        criteria: 评估标准。
        model: 用于评估的 LLM 模型。
    """

    def __init__(
        self,
        criteria: ReflectionCriteria,
        model: Any = None,
    ):
        self.criteria = criteria
        self.model = model

    def evaluate(self, question: str, answer: str) -> ReflectionResult:
        """评估回答质量。"""
        if not self.model:
            return self._default_result()

        prompt = REFLECTION_PROMPT.format(
            criteria=self.criteria.to_prompt(),
            question=question[:500],
            answer=answer[:1000],
        )

        try:
            response = self.model.invoke([HumanMessage(content=prompt)])
            content = getattr(response, "content", "")
            return self._parse_result(content)
        except Exception as e:
            logger.error("Reflection evaluation failed: %s", e)
            return self._default_result()

    def _parse_result(self, content: str) -> ReflectionResult:
        """解析 LLM 返回的评估结果。"""
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())

            dimensions = data.get("dimensions", {})
            overall = data.get("overall", 0.0)
            issues = data.get("issues", [])
            suggestions = data.get("suggestions", [])

            return ReflectionResult(
                dimensions=dimensions,
                overall=overall,
                issues=issues,
                suggestions=suggestions,
                passed=overall >= self.criteria.threshold,
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to parse reflection result: %s", e)
            return self._default_result()

    def _default_result(self) -> ReflectionResult:
        """返回默认评估结果（通过）。"""
        return ReflectionResult(
            dimensions={dim: 1.0 for dim in self.criteria.dimensions},
            overall=1.0,
            issues=[],
            suggestions=[],
            passed=True,
        )
