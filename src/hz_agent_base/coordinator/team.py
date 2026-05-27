"""Team registry for managing agent teams."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Team:
    """A named group of agents."""

    name: str
    members: list[str] = field(default_factory=list)


class TeamRegistry:
    """Registry for managing teams and their members."""

    def __init__(self):
        self._teams: dict[str, Team] = {}

    def create_team(self, name: str) -> Team:
        """Create a new team."""
        if name not in self._teams:
            self._teams[name] = Team(name=name)
        return self._teams[name]

    def add_member(self, team_name: str, agent_name: str) -> None:
        """Add an agent to a team."""
        team = self.create_team(team_name)
        if agent_name not in team.members:
            team.members.append(agent_name)

    def get_team(self, name: str) -> Team | None:
        """Get a team by name."""
        return self._teams.get(name)

    def get_members(self, team_name: str) -> list[str]:
        """Get all members of a team."""
        team = self._teams.get(team_name)
        return team.members if team else []

    def get_status(self) -> str:
        """Get a formatted status of all teams."""
        if not self._teams:
            return "No teams configured."

        lines = []
        for team in self._teams.values():
            members = ", ".join(team.members) if team.members else "(empty)"
            lines.append(f"  {team.name}: {members}")

        return "\n".join(lines)
