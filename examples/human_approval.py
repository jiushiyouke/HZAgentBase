"""Human-in-the-loop 示例。

演示如何使用 HumanApprovalMiddleware 在危险操作前请求人工确认。
"""

from hz_agent_base import create_agent, run_agent
from hz_agent_base.middleware.human_approval import (
    HumanApprovalMiddleware,
    ApprovalRule,
    ApprovalCallback,
)


class RedisApprovalCallback:
    """Redis 审批回调示例（伪代码）。

    实际使用时需要实现 Redis 交互逻辑。
    """

    def __init__(self, redis_client):
        self.redis = redis_client

    def request_approval(self, tool_name, args, rule_description):
        """通过 Redis 发送审批请求，等待用户在 Web 界面确认。"""
        # 1. 生成审批请求 ID
        request_id = f"approval:{tool_name}:{id(args)}"

        # 2. 存储到 Redis
        self.redis.set(request_id, {
            "tool_name": tool_name,
            "args": args,
            "description": rule_description,
        })

        # 3. 等待用户确认（轮询或订阅）
        # 实际实现中应该用 Pub/Sub 或 WebSocket
        import time
        for _ in range(300):  # 5 分钟超时
            result = self.redis.get(f"{request_id}:result")
            if result:
                return result == "approved"
            time.sleep(1)

        return False  # 超时拒绝


def example_basic():
    """基础用法：控制台审批。"""
    agent = create_agent(
        middleware=[
            HumanApprovalMiddleware(
                rules=[
                    ApprovalRule(
                        tools=["bash", "delete_file"],
                        description="危险操作需确认",
                    ),
                ],
            )
        ]
    )

    # 执行 bash 命令时会询问用户
    result = run_agent(agent, "列出当前目录文件", thread_id="user-1")
    print(f"回复: {result}")


def example_with_patterns():
    """带模式匹配的审批规则。"""
    agent = create_agent(
        middleware=[
            HumanApprovalMiddleware(
                rules=[
                    # 删除文件需要确认
                    ApprovalRule(
                        tools=["delete_file", "remove_file"],
                        description="删除文件需确认",
                    ),
                    # 写入敏感文件需要确认
                    ApprovalRule(
                        tools=["write_file", "edit_file"],
                        patterns=["**/.env*", "**/secrets/**", "**/*.key"],
                        description="写入敏感文件需确认",
                    ),
                    # 执行危险命令需要确认
                    ApprovalRule(
                        tools=["bash"],
                        patterns=["rm *", "sudo *", "chmod *"],
                        description="危险命令需确认",
                    ),
                ],
            )
        ]
    )

    result = run_agent(agent, "帮我创建一个 .env 文件", thread_id="user-2")
    print(f"回复: {result}")


def example_custom_callback():
    """自定义审批回调。"""

    class MockApprovalCallback:
        """模拟审批回调（用于演示）。"""

        def request_approval(self, tool_name, args, rule_description):
            print(f"\n[自动审批] 工具: {tool_name}, 参数: {args}")
            return True  # 自动批准

    agent = create_agent(
        middleware=[
            HumanApprovalMiddleware(
                rules=[
                    ApprovalRule(tools=["bash"]),
                ],
                callback=MockApprovalCallback(),
            )
        ]
    )

    result = run_agent(agent, "执行 ls 命令", thread_id="user-3")
    print(f"回复: {result}")


def example_combined():
    """组合使用：多个中间件。"""
    from hz_agent_base.middleware.conversation_history import ConversationHistoryMiddleware
    from hz_agent_base.middleware.sanitizer import OutputSanitizerMiddleware

    agent = create_agent(
        middleware=[
            # 1. 人工审批（优先级最高）
            HumanApprovalMiddleware(
                rules=[ApprovalRule(tools=["bash"])],
            ),
            # 2. 对话历史管理
            ConversationHistoryMiddleware(strategy="sliding_window", max_tokens=16000),
            # 3. 输出清洗
            OutputSanitizerMiddleware(mask_pii=True),
        ]
    )

    result = run_agent(agent, "你好", thread_id="user-4")
    print(f"回复: {result}")


if __name__ == "__main__":
    print("=== 基础用法 ===")
    example_basic()

    print("\n=== 带模式匹配 ===")
    example_with_patterns()

    print("\n=== 自定义回调 ===")
    example_custom_callback()

    print("\n=== 组合使用 ===")
    example_combined()
