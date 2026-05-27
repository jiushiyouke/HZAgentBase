"""示例：多用户并发隔离。

HZAgentBase 通过 thread_id 实现多用户会话隔离。
同一个 agent 实例可以同时服务多个用户，互不干扰。
"""

from hz_agent_base import create_agent, run_agent

# 创建一个 agent，全局复用
agent = create_agent()

# 用户 A 的对话
result_a = run_agent(
    agent,
    "记住：我的名字是小明，我喜欢 Python",
    thread_id="user-a-session-1",
)

# 用户 B 的对话（完全隔离，不知道用户 A 说了什么）
result_b = run_agent(
    agent,
    "记住：我的名字是小红，我喜欢 JavaScript",
    thread_id="user-b-session-1",
)

# 验证隔离：问各自的名字
result_a2 = run_agent(agent, "我的名字是什么？", thread_id="user-a-session-1")
result_b2 = run_agent(agent, "我的名字是什么？", thread_id="user-b-session-1")

print("用户 A 的回答：")
for msg in result_a2.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"  {msg.content}")
        break

print("用户 B 的回答：")
for msg in result_b2.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"  {msg.content}")
        break
