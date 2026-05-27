"""Example: Agent with persistent memory."""

from hz_agent_base import create_agent

# Create an agent with memory
agent = create_agent(
    memory_path=".my_agent_memory/",
)

# First interaction - agent will remember this
result = agent.invoke({
    "messages": [
        {"role": "user", "content": "My name is Alice and I prefer Python over JavaScript."}
    ]
})

for msg in result.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"Agent: {msg.content}")

# Second interaction - agent should remember
result = agent.invoke({
    "messages": [
        {"role": "user", "content": "What's my name and language preference?"}
    ]
})

for msg in result.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"Agent: {msg.content}")
