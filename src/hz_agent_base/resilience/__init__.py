"""容错协议模块。

定义容错相关的协议接口，用户实现这些协议接入自己的机制：
- CancellationChecker: 取消检查（支持 Redis/DB/内存等）
- StopCondition: 终止条件（轮次限制/规则引擎/外部 API 等）

ResilientMiddleware 位于 middleware 包中。
"""

from .protocols import CancellationChecker, StopCondition

__all__ = [
    "CancellationChecker",
    "StopCondition",
]
