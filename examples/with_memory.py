"""示例：使用持久化记忆系统。"""

from hz_agent_base import create_agent, run_agent

# 创建带记忆的 agent
agent = create_agent(memory_path=".my_agent_memory/")

# 第一轮对话 — agent 会记住这些信息
result1 = run_agent(
    agent,
    "我叫小明，我喜欢用 Python 写代码",
    thread_id="demo",
)

for msg in result1.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"[第一轮] Agent: {msg.content}")
        break

# 第二轮对话 — agent 应该记得之前的对话
result2 = run_agent(
    agent,
    "我叫什么？我喜欢什么语言？",
    thread_id="demo",
)

for msg in result2.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"[第二轮] Agent: {msg.content}")
        break
