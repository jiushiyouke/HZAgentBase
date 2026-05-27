"""工具扩展包。

薄封装层，re-export Deep Agents 的 BaseTool。
业务项目可在此基础上定义自定义工具。
"""

# Re-export Deep Agents 基础工具类
from deepagents.tools import BaseTool

__all__ = ["BaseTool"]
