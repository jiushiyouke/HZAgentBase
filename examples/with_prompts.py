"""示例：提示词和规则管理。

目录结构：
    prompts/
    ├── shared/rules/
    │   └── safety.md          # 共享安全规则
    ├── coordinator/
    │   ├── base.md            # 协调者人设
    │   └── rules/delegation.md
    └── researcher/
        ├── base.md            # 研究员人设
        └── rules/search.md
"""

from hz_agent_base import create_agent, run_agent, WorkerConfig

# 方式一：直接传字符串（最简单）
agent_simple = create_agent(
    system_prompt="你是一个数据分析助手。回答要简洁、用中文。",
)

# 方式二：从目录加载（推荐生产使用）
# 目录下有 base.md 和 rules/ 子目录
# agent = create_agent(
#     system_prompt="./prompts/coordinator/",
#     rules=["./prompts/shared/rules/"],
# )

# 方式三：多 Agent 各自独立的提示词目录
agent_multi = create_agent(
    system_prompt="你是协调者，负责分配任务给合适的 worker。",
    rules=["./prompts/shared/rules/"] if __import__("os").path.exists("./prompts/shared/rules/") else None,
    workers=[
        WorkerConfig(
            name="researcher",
            prompt="你是研究助手，擅长搜索和分析信息。",
            tools=["web_search", "read_file"],
        ),
        WorkerConfig(
            name="coder",
            prompt="你是编程助手，擅长编写和修改代码。",
            tools=["write_file", "edit_file"],
        ),
    ],
)

# 使用
result = run_agent(agent_simple, "用一句话介绍 Python 的 logging 模块", thread_id="demo")
for msg in result.get("messages", []):
    if hasattr(msg, "type") and msg.type == "ai":
        print(f"Agent: {msg.content}")
