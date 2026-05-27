"""团队注册表 — 管理命名的 Agent 团队及其成员。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Team:
    """一个命名的 Agent 团队。"""

    name: str
    """团队名称。"""

    members: list[str] = field(default_factory=list)
    """团队成员名称列表。"""


class TeamRegistry:
    """团队注册表，管理团队的创建和成员关系。"""

    def __init__(self):
        self._teams: dict[str, Team] = {}

    def create_team(self, name: str) -> Team:
        """创建团队（已存在则直接返回）。"""
        if name not in self._teams:
            self._teams[name] = Team(name=name)
        return self._teams[name]

    def add_member(self, team_name: str, agent_name: str) -> None:
        """将 Agent 添加到指定团队。"""
        team = self.create_team(team_name)
        if agent_name not in team.members:
            team.members.append(agent_name)

    def get_team(self, name: str) -> Team | None:
        """按名称获取团队。"""
        return self._teams.get(name)

    def get_members(self, team_name: str) -> list[str]:
        """获取团队的所有成员名称。"""
        team = self._teams.get(team_name)
        return team.members if team else []

    def get_status(self) -> str:
        """返回所有团队的格式化状态信息。"""
        if not self._teams:
            return "No teams configured."

        lines = []
        for team in self._teams.values():
            members = ", ".join(team.members) if team.members else "(empty)"
            lines.append(f"  {team.name}: {members}")

        return "\n".join(lines)
