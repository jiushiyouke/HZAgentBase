"""Example: Agent with custom permission settings."""

from hz_agent_base import create_agent, PermissionSettings, PermissionMode

# Create an agent with restricted permissions
agent = create_agent(
    permissions=PermissionSettings(
        mode=PermissionMode.DEFAULT,
        # Only allow these tools
        allowed_tools=["read_file", "glob", "grep"],
        # Never allow these tools
        denied_tools=["bash"],
        # Block access to sensitive paths
        denied_paths=["**/.env*", "**/secrets/**"],
    ),
)

# This will work (read-only)
result = agent.invoke({
    "messages": [
        {"role": "user", "content": "List files in the current directory"}
    ]
})

for msg in result.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"Agent: {msg.content}")
