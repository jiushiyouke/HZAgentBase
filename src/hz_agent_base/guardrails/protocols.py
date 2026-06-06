"""Guardrails — 协议定义。

定义内容审核、事实检查、输出校验的协议接口。
用户实现这些协议后注入 GuardrailsMiddleware。
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence, runtime_checkable


@runtime_checkable
class ContentModerator(Protocol):
    """内容审核协议 — 检测输出是否包含违规内容。

    实现示例：

        class APIModerator:
            def __init__(self, api_url: str):
                self.api_url = api_url

            def is_safe(self, content: str) -> bool:
                response = requests.post(self.api_url, json={"text": content})
                return response.json().get("safe", True)
    """

    def is_safe(self, content: str) -> bool:
        """检查内容是否安全。

        Args:
            content: 待检查的文本内容。

        Returns:
            True 表示安全，False 表示包含违规内容。
        """
        ...


@runtime_checkable
class FactChecker(Protocol):
    """事实检查协议 — 验证输出是否准确。

    实现示例：

        class KnowledgeBaseChecker:
            def __init__(self, knowledge_base):
                self.kb = knowledge_base

            def is_accurate(self, content: str, context: Sequence[Any]) -> bool:
                # 对比知识库验证
                return self.kb.verify(content)
    """

    def is_accurate(self, content: str, context: Sequence[Any]) -> bool:
        """检查内容是否准确。

        Args:
            content: 待检查的文本内容。
            context: 上下文信息（如对话历史）。

        Returns:
            True 表示准确，False 表示可能存在错误。
        """
        ...


@runtime_checkable
class OutputValidator(Protocol):
    """输出校验协议 — 验证输出是否符合预期格式。

    实现示例：

        class JSONValidator:
            def is_valid(self, content: str) -> bool:
                try:
                    json.loads(content)
                    return True
                except json.JSONDecodeError:
                    return False
    """

    def is_valid(self, content: str) -> bool:
        """检查内容格式是否有效。

        Args:
            content: 待检查的文本内容。

        Returns:
            True 表示格式有效，False 表示格式错误。
        """
        ...
