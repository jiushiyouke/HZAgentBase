"""示例：使用 Hook 系统监控工具调用。"""

from hz_agent_base import (
    create_agent,
    run_agent,
    HookRegistry,
    HookEvent,
)
from hz_agent_base.hooks import CommandHookDefinition

# 创建 Hook 注册表
registry = HookRegistry()

# 注册 Hook：记录所有工具调用
registry.register(CommandHookDefinition(
    event=HookEvent.POST_TOOL_USE,
    command='echo "Tool used: $HZ_HOOK_PAYLOAD" >> tool_usage.log',
    block_on_failure=False,
))

# 创建带 Hook 的 agent
agent = create_agent(hooks=registry)

# 运行
result = run_agent(
    agent,
    "显示当前目录内容",
    thread_id="demo",
)

for msg in result.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"Agent: {msg.content}")
