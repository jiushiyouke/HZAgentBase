"""多 Agent 编排包。

Coordinator 模式：一个协调者管理多个 Worker Agent，
每个 Worker 有独立的角色、工具和提示词。
"""

from .worker import WorkerConfig
from .team import TeamRegistry
from .coordinator import CoordinatorMiddleware

__all__ = [
    "WorkerConfig",
    "TeamRegistry",
    "CoordinatorMiddleware",
]
