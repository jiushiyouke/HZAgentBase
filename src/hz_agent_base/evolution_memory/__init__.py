"""进化记忆 — 从任务中学习，持续提升能力。"""

from .types import (
    TaskExperience,
    TaskResult,
    ReflectionResult,
    ReflectionCriteria,
    classify_task,
    TASK_PATTERNS,
    TASK_DIMENSIONS,
    DIMENSION_DESCRIPTIONS,
)
from .store import ExperienceStore
from .evaluator import TaskEvaluator, ReflectionEvaluator

__all__ = [
    # 类型
    "TaskExperience",
    "TaskResult",
    "ReflectionResult",
    "ReflectionCriteria",
    # 分类
    "classify_task",
    "TASK_PATTERNS",
    "TASK_DIMENSIONS",
    "DIMENSION_DESCRIPTIONS",
    # 评估器
    "TaskEvaluator",
    "ReflectionEvaluator",
    # 存储
    "ExperienceStore",
]
