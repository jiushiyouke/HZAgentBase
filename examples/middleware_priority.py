"""示例：中间件优先级控制。

通过 (middleware, priority) 元组指定自定义中间件的执行位置。

用法:
    python examples/middleware_priority.py
"""

from hz_agent_base import create_agent, run_agent, AgentMiddleware
from hz_agent_base.utils.constants import BEFORE_ALL, AFTER_ALL, DEFAULT


# ============================================================
# 定义自定义中间件
# ============================================================

class RequestLogger(AgentMiddleware):
    """请求日志中间件 — 记录每次请求。"""
    def wrap_model_call(self, request, handler):
        messages = request.messages or []
        user_msg = ""
        for msg in messages:
            if getattr(msg, "type", "") == "human":
                user_msg = getattr(msg, "content", "")
        print(f"[RequestLogger] 收到请求: {user_msg[:50]}...")
        response = handler(request)
        print(f"[RequestLogger] 请求完成")
        return response


class OutputSanitizer(AgentMiddleware):
    """输出清洗中间件 — 过滤敏感信息。"""
    def wrap_model_call(self, request, handler):
        response = handler(request)
        print(f"[OutputSanitizer] 输出已清洗")
        return response


class BusinessContext(AgentMiddleware):
    """业务上下文中间件 — 注入业务信息。"""
    def __init__(self, context: str):
        self.context = context

    def wrap_model_call(self, request, handler):
        enriched = request.override(
            system_prompt=(request.system_prompt or "") + f"\n\n业务上下文: {self.context}"
        )
        return handler(enriched)


# ============================================================
# 创建 agent，指定中间件优先级
# ============================================================

agent = create_agent(
    middleware=[
        (RequestLogger(), BEFORE_ALL),         # 最前面执行（优先级 0）
        (BusinessContext("生产环境")),           # 默认位置（优先级 30）
        (OutputSanitizer(), AFTER_ALL),        # 最后面执行（优先级 100）
    ],
)

# 运行
result = run_agent(agent, "你好", thread_id="demo")
for msg in result.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"\nAgent: {msg.content}")
