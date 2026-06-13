"""Human-in-the-loop 中间件 — 危险操作需人工确认。

功能：
- 工具调用前检查是否需要人工审批
- 支持同步审批（控制台输入）
- 支持自定义审批回调

使用方式：
    from hz_agent_base.middleware.human_approval import HumanApprovalMiddleware
    from hz_agent_base.human_approval import ApprovalRule

    agent = create_agent(
        middleware=[
            HumanApprovalMiddleware(
                rules=[ApprovalRule(tools=["bash", "delete_file"])],
            )
        ]
    )
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage

from ..human_approval import ApprovalRule, ConsoleApprovalCallback

logger = logging.getLogger(__name__)


class HumanApprovalMiddleware(AgentMiddleware):
    """Human-in-the-loop 中间件。

    在工具执行前检查是否需要人工审批。

    Args:
        rules: 审批规则列表。
        callback: 审批回调。None 时使用控制台审批。
        default_approve: 无回调时是否默认批准（用于测试）。
    """

    def __init__(
        self,
        rules: list[ApprovalRule] | None = None,
        callback: Any = None,
        default_approve: bool = False,
    ):
        self.rules = rules or []
        self.callback = callback
        self.default_approve = default_approve

    def wrap_tool_call(self, request, handler) -> Any:
        """工具执行前检查是否需要审批。"""
        tool_call = request.tool_call
        tool_name = self._get_tool_name(tool_call)
        args = self._get_tool_args(tool_call)

        # 检查是否需要审批
        matched_rule = self._find_matching_rule(tool_name, args)
        if matched_rule:
            try:
                approved = self._request_approval(tool_name, args, matched_rule)
            except Exception as e:
                logger.error("Approval request failed: %s", e)
                approved = self.default_approve

            if not approved:
                tool_call_id = self._get_tool_call_id(tool_call)
                logger.info("Tool call rejected by user: %s", tool_name)
                return ToolMessage(
                    content="操作被用户拒绝。",
                    tool_call_id=tool_call_id,
                )

        return handler(request)

    def _get_tool_name(self, tool_call: Any) -> str:
        """获取工具名称。"""
        if isinstance(tool_call, dict):
            return tool_call.get("name", "")
        return getattr(tool_call, "name", "")

    def _get_tool_args(self, tool_call: Any) -> dict[str, Any]:
        """获取工具参数。"""
        if isinstance(tool_call, dict):
            return tool_call.get("args", {})
        return getattr(tool_call, "args", {})

    def _get_tool_call_id(self, tool_call: Any) -> str:
        """获取工具调用 ID。"""
        if isinstance(tool_call, dict):
            return tool_call.get("id", "")
        return getattr(tool_call, "id", "")

    def _find_matching_rule(self, tool_name: str, args: dict[str, Any]) -> ApprovalRule | None:
        """查找匹配的审批规则。"""
        for rule in self.rules:
            if rule.matches(tool_name, args):
                return rule
        return None

    def _request_approval(
        self,
        tool_name: str,
        args: dict[str, Any],
        rule: ApprovalRule,
    ) -> bool:
        """请求审批。"""
        if self.callback:
            return self.callback.request_approval(tool_name, args, rule.description)

        try:
            return ConsoleApprovalCallback().request_approval(
                tool_name, args, rule.description
            )
        except (EOFError, KeyboardInterrupt):
            logger.warning("Approval request interrupted, denying by default")
            return False
        except Exception as e:
            logger.error("Approval request failed: %s", e)
            return self.default_approve

    async def awrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """工具执行前检查是否需要审批（异步版本）。"""
        tool_call = request.tool_call
        tool_name = self._get_tool_name(tool_call)
        args = self._get_tool_args(tool_call)

        # 检查是否需要审批
        matched_rule = self._find_matching_rule(tool_name, args)
        if matched_rule:
            try:
                approved = self._request_approval(tool_name, args, matched_rule)
            except Exception as e:
                logger.error("Approval request failed: %s", e)
                approved = self.default_approve

            if not approved:
                tool_call_id = self._get_tool_call_id(tool_call)
                logger.info("Tool call rejected by user: %s", tool_name)
                return ToolMessage(
                    content="操作被用户拒绝。",
                    tool_call_id=tool_call_id,
                )

        return await handler(request)
