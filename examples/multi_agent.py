"""示例：多 Agent 协作编排。"""

from hz_agent_base import create_agent, run_agent
from hz_agent_base.coordinator import CoordinatorMiddleware, WorkerConfig

# 定义工作 Agent
workers = [
    WorkerConfig(
        name="researcher",
        prompt="你是研究助手，负责搜索和分析信息。",
        tools=["web_search", "read_file", "glob"],
        team="research",
        color="green",
    ),
    WorkerConfig(
        name="coder",
        prompt="你是编程助手，负责编写和修改代码。",
        tools=["write_file", "edit_file", "bash"],
        team="development",
        color="blue",
    ),
]

# 创建带 Coordinator 的 agent
agent = create_agent(
    middleware=[CoordinatorMiddleware(workers)],
)

# 运行需要协作的任务
result = run_agent(
    agent,
    "研究 Python logging 最佳实践，然后创建一个日志配置文件",
    thread_id="demo",
)

for msg in result.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"Agent: {msg.content}")
