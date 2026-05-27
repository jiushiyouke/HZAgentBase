"""Example: Multi-agent coordination."""

from hz_agent_base import create_agent
from hz_agent_base.coordinator import CoordinatorMiddleware, WorkerConfig

# Define worker agents
workers = [
    WorkerConfig(
        name="researcher",
        prompt="You are a research assistant. Search and analyze information.",
        tools=["web_search", "read_file", "glob"],
        team="research",
        color="green",
    ),
    WorkerConfig(
        name="coder",
        prompt="You are a coding assistant. Write and edit code.",
        tools=["write_file", "edit_file", "bash"],
        team="development",
        color="blue",
    ),
]

# Create agent with coordinator
agent = create_agent(
    middleware=[CoordinatorMiddleware(workers)],
)

# Run a task that requires coordination
result = agent.invoke({
    "messages": [
        {
            "role": "user",
            "content": "Research best practices for Python logging, then create a sample logging configuration file."
        }
    ]
})

for msg in result.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"Agent: {msg.content}")
