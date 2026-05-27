"""示例：自定义权限配置。"""

from hz_agent_base import (
    create_agent,
    run_agent,
    PermissionSettings,
    PermissionMode,
)

# 创建带有限制权限的 agent
agent = create_agent(
    permissions=PermissionSettings(
        mode=PermissionMode.DEFAULT,
        # 只允许这些工具
        allowed_tools=["read_file", "glob", "grep"],
        # 禁止这些工具
        denied_tools=["bash"],
        # 禁止访问敏感路径
        denied_paths=["**/.env*", "**/secrets/**"],
    ),
)

# 运行（只读操作会被允许）
result = run_agent(
    agent,
    "列出当前目录的文件",
    thread_id="demo",
)

for msg in result.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"Agent: {msg.content}")
