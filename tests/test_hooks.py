"""测试钩子系统：HookRegistry、HookExecutor、HookEvent。"""

import pytest

from hz_agent_base.hooks.events import HookEvent
from hz_agent_base.hooks.schemas import (
    HookDefinition,
    CommandHookDefinition,
)
from hz_agent_base.hooks.registry import HookRegistry
from hz_agent_base.hooks.executor import HookExecutor, HookResult, AggregatedHookResult


class TestHookEvent:
    """测试 HookEvent 枚举。"""

    def test_all_events_exist(self):
        """确保所有预期事件都存在。"""
        expected = {"session_start", "session_end", "pre_tool_use",
                    "post_tool_use", "user_prompt_submit"}
        actual = {e.value for e in HookEvent}
        assert expected == actual


class TestHookRegistry:
    """测试 HookRegistry。"""

    def test_register_single_hook(self):
        """注册单个钩子。"""
        registry = HookRegistry()
        hook = HookDefinition(event=HookEvent.PRE_TOOL_USE)
        registry.register(hook)

        hooks = registry.get_hooks(HookEvent.PRE_TOOL_USE)
        assert len(hooks) == 1
        assert hooks[0] is hook

    def test_register_many(self):
        """批量注册钩子。"""
        registry = HookRegistry()
        hooks = [
            HookDefinition(event=HookEvent.PRE_TOOL_USE),
            HookDefinition(event=HookEvent.POST_TOOL_USE),
        ]
        registry.register_many(hooks)

        assert len(registry.get_hooks(HookEvent.PRE_TOOL_USE)) == 1
        assert len(registry.get_hooks(HookEvent.POST_TOOL_USE)) == 1

    def test_get_hooks_returns_empty_for_unknown_event(self):
        """未注册的事件应返回空列表。"""
        registry = HookRegistry()
        assert registry.get_hooks(HookEvent.SESSION_END) == []

    def test_clear_specific_event(self):
        """清除特定事件的钩子。"""
        registry = HookRegistry()
        registry.register(HookDefinition(event=HookEvent.PRE_TOOL_USE))
        registry.register(HookDefinition(event=HookEvent.POST_TOOL_USE))

        registry.clear(HookEvent.PRE_TOOL_USE)

        assert len(registry.get_hooks(HookEvent.PRE_TOOL_USE)) == 0
        assert len(registry.get_hooks(HookEvent.POST_TOOL_USE)) == 1

    def test_clear_all(self):
        """清除所有钩子。"""
        registry = HookRegistry()
        registry.register(HookDefinition(event=HookEvent.PRE_TOOL_USE))
        registry.register(HookDefinition(event=HookEvent.POST_TOOL_USE))

        registry.clear()

        assert len(registry.get_hooks(HookEvent.PRE_TOOL_USE)) == 0
        assert len(registry.get_hooks(HookEvent.POST_TOOL_USE)) == 0


class TestHookExecutor:
    """测试 HookExecutor。"""

    def test_execute_no_hooks_returns_empty_result(self):
        """没有钩子时应返回空结果。"""
        registry = HookRegistry()
        executor = HookExecutor(registry)

        result = executor.execute(HookEvent.PRE_TOOL_USE, {"tool": "test"})

        assert isinstance(result, AggregatedHookResult)
        assert result.blocked is False
        assert result.results == []

    def test_execute_command_hook_success(self):
        """成功的命令钩子应返回 success=True。"""
        registry = HookRegistry()
        # echo 是跨平台可用的简单命令
        registry.register(CommandHookDefinition(
            event=HookEvent.PRE_TOOL_USE,
            command="echo ok",
        ))
        executor = HookExecutor(registry)

        result = executor.execute(HookEvent.PRE_TOOL_USE, {"tool": "test"})

        assert len(result.results) == 1
        assert result.results[0].success is True
        assert result.results[0].blocked is False

    def test_execute_command_hook_failure_blocks(self):
        """失败的命令钩子在 block_on_failure=True 时应阻止操作。"""
        registry = HookRegistry()
        # 执行一个必定失败的命令
        registry.register(CommandHookDefinition(
            event=HookEvent.PRE_TOOL_USE,
            command="python -c \"import sys; sys.exit(1)\"",
            block_on_failure=True,
        ))
        executor = HookExecutor(registry)

        result = executor.execute(HookEvent.PRE_TOOL_USE, {"tool": "test"})

        assert result.blocked is True
        assert len(result.reasons) > 0

    def test_execute_command_hook_failure_no_block(self):
        """失败的命令钩子在 block_on_failure=False 时不阻止。"""
        registry = HookRegistry()
        registry.register(CommandHookDefinition(
            event=HookEvent.PRE_TOOL_USE,
            command="python -c \"import sys; sys.exit(1)\"",
            block_on_failure=False,
        ))
        executor = HookExecutor(registry)

        result = executor.execute(HookEvent.PRE_TOOL_USE, {"tool": "test"})

        # 虽然失败，但不阻止
        assert result.results[0].success is False
        assert result.blocked is False

    def test_matcher_filters_hooks(self):
        """matcher 模式应过滤不匹配的钩子。"""
        registry = HookRegistry()
        registry.register(CommandHookDefinition(
            event=HookEvent.PRE_TOOL_USE,
            command="echo matched",
            matcher="bash",  # 只匹配 bash 工具
        ))
        executor = HookExecutor(registry)

        # 不匹配的工具名
        result = executor.execute(
            HookEvent.PRE_TOOL_USE, {"tool": "test"}, tool_name="read_file"
        )
        assert len(result.results) == 0

        # 匹配的工具名
        result = executor.execute(
            HookEvent.PRE_TOOL_USE, {"tool": "test"}, tool_name="bash"
        )
        assert len(result.results) == 1


class TestAggregatedHookResult:
    """测试 AggregatedHookResult。"""

    def test_blocked_when_any_hook_blocked(self):
        """任一钩子阻止则整体阻止。"""
        result = AggregatedHookResult(results=[
            HookResult(success=True),
            HookResult(success=True, blocked=True, reason="bad"),
        ])
        assert result.blocked is True

    def test_not_blocked_when_all_pass(self):
        """所有钩子通过则不阻止。"""
        result = AggregatedHookResult(results=[
            HookResult(success=True),
            HookResult(success=True),
        ])
        assert result.blocked is False

    def test_reasons_returns_only_blocked(self):
        """reasons 应只返回阻止的原因。"""
        result = AggregatedHookResult(results=[
            HookResult(success=True, blocked=True, reason="reason1"),
            HookResult(success=True),
            HookResult(success=True, blocked=True, reason="reason2"),
        ])
        assert result.reasons == ["reason1", "reason2"]
