"""示例：多用户并发使用，用户之间完全隔离。

HZAgentBase 支持多用户并发使用同一个 agent 实例，
通过 thread_id 实现用户状态隔离。
"""

from hz_agent_base import create_agent, run_agent


# 创建 agent（全局只需一次，线程安全）
agent = create_agent()

# 模拟多个用户同时使用
# 用户 A：数据分析任务
result_a = run_agent(
    agent,
    "帮我分析一下 Python 的 logging 模块",
    thread_id="user-a-session-1",
)

# 用户 B：代码编写任务
result_b = run_agent(
    agent,
    "写一个快速排序算法",
    thread_id="user-b-session-1",
)

# 用户 A 继续对话（同一 thread_id 保持上下文）
result_a2 = run_agent(
    agent,
    "能给我一个具体的使用示例吗？",
    thread_id="user-a-session-1",
)

# 输出结果
for msg in result_a.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"[用户 A] {msg.content[:100]}...")
        break

for msg in result_b.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"[用户 B] {msg.content[:100]}...")
        break

for msg in result_a2.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"[用户 A 续] {msg.content[:100]}...")
        break
