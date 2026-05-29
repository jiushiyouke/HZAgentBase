"""容错协议定义。

用户实现这些协议来接入自己的取消和终止机制。
支持任意后端（Redis、数据库、API、内存等）。
"""

from __future__ import annotations

from typing import Protocol, Any, Sequence


class CancellationChecker(Protocol):
    """取消检查器协议 — 检查用户是否已取消当前请求。

    用户实现此协议接入自己的取消机制（Redis、数据库、内存等）。

    实现示例：

        import redis

        class RedisCancellationChecker:
            def __init__(self):
                self.redis = redis.Redis()

            def is_cancelled(self, thread_id: str) -> bool:
                return self.redis.exists(f"cancel:{thread_id}")

        # Web 端取消接口
        @app.post("/cancel/{thread_id}")
        def cancel(thread_id: str):
            redis.set(f"cancel:{thread_id}", "1", ex=300)
    """

    def is_cancelled(self, thread_id: str) -> bool:
        """检查指定请求是否已被取消。

        Args:
            thread_id: 请求的线程标识。

        Returns:
            True 表示已取消，Agent 应终止当前执行。
        """
        ...


class StopCondition(Protocol):
    """终止条件协议 — 检查 Agent 是否应停止循环。

    用户实现此协议接入自己的终止逻辑（规则引擎、数据库配置、外部 API 等）。

    实现示例：

        # 轮次限制
        class MaxRoundsCondition:
            def __init__(self, max_rounds: int = 5):
                self.max_rounds = max_rounds

            def should_stop(self, messages: list) -> bool:
                ai_count = sum(1 for m in messages if getattr(m, "type", "") == "ai")
                return ai_count >= self.max_rounds

        # 外部规则引擎
        class RuleEngineCondition:
            def should_stop(self, messages: list) -> bool:
                import requests
                resp = requests.post("http://rules/check", json={"messages": [...]})
                return resp.json().get("stop", False)
    """

    def should_stop(self, messages: list) -> bool:
        """检查是否应该终止 Agent 循环。

        Args:
            messages: 当前对话的消息列表。

        Returns:
            True 表示应终止，Agent 停止循环并返回已有结果。
        """
        ...
