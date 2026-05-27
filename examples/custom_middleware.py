"""示例：自定义 Middleware 扩展。

演示如何继承 AgentMiddleware 实现业务逻辑中间件。
Middleware 可以拦截和修改模型请求、注入上下文、记录日志等。

用法:
    python examples/custom_middleware.py
"""

from typing import Any

from hz_agent_base import create_agent, run_agent, AgentMiddleware


class BusinessContextMiddleware(AgentMiddleware):
    """注入业务上下文到系统提示词。

    典型用途：
    - 注入用户画像、权限信息
    - 注入业务规则和约束
    - 注入外部系统状态（数据库连接、API 配额等）
    """

    def __init__(self, context: str):
        self.context = context

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        """拦截模型调用，注入业务上下文。"""
        # 在系统提示词末尾追加业务上下文
        original_prompt = request.system_prompt or ""
        enriched_prompt = f"{original_prompt}\n\n## 业务上下文\n{self.context}"

        # 使用 override() 创建新请求（不修改原请求）
        modified_request = request.override(system_prompt=enriched_prompt)

        # 调用下一个 middleware 或模型
        return handler(modified_request)


class LoggingMiddleware(AgentMiddleware):
    """记录每次模型调用的输入输出。

    典型用途：
    - 调试和审计
    - 性能监控
    - 用量统计
    """

    def __init__(self):
        self.call_count = 0

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        """记录请求和响应。"""
        self.call_count += 1
        print(f"[LoggingMiddleware] 第 {self.call_count} 次模型调用")

        # 提取用户消息摘要
        if request.messages:
            last_msg = request.messages[-1]
            content = getattr(last_msg, "content", "")
            if content:
                print(f"  用户消息: {content[:80]}...")

        # 调用下一个 middleware
        response = handler(request)

        # 记录响应摘要
        if hasattr(response, "content"):
            print(f"  响应长度: {len(response.content)} 字符")

        return response


# 创建带自定义 middleware 的 agent
agent = create_agent(
    middleware=[
        BusinessContextMiddleware(context="当前用户: 管理员\n环境: 生产环境\n注意: 所有操作需要记录审计日志"),
        LoggingMiddleware(),
    ],
)

# 运行
result = run_agent(
    agent,
    "你好，请介绍一下自己",
    thread_id="demo",
)

for msg in result.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"\nAgent: {msg.content}")
