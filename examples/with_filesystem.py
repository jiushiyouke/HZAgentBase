"""示例：文件操作审计和变更追踪。"""

from hz_agent_base import create_agent, run_agent

# 启用文件审计（默认配置）
agent = create_agent(
    filesystem=True,
)

# 也可以自定义配置
# agent = create_agent(
#     filesystem={
#         "audit": True,           # 记录文件操作
#         "track_changes": True,   # 记录变更内容
#         "workspace": "./project", # 限制文件操作范围
#         "log_path": "audit.jsonl", # 审计日志持久化路径
#     },
# )

# 使用
result = run_agent(
    agent,
    "创建一个 hello.py 文件，内容是 print('hello')",
    thread_id="demo",
)

for msg in result.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"Agent: {msg.content}")
