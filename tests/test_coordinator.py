"""测试多 Agent 编排：WorkerConfig、TeamRegistry、CoordinatorMiddleware。"""

import pytest
from unittest.mock import MagicMock

from langchain_core.messages import HumanMessage

from hz_agent_base.coordinator.worker import WorkerConfig
from hz_agent_base.coordinator.team import TeamRegistry, Team
from hz_agent_base.coordinator.coordinator import CoordinatorMiddleware


# ============================================================
# WorkerConfig 测试
# ============================================================

class TestWorkerConfig:
    """测试 WorkerConfig 数据类。"""

    def test_minimal_config(self):
        """最小配置应只需 name。"""
        w = WorkerConfig(name="researcher")
        assert w.name == "researcher"
        assert w.prompt == ""
        assert w.tools == []
        assert w.model is None
        assert w.team == "default"
        assert w.color == "blue"

    def test_full_config(self):
        """完整配置应支持所有字段。"""
        w = WorkerConfig(
            name="coder",
            prompt="你是编程助手",
            tools=["write_file", "edit_file"],
            model="deepseek-v4-flash",
            team="development",
            color="green",
        )
        assert w.name == "coder"
        assert w.prompt == "你是编程助手"
        assert w.tools == ["write_file", "edit_file"]
        assert w.model == "deepseek-v4-flash"
        assert w.team == "development"
        assert w.color == "green"


# ============================================================
# TeamRegistry 测试
# ============================================================

class TestTeamRegistry:
    """测试 TeamRegistry。"""

    def test_create_team(self):
        """创建 team 应返回 Team 对象。"""
        registry = TeamRegistry()
        team = registry.create_team("research")
        assert isinstance(team, Team)
        assert team.name == "research"

    def test_create_team_idempotent(self):
        """重复创建同名 team 应返回同一个对象。"""
        registry = TeamRegistry()
        t1 = registry.create_team("research")
        t2 = registry.create_team("research")
        assert t1 is t2

    def test_add_member(self):
        """添加成员应出现在 team 中。"""
        registry = TeamRegistry()
        registry.add_member("research", "researcher")

        members = registry.get_members("research")
        assert "researcher" in members

    def test_add_member_no_duplicate(self):
        """重复添加同一成员不应重复。"""
        registry = TeamRegistry()
        registry.add_member("research", "researcher")
        registry.add_member("research", "researcher")

        assert len(registry.get_members("research")) == 1

    def test_add_member_to_nonexistent_team(self):
        """向不存在的 team 添加成员应自动创建 team。"""
        registry = TeamRegistry()
        registry.add_member("new-team", "agent-1")

        assert registry.get_team("new-team") is not None
        assert "agent-1" in registry.get_members("new-team")

    def test_get_team_returns_none_for_unknown(self):
        """查询不存在的 team 应返回 None。"""
        registry = TeamRegistry()
        assert registry.get_team("nope") is None

    def test_get_members_returns_empty_for_unknown(self):
        """查询不存在的 team 的成员应返回空列表。"""
        registry = TeamRegistry()
        assert registry.get_members("nope") == []

    def test_get_status_empty(self):
        """没有 team 时应返回提示。"""
        registry = TeamRegistry()
        assert "No teams" in registry.get_status()

    def test_get_status_with_teams(self):
        """有 team 时应显示 team 名和成员。"""
        registry = TeamRegistry()
        registry.add_member("research", "researcher")
        registry.add_member("dev", "coder")

        status = registry.get_status()
        assert "research" in status
        assert "researcher" in status
        assert "dev" in status
        assert "coder" in status


# ============================================================
# CoordinatorMiddleware 测试
# ============================================================

def make_mock_request(system_prompt="You are helpful."):
    """创建模拟的 ModelRequest。"""
    request = MagicMock()
    request.messages = [HumanMessage(content="hello")]
    request.system_prompt = system_prompt

    def mock_override(**kwargs):
        new_req = MagicMock()
        new_req.messages = request.messages
        new_req.system_prompt = kwargs.get("system_prompt", request.system_prompt)
        return new_req

    request.override = MagicMock(side_effect=mock_override)
    return request


class TestCoordinatorMiddleware:
    """测试 CoordinatorMiddleware。"""

    def test_creates_with_workers(self):
        """应能用 worker 列表创建。"""
        workers = [
            WorkerConfig(name="researcher", prompt="研究助手"),
            WorkerConfig(name="coder", prompt="编程助手"),
        ]
        mw = CoordinatorMiddleware(workers)
        assert len(mw.workers) == 2
        assert len(mw.subagents) == 2

    def test_registers_workers_into_teams(self):
        """创建时应将 worker 注册到对应 team。"""
        workers = [
            WorkerConfig(name="researcher", team="research"),
            WorkerConfig(name="coder", team="dev"),
        ]
        mw = CoordinatorMiddleware(workers)

        assert "researcher" in mw.team_registry.get_members("research")
        assert "coder" in mw.team_registry.get_members("dev")

    def test_subagents_created(self):
        """应为每个 worker 创建对应的 subagent。"""
        workers = [
            WorkerConfig(name="a", prompt="prompt a", tools=["bash"]),
            WorkerConfig(name="b", prompt="prompt b"),
        ]
        mw = CoordinatorMiddleware(workers)

        assert len(mw.subagents) == 2
        assert mw.subagents[0]["name"] == "a"
        assert mw.subagents[0]["tools"] == ["bash"]
        assert mw.subagents[1]["name"] == "b"

    def test_injects_worker_info_into_system_prompt(self):
        """应将 worker 信息注入系统提示词。"""
        workers = [
            WorkerConfig(name="researcher", prompt="研究助手", tools=["web_search"]),
        ]
        mw = CoordinatorMiddleware(workers)

        request = make_mock_request("You are helpful.")
        handler = MagicMock(return_value="response")

        mw.wrap_model_call(request, handler)

        # 检查 override 被调用
        request.override.assert_called_once()
        new_prompt = request.override.call_args[1]["system_prompt"]

        assert "Available Workers" in new_prompt
        assert "researcher" in new_prompt
        assert "web_search" in new_prompt
        assert "Team Status" in new_prompt

    def test_preserves_original_system_prompt(self):
        """注入时应保留原始系统提示词。"""
        workers = [WorkerConfig(name="a")]
        mw = CoordinatorMiddleware(workers)

        request = make_mock_request("Original prompt.")
        handler = MagicMock(return_value="response")

        mw.wrap_model_call(request, handler)

        new_prompt = request.override.call_args[1]["system_prompt"]
        assert new_prompt.startswith("Original prompt.")

    def test_handler_called_with_modified_request(self):
        """handler 应收到修改后的 request。"""
        workers = [WorkerConfig(name="a")]
        mw = CoordinatorMiddleware(workers)

        request = make_mock_request()
        handler = MagicMock(return_value="response")

        mw.wrap_model_call(request, handler)

        # handler 应被调用，参数是 override 后的新 request
        handler.assert_called_once()
        call_arg = handler.call_args[0][0]
        # 新 request 应有注入的内容
        assert call_arg.system_prompt != request.system_prompt

    def test_long_prompt_truncated(self):
        """过长的 worker prompt 应被截断。"""
        long_prompt = "A" * 200
        workers = [WorkerConfig(name="a", prompt=long_prompt)]
        mw = CoordinatorMiddleware(workers)

        request = make_mock_request()
        handler = MagicMock(return_value="response")

        mw.wrap_model_call(request, handler)

        new_prompt = request.override.call_args[1]["system_prompt"]
        # 截断后应包含 "..."
        assert "..." in new_prompt
