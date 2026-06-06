"""进化记忆 — 类型定义。

定义经验记录、评估结果、任务分类等核心类型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ============================================================
# 任务分类
# ============================================================

# 任务类型 → 触发关键词（支持单关键字和双关键字组合）
TASK_PATTERNS: dict[str, list[tuple[str, ...]]] = {
    "code_analysis": [
        ("分析", "代码"), ("代码", "结构"), ("代码", "审查"),
        ("review",), ("code", "analysis"),
    ],
    "code_writing": [
        ("写", "代码"), ("写", "脚本"), ("实现", "功能"),
        ("修复", "bug"), ("fix",), ("implement",),
        ("编程",), ("script",), ("python", "写"),
        ("写", "python"), ("写", "脚本"),
    ],
    "research": [
        ("研究",), ("调研",), ("对比",),
        ("compare",), ("research",),
    ],
    "explanation": [
        ("解释",), ("说明",), ("介绍",), ("explain",),
    ],
    "data_analysis": [
        ("分析", "数据"), ("统计",), ("图表",),
        ("data", "analysis"),
    ],
    "refactor": [
        ("重构",), ("优化",), ("refactor",), ("optimize",),
    ],
    "testing": [
        ("测试",), ("单元测试",), ("test",),
    ],
    "documentation": [
        ("文档",), ("注释",), ("document",),
    ],
}


def _match_keywords(text: str, keywords: tuple[str, ...]) -> bool:
    """检查文本是否匹配关键词组合。"""
    text_lower = text.lower()
    return all(kw.lower() in text_lower for kw in keywords)


def classify_task(text: str) -> str:
    """根据文本自动分类任务类型。

    Args:
        text: 任务描述文本。

    Returns:
        任务类型字符串。
    """
    for task_type, keyword_tuples in TASK_PATTERNS.items():
        for keywords in keyword_tuples:
            if _match_keywords(text, keywords):
                return task_type
    return "general"


# ============================================================
# 经验记录
# ============================================================

@dataclass
class TaskExperience:
    """任务经验记录。

    Attributes:
        id: 经验 ID。
        task: 任务描述。
        task_type: 任务类型。
        strategy: 采取的策略。
        tools_used: 使用的工具列表。
        result: 任务结果（success/failure）。
        duration: 耗时（秒）。
        issues: 遇到的问题。
        lessons: 学到的教训。
        timestamp: 记录时间。
        tags: 标签列表。
    """

    id: str
    task: str
    task_type: str
    strategy: str
    tools_used: list[str] = field(default_factory=list)
    result: str = "success"
    duration: float = 0.0
    issues: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: list[str] = field(default_factory=list)


# ============================================================
# 评估结果
# ============================================================

@dataclass
class TaskResult:
    """任务评估结果。

    Attributes:
        success: 是否成功。
        tools_used: 使用的工具列表。
        summary: 任务摘要。
        issues: 遇到的问题。
        lessons: 学到的教训。
    """

    success: bool
    tools_used: list[str] = field(default_factory=list)
    summary: str = ""
    issues: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)


@dataclass
class ReflectionResult:
    """反思评估结果。

    Attributes:
        dimensions: 各维度分数。
        overall: 总体分数。
        issues: 扣分原因列表。
        suggestions: 改进建议列表。
        passed: 是否通过质量阈值。
    """

    dimensions: dict[str, float] = field(default_factory=dict)
    overall: float = 0.0
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    passed: bool = True


# ============================================================
# 评估维度
# ============================================================

# 任务类型 → 推荐评估维度
TASK_DIMENSIONS: dict[str, list[str]] = {
    "code": ["correctness", "efficiency", "readability", "completeness"],
    "writing": ["clarity", "coherence", "completeness", "engagement"],
    "explanation": ["accuracy", "clarity", "depth", "examples"],
    "analysis": ["accuracy", "depth", "relevance", "evidence"],
    "general": ["completeness", "accuracy", "relevance", "clarity"],
}

# 维度描述（用于评估提示词）
DIMENSION_DESCRIPTIONS: dict[str, str] = {
    "completeness": "完整性：是否回答了用户的所有问题",
    "accuracy": "准确性：信息是否正确",
    "relevance": "相关性：是否紧扣主题",
    "clarity": "清晰度：是否易于理解",
    "depth": "深度：是否足够详细",
    "examples": "示例：是否包含具体示例",
    "correctness": "正确性：代码是否正确运行",
    "efficiency": "效率：代码是否高效",
    "readability": "可读性：代码是否易于理解",
    "coherence": "连贯性：文章是否逻辑清晰",
    "engagement": "吸引力：内容是否引人入胜",
    "evidence": "证据：是否有充分的证据支持",
}


@dataclass
class ReflectionCriteria:
    """反思评估标准。

    Args:
        dimensions: 评估维度列表。
        task_type: 任务类型（自动选择维度）。
        threshold: 质量阈值（0-1）。
    """

    dimensions: list[str] = field(default_factory=list)
    task_type: str | None = None
    threshold: float = 0.7

    def __post_init__(self):
        """初始化后处理。"""
        if not self.dimensions:
            if self.task_type and self.task_type in TASK_DIMENSIONS:
                self.dimensions = TASK_DIMENSIONS[self.task_type]
            else:
                self.dimensions = TASK_DIMENSIONS["general"]

    def get_dimension_description(self, dimension: str) -> str:
        """获取维度描述。"""
        return DIMENSION_DESCRIPTIONS.get(dimension, dimension)

    def to_prompt(self) -> str:
        """生成评估提示词。"""
        lines = ["请从以下维度评估回答质量（0-1 分）：\n"]
        for i, dim in enumerate(self.dimensions, 1):
            desc = self.get_dimension_description(dim)
            lines.append(f"{i}. {desc}")
        lines.append(f"\n质量阈值：{self.threshold}")
        return "\n".join(lines)
