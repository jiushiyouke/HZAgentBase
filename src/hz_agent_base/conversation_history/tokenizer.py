"""对话历史管理 — 类型定义和工具函数。"""

from __future__ import annotations

from typing import Any

# Token 估算常量
CHARS_PER_TOKEN = 4  # 简化估算：平均 4 个字符 ≈ 1 token

# 摘要提示词
SUMMARY_PROMPT = """请将以下对话历史压缩为简洁的摘要，保留关键信息和上下文：

{history}

要求：
1. 保留用户的主要需求和意图
2. 保留 Agent 的关键回答和结论
3. 保留重要的上下文信息（如文件路径、代码片段等）
4. 压缩到原长度的 20-30%
5. 使用第三人称描述（"用户要求..."，"Agent 回答..."）

请直接输出摘要，不要添加额外说明。"""


def estimate_tokens(text: str) -> int:
    """估算文本的 token 数量。"""
    return len(text) // CHARS_PER_TOKEN


def estimate_message_tokens(message: Any) -> int:
    """估算单条消息的 token 数量。"""
    content = getattr(message, "content", "")
    if not content:
        return 0

    if isinstance(content, list):
        text = " ".join(str(item) for item in content if isinstance(item, str))
        return estimate_tokens(text)

    return estimate_tokens(str(content))


def format_message_for_summary(message: Any) -> str:
    """将消息格式化为摘要用的文本。"""
    role = getattr(message, "type", None) or getattr(message, "role", "unknown")
    content = getattr(message, "content", "")

    if isinstance(content, list):
        content = " ".join(str(item) for item in content if isinstance(item, str))

    role_map = {"human": "用户", "ai": "Agent", "system": "系统"}
    role_name = role_map.get(str(role), str(role))

    return f"{role_name}: {content}"
