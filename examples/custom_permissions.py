"""示例：自定义权限控制。"""

from hz_agent_base import create_agent, run_agent, PermissionSettings, PermissionMode

# 方式一：PLAN 模式（只读，禁止写操作）
agent_readonly = create_agent(
    permissions=PermissionSettings(mode=PermissionMode.PLAN),
)

# 方式二：自定义工具白名单
agent_limited = create_agent(
    permissions=PermissionSettings(
        mode=PermissionMode.DEFAULT,
        allowed_tools=["read_file", "glob", "grep"],  # 只允许读取类工具
        denied_tools=["bash", "eval"],                 # 明确禁止危险工具
        denied_paths=["**/.env*", "**/secrets/**"],    # 禁止访问敏感路径
    ),
)

# 方式三：FULL_AUTO 模式（不确认，全自动）
agent_auto = create_agent(
    permissions=PermissionSettings(mode=PermissionMode.FULL_AUTO),
)

# 使用
result = run_agent(agent_limited, "列出当前目录的文件", thread_id="demo")
for msg in result.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"Agent: {msg.content}")
