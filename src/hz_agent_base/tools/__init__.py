"""工具扩展包 — 提供工具基类的便捷导入。

HZAgentBase 不封装自己的工具，而是透传 LangChain 的 BaseTool。
自定义工具直接继承 BaseTool 即可接入 Agent。
"""

from langchain_core.tools import BaseTool

__all__ = ["BaseTool"]
