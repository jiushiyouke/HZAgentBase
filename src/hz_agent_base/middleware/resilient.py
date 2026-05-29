"""容错中间件 — 统一处理重试、取消、终止条件。

在 wrap_model_call 中按以下顺序检查：
1. 取消信号 → 立即返回
2. 终止条件 → 立即返回
3. 调用模型（带重试）
4. 返回结果后再检查终止条件
"""

from __future__ import annotations

import logging
import time
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware

from ..resilience.protocols import CancellationChecker, StopCondition

logger = logging.getLogger(__name__)


class ResilientMiddleware(AgentMiddleware):
    """容错中间件，提供重试、取消、终止条件能力。

    Args:
        cancellation_checker: 取消检查器（可选）。实现 CancellationChecker 协议。
        stop_condition: 终止条件（可选）。实现 StopCondition 协议。
        max_retries: LLM 调用失败时的最大重试次数。
        retry_base_delay: 重试基础延迟（秒），实际延迟 = base_delay * 2^attempt。
    """

    def __init__(
        self,
        cancellation_checker: CancellationChecker | None = None,
        stop_condition: StopCondition | None = None,
        max_retries: int = 2,
        retry_base_delay: float = 1.0,
    ):
        self.cancellation_checker = cancellation_checker
        self.stop_condition = stop_condition
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay

    def _get_thread_id(self, request: Any) -> str:
        """从 request 中提取 thread_id。"""
        # 尝试从 configurable 中获取
        config = getattr(request, "configurable", None)
        if config and isinstance(config, dict):
            return config.get("thread_id", "")
        # 降级
        return getattr(request, "thread_id", "") or ""

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        """容错的模型调用：取消检查 → 终止检查 → 重试调用 → 终止检查。"""
        thread_id = self._get_thread_id(request)

        # 1. 检查取消信号
        if self.cancellation_checker and thread_id:
            try:
                if self.cancellation_checker.is_cancelled(thread_id):
                    from langchain_core.messages import AIMessage
                    return {"messages": [AIMessage(content="请求已被取消。")]}
            except Exception as e:
                logger.warning("Cancellation check failed: %s", e)

        # 2. 检查终止条件（调用前）
        if self.stop_condition:
            try:
                messages = request.messages or []
                if self.stop_condition.should_stop(messages):
                    from langchain_core.messages import AIMessage
                    return {"messages": [AIMessage(content="已满足终止条件。")]}
            except Exception as e:
                logger.warning("Stop condition check failed: %s", e)

        # 3. 调用模型（带重试）
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = handler(request)

                # 4. 调用成功后检查终止条件
                if self.stop_condition:
                    try:
                        resp_messages = response.get("messages", []) if isinstance(response, dict) else []
                        all_messages = list(request.messages or []) + list(resp_messages)
                        if self.stop_condition.should_stop(all_messages):
                            return response  # 满足条件，直接返回，不继续下一轮
                    except Exception as e:
                        logger.warning("Stop condition check failed: %s", e)

                return response

            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = self.retry_base_delay * (2 ** attempt)
                    logger.warning(
                        "LLM call failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, self.max_retries + 1, delay, e,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "LLM call failed after %d attempts: %s",
                        self.max_retries + 1, e,
                    )

        # 全部重试失败，返回友好错误
        from langchain_core.messages import AIMessage
        return {
            "messages": [AIMessage(
                content=f"模型暂时不可用（已重试 {self.max_retries} 次），请稍后重试。"
            )],
        }
