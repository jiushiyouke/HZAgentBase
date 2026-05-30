"""示例：多租户支持。

通过 api_key 和 base_url 参数，不同租户可用不同 API 配置。

用法:
    python examples/multi_tenant.py
"""

from hz_agent_base import create_agent, run_agent

# ============================================================
# 方式 1：通过 api_key 参数覆盖
# ============================================================

# 租户 A 用 DeepSeek
agent_a = create_agent(
    model="deepseek-v4-flash",
    api_key="sk-tenant-a-key...",
)

# 租户 B 用 OpenAI
agent_b = create_agent(
    model="gpt-4",
    api_key="sk-tenant-b-key...",
    base_url="https://api.openai.com/v1",
)

# ============================================================
# 方式 2：直接传预配置的模型实例
# ============================================================

from langchain_openai import ChatOpenAI
from langchain_deepseek import ChatDeepSeek

agent_c = create_agent(
    model=ChatDeepSeek(
        model="deepseek-v4-flash",
        api_key="sk-tenant-c-key...",
        base_url="https://api.deepseek.com/v1",
    ),
)

# ============================================================
# 使用示例
# ============================================================

# 每个租户的 agent 独立运行
result_a = run_agent(agent_a, "你好", thread_id="tenant-a")
result_b = run_agent(agent_b, "Hello", thread_id="tenant-b")

print("Tenant A:", result_a.get("messages", [])[-1].content if result_a.get("messages") else "No response")
print("Tenant B:", result_b.get("messages", [])[-1].content if result_b.get("messages") else "No response")
