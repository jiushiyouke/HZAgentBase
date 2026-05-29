"""容错与韧性模块。

提供 Agent 运行时的容错能力：
- CancellationChecker: 用户取消检查协议
- StopCondition: 终止条件检查协议
- ResilientMiddleware: 重试、超时、取消、终止条件的统一中间件
"""

from .protocols import CancellationChecker, StopCondition
from .middleware import ResilientMiddleware

__all__ = [
    "CancellationChecker",
    "StopCondition",
    "ResilientMiddleware",
]
