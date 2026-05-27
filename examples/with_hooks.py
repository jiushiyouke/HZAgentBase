"""Example: Agent with hook system for lifecycle events."""

from hz_agent_base import (
    create_agent,
    HookRegistry,
    HookEvent,
)
from hz_agent_base.hooks import CommandHookDefinition

# Create a hook registry
registry = HookRegistry()

# Register a hook that logs all tool calls
registry.register(CommandHookDefinition(
    event=HookEvent.POST_TOOL_USE,
    command='echo "Tool used: $HZ_HOOK_PAYLOAD" >> tool_usage.log',
    block_on_failure=False,
))

# Register a hook that blocks dangerous commands
registry.register(CommandHookDefinition(
    event=HookEvent.PRE_TOOL_USE,
    matcher="bash",
    command='echo "$HZ_HOOK_PAYLOAD" | python -c "import sys,json; d=json.load(sys.stdin); exit(0 if \'rm\' in d.get(\'arguments\',{}).get(\'command\',\'\') else 1)"',
    block_on_failure=True,
))

# Create agent with hooks
agent = create_agent(
    hooks=registry,
)

# Run a query
result = agent.invoke({
    "messages": [
        {"role": "user", "content": "Show me the current directory contents"}
    ]
})

for msg in result.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"Agent: {msg.content}")
