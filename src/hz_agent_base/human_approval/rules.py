"""Human-in-the-loop — 类型定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class ApprovalCallback(Protocol):
    """审批回调协议。"""

    def request_approval(
        self,
        tool_name: str,
        args: dict[str, Any],
        rule_description: str,
    ) -> bool:
        """请求人工审批。

        Args:
            tool_name: 工具名称。
            args: 工具参数。
            rule_description: 触发的规则描述。

        Returns:
            True 表示批准，False 表示拒绝。
        """
        ...


@dataclass
class ApprovalRule:
    """审批规则。

    Attributes:
        tools: 需要审批的工具名称列表。
        patterns: 参数匹配模式列表（如文件路径 glob 模式）。
            如果指定，只有参数匹配时才触发审批。
        description: 规则描述，会显示给用户。
    """

    tools: list[str]
    patterns: list[str] = field(default_factory=list)
    description: str = ""

    def matches(self, tool_name: str, args: dict[str, Any]) -> bool:
        """检查工具调用是否匹配此规则。"""
        # 检查工具名
        if tool_name not in self.tools:
            return False

        # 如果没有指定 patterns，直接匹配
        if not self.patterns:
            return True

        # 检查参数中的文件路径是否匹配 patterns
        file_path = args.get("file_path") or args.get("path") or args.get("command") or ""
        if not file_path:
            return False

        from pathlib import PurePosixPath
        file_path = str(file_path)
        return any(
            PurePosixPath(file_path).match(pattern)
            for pattern in self.patterns
        )


class ConsoleApprovalCallback:
    """控制台审批回调（默认实现）。"""

    def request_approval(
        self,
        tool_name: str,
        args: dict[str, Any],
        rule_description: str,
    ) -> bool:
        """在控制台询问用户是否批准。"""
        print("\n" + "=" * 60)
        print(f"⚠️  需要人工审批")
        print(f"工具: {tool_name}")
        print(f"参数: {args}")
        if rule_description:
            print(f"规则: {rule_description}")
        print("=" * 60)

        while True:
            response = input("是否批准？(y/n): ").strip().lower()
            if response in ("y", "yes", "是"):
                return True
            if response in ("n", "no", "否"):
                return False
            print("请输入 y 或 n")
