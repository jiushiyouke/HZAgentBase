"""Basic agent example - simplest usage of HZAgentBase."""

from hz_agent_base import create_agent

# Create a basic agent with default settings (deepseek-v4-flash)
agent = create_agent()

# Run a simple query
result = agent.invoke({
    "messages": [
        {"role": "user", "content": "What is 2 + 2?"}
    ]
})

# Print the response
for msg in result.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"Agent: {msg.content}")
