"""对话历史管理示例。

演示如何使用 ConversationHistoryMiddleware 防止 token 超限。
"""

from hz_agent_base import create_agent, run_agent
from hz_agent_base.middleware.conversation_history import ConversationHistoryMiddleware


def example_sliding_window():
    """滑动窗口策略：保留最近 16K tokens 的消息。"""
    agent = create_agent(
        middleware=[
            ConversationHistoryMiddleware(
                strategy="sliding_window",
                max_tokens=16000,  # 保留最近 16K tokens
                keep_system=True,  # 保留 system message
            )
        ]
    )

    # 长对话不会报错
    result = run_agent(agent, "你好", thread_id="user-1")
    print(f"回复: {result}")


def example_truncate():
    """截断策略：保留最近 50 条消息。"""
    agent = create_agent(
        middleware=[
            ConversationHistoryMiddleware(
                strategy="truncate",
                max_messages=50,
            )
        ]
    )

    result = run_agent(agent, "你好", thread_id="user-2")
    print(f"回复: {result}")


def example_summary():
    """摘要策略：旧消息压缩为摘要。"""
    agent = create_agent(
        middleware=[
            ConversationHistoryMiddleware(
                strategy="summary",
                max_tokens=16000,
                summary_threshold=0.8,  # 超过 80% 时触发压缩
            )
        ]
    )

    result = run_agent(agent, "你好", thread_id="user-3")
    print(f"回复: {result}")


def example_combined():
    """组合使用：对话历史管理 + 其他中间件。"""
    from hz_agent_base.middleware.sanitizer import OutputSanitizerMiddleware

    agent = create_agent(
        middleware=[
            # 先管理对话历史
            ConversationHistoryMiddleware(
                strategy="sliding_window",
                max_tokens=16000,
            ),
            # 再清洗输出
            OutputSanitizerMiddleware(mask_pii=True),
        ]
    )

    result = run_agent(agent, "你好", thread_id="user-4")
    print(f"回复: {result}")


if __name__ == "__main__":
    print("=== 滑动窗口策略 ===")
    example_sliding_window()

    print("\n=== 截断策略 ===")
    example_truncate()

    print("\n=== 摘要策略 ===")
    example_summary()

    print("\n=== 组合使用 ===")
    example_combined()
