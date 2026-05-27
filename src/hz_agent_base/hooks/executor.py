"""Hook 执行器 — 运行 Hook 并聚合结果。

支持 4 种 Hook 的执行：
- CommandHook: 通过 subprocess 执行 shell 命令
- HttpHook: 通过 httpx 发送 HTTP POST
- PromptHook: 通过 LLM 验证条件
- AgentHook: 通过子 Agent 深度验证
"""

from __future__ import annotations

import json
import subprocess
import fnmatch
from dataclasses import dataclass
from typing import Any

from .events import HookEvent
from .registry import HookRegistry
from .schemas import (
    HookDefinition,
    CommandHookDefinition,
    HttpHookDefinition,
    PromptHookDefinition,
    AgentHookDefinition,
)


@dataclass
class HookResult:
    """单个 Hook 的执行结果。"""

    success: bool
    """是否执行成功。"""

    blocked: bool = False
    """是否阻止了操作。"""

    reason: str = ""
    """阻止原因。"""

    output: str = ""
    """Hook 的输出内容。"""


@dataclass
class AggregatedHookResult:
    """一个事件的所有 Hook 聚合结果。"""

    results: list[HookResult]

    @property
    def blocked(self) -> bool:
        """是否有任何 Hook 阻止了操作。"""
        return any(r.blocked for r in self.results)

    @property
    def reasons(self) -> list[str]:
        """所有阻止原因列表。"""
        return [r.reason for r in self.results if r.blocked]


class HookExecutor:
    """执行 Hook 并聚合结果。

    Args:
        registry: Hook 注册表。
        model: LLM 模型实例（LangChain ChatModel），供 PromptHook 和 AgentHook 使用。
               未设置时，PromptHook 和 AgentHook 会直接放行。
    """

    def __init__(self, registry: HookRegistry, model: Any = None):
        self.registry = registry
        self.model = model

    def execute(
        self,
        event: HookEvent,
        payload: dict[str, Any],
        tool_name: str | None = None,
    ) -> AggregatedHookResult:
        """执行事件匹配的所有 Hook。

        Args:
            event: 事件类型。
            payload: 事件数据。
            tool_name: 工具名称（用于 matcher 过滤）。

        Returns:
            聚合的 Hook 执行结果。
        """
        hooks = self.registry.get_hooks(event)
        results: list[HookResult] = []

        for hook in hooks:
            # 检查 matcher 模式是否匹配工具名
            if hook.matcher and tool_name:
                if not fnmatch.fnmatch(tool_name, hook.matcher):
                    continue

            result = self._execute_single(hook, payload)
            results.append(result)

            # 如果 Hook 阻止了操作且设置了 block_on_failure，短路退出
            if result.blocked and hook.block_on_failure:
                break

        return AggregatedHookResult(results=results)

    def _execute_single(
        self,
        hook: HookDefinition,
        payload: dict[str, Any],
    ) -> HookResult:
        """根据 Hook 类型分发到对应的执行方法。"""
        if isinstance(hook, CommandHookDefinition):
            return self._execute_command(hook, payload)
        elif isinstance(hook, HttpHookDefinition):
            return self._execute_http(hook, payload)
        elif isinstance(hook, PromptHookDefinition):
            return self._execute_prompt(hook, payload)
        elif isinstance(hook, AgentHookDefinition):
            return self._execute_agent(hook, payload)
        else:
            return HookResult(success=False, reason=f"Unknown hook type: {type(hook)}")

    def _execute_command(
        self,
        hook: CommandHookDefinition,
        payload: dict[str, Any],
    ) -> HookResult:
        """执行 shell 命令 Hook。"""
        import os

        # 将事件信息注入环境变量，供命令脚本读取
        env = os.environ.copy()
        env["HZ_HOOK_EVENT"] = hook.event.value
        env["HZ_HOOK_PAYLOAD"] = json.dumps(payload)

        try:
            result = subprocess.run(
                hook.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=hook.timeout_seconds,
                env=env,
            )

            if result.returncode != 0:
                blocked = hook.block_on_failure
                return HookResult(
                    success=False,
                    blocked=blocked,
                    reason=f"Command hook failed: {result.stderr}",
                    output=result.stderr,
                )

            return HookResult(success=True, output=result.stdout)

        except subprocess.TimeoutExpired:
            return HookResult(
                success=False,
                blocked=hook.block_on_failure,
                reason=f"Command hook timed out after {hook.timeout_seconds}s",
            )
        except Exception as e:
            return HookResult(
                success=False,
                blocked=hook.block_on_failure,
                reason=f"Command hook error: {str(e)}",
            )

    def _execute_http(
        self,
        hook: HttpHookDefinition,
        payload: dict[str, Any],
    ) -> HookResult:
        """执行 HTTP POST Hook。"""
        try:
            import httpx

            response = httpx.post(
                hook.url,
                json=payload,
                headers=hook.headers,
                timeout=hook.timeout_seconds,
            )

            if response.status_code >= 400:
                return HookResult(
                    success=False,
                    blocked=hook.block_on_failure,
                    reason=f"HTTP hook returned {response.status_code}",
                )

            # 检查响应体中的阻止信号
            try:
                data = response.json()
                if isinstance(data, dict) and data.get("ok") is False:
                    return HookResult(
                        success=True,
                        blocked=True,
                        reason=data.get("reason", "HTTP hook blocked"),
                    )
            except Exception:
                pass

            return HookResult(success=True)

        except Exception as e:
            return HookResult(
                success=False,
                blocked=hook.block_on_failure,
                reason=f"HTTP hook error: {str(e)}",
            )

    def _execute_prompt(
        self,
        hook: PromptHookDefinition,
        payload: dict[str, Any],
    ) -> HookResult:
        """执行 Prompt 验证 Hook。

        将 hook.prompt 和事件数据发送给 LLM，
        解析响应中的 JSON 判断是否放行：
        - {"ok": true} → 放行
        - {"ok": false, "reason": "..."} → 阻止

        未配置 model 时直接放行。
        """
        if not self.model:
            return HookResult(
                success=True,
                reason="No model configured for PromptHook, skipped",
            )

        try:
            from langchain_core.messages import HumanMessage

            # 构造验证请求：hook 提示词 + 事件上下文
            payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
            full_prompt = (
                f"{hook.prompt}\n\n"
                f"## Event Context\n"
                f"Event: {hook.event.value}\n"
                f"Payload:\n{payload_json}\n\n"
                f"Respond with JSON only: {{\"ok\": true}} or {{\"ok\": false, \"reason\": \"...\"}}"
            )

            response = self.model.invoke([HumanMessage(content=full_prompt)])
            response_text = response.content if isinstance(response.content, str) else str(response.content)

            # 解析 LLM 响应中的 JSON
            result_data = self._extract_json(response_text)

            if result_data and result_data.get("ok") is False:
                return HookResult(
                    success=True,
                    blocked=True,
                    reason=result_data.get("reason", "PromptHook validation failed"),
                    output=response_text,
                )

            return HookResult(success=True, output=response_text)

        except Exception as e:
            return HookResult(
                success=False,
                blocked=hook.block_on_failure,
                reason=f"PromptHook error: {str(e)}",
            )

    def _execute_agent(
        self,
        hook: AgentHookDefinition,
        payload: dict[str, Any],
    ) -> HookResult:
        """执行子 Agent 验证 Hook。

        创建一个轻量子 Agent，使用 hook.agent_prompt 作为系统提示词，
        将事件数据作为输入，根据子 Agent 的响应判断是否放行。

        未配置 model 时直接放行。
        """
        if not self.model:
            return HookResult(
                success=True,
                reason="No model configured for AgentHook, skipped",
            )

        try:
            from langchain_core.messages import SystemMessage, HumanMessage

            # 构造子 Agent 的输入
            payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
            validation_prompt = (
                f"Analyze the following event and decide whether to allow it.\n\n"
                f"Event: {hook.event.value}\n"
                f"Payload:\n{payload_json}\n\n"
                f"Respond with JSON only: {json.dumps({'ok': True})} to allow, "
                f"or {json.dumps({'ok': False, 'reason': '...'})} to block."
            )

            # 调用 LLM（使用 agent_prompt 作为系统提示词）
            messages = [
                SystemMessage(content=hook.agent_prompt),
                HumanMessage(content=validation_prompt),
            ]
            response = self.model.invoke(messages)
            response_text = response.content if isinstance(response.content, str) else str(response.content)

            # 解析响应
            result_data = self._extract_json(response_text)

            if result_data and result_data.get("ok") is False:
                return HookResult(
                    success=True,
                    blocked=True,
                    reason=result_data.get("reason", "AgentHook validation failed"),
                    output=response_text,
                )

            return HookResult(success=True, output=response_text)

        except Exception as e:
            return HookResult(
                success=False,
                blocked=hook.block_on_failure,
                reason=f"AgentHook error: {str(e)}",
            )

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """从文本中提取 JSON 对象。

        LLM 响应可能包含 markdown 代码块或额外文本，
        此方法尝试从中提取第一个 JSON 对象。
        """
        import re

        # 尝试直接解析
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # 尝试从 ```json ... ``` 代码块中提取
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取第一个 { ... } 块
        match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None
