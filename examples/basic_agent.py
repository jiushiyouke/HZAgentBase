"""基础示例：最简单的 HZAgentBase 使用方式。"""

from hz_agent_base import create_agent, run_agent

# 创建 agent（默认使用 deepseek-v4-flash）
agent = create_agent()

# 运行一次对话（thread_id 用于多用户隔离）
result = run_agent(agent, "2 + 2 等于多少？", thread_id="demo")

# 输出结果
for msg in result.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"Agent: {msg.content}")
