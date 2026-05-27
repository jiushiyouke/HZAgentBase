# HZAgentBase

可复用的 Agent Harness 基础设施库。

基于 [Deep Agents](https://github.com/langchain-ai/deepagents) 和 [OpenHarness](https://github.com/HKUDS/OpenHarness) 构建。

## 功能特性

- **权限系统** — 三种模式（DEFAULT / PLAN / FULL_AUTO），细粒度工具调用控制
- **Hook 系统** — 生命周期事件钩子（4 种类型：Command / Http / Prompt / Agent）
- **记忆系统** — 基于文件的持久化跨会话记忆，支持相关性搜索
- **多 Agent 编排** — Coordinator / Worker 模式，支持团队管理
- **多用户隔离** — 基于 LangGraph thread_id 的状态隔离，同一 agent 实例可并发服务多个用户
- **可插拔后端** — 本地 / 沙箱 / 远程执行环境
- **CLI 工具** — 命令行交互界面

## 安装

```bash
pip install hz-agent-base
```

或从源码安装：

```bash
git clone https://github.com/jiushiyouke/HZAgentBase.git
cd HZAgentBase
pip install -e .
```

## 快速开始

```python
from hz_agent_base import create_agent, run_agent

# 创建 agent（全局只需一次，线程安全）
agent = create_agent()

# 单用户使用
result = run_agent(agent, "你好，请介绍一下自己")

# 多用户使用（通过 thread_id 隔离）
result_a = run_agent(agent, "帮我分析数据", thread_id="user-a")
result_b = run_agent(agent, "写一个 Python 脚本", thread_id="user-b")
```

## 配置

设置 DeepSeek API Key：

```bash
export DEEPSEEK_API_KEY="your-api-key"
```

## 多用户场景

HZAgentBase 支持多用户并发使用，用户之间完全隔离：

```python
from hz_agent_base import create_agent, run_agent

# 创建一次，全局复用
agent = create_agent()

# Web 服务示例
from fastapi import FastAPI
app = FastAPI()

@app.post("/chat")
async def chat(user_id: str, message: str):
    # 每个用户使用独立的 thread_id
    result = run_agent(agent, message, thread_id=f"user-{user_id}")
    return {"response": extract_reply(result)}
```

**隔离机制说明**：
- `create_agent()` 返回的 `CompiledStateGraph` 是无状态的图定义，可安全共享
- 每次 `run_agent()` 调用通过 `thread_id` 创建独立的执行上下文
- 不同用户的对话历史、文件状态、中间数据完全隔离
- 无全局可变状态，支持高并发场景

## 自定义权限

```python
from hz_agent_base import create_agent, PermissionSettings, PermissionMode

agent = create_agent(
    permissions=PermissionSettings(
        mode=PermissionMode.DEFAULT,
        allowed_tools=["read_file", "glob", "grep"],
        denied_tools=["bash"],
        denied_paths=["**/.env*", "**/secrets/**"],
    ),
)
```

## 使用 Hook

```python
from hz_agent_base import create_agent, HookRegistry, HookEvent
from hz_agent_base.hooks import CommandHookDefinition

registry = HookRegistry()
registry.register(CommandHookDefinition(
    event=HookEvent.POST_TOOL_USE,
    command='echo "Tool used" >> audit.log',
))

agent = create_agent(hooks=registry)
```

## 项目结构

```
HZAgentBase/
├── src/hz_agent_base/
│   ├── agent.py              # create_agent() / run_agent() 入口
│   ├── cli.py                # CLI 工具
│   ├── middleware/            # 中间件（权限 / Hook / 记忆）
│   ├── permissions/           # 权限系统
│   ├── hooks/                 # Hook 系统
│   ├── memory/                # 记忆系统
│   ├── coordinator/           # 多 Agent 编排
│   ├── tools/                 # 工具扩展
│   └── backends/              # 后端抽象
├── examples/                  # 使用示例
└── docs/                      # 文档
```

## 致谢

本项目基于以下开源项目构建，特此致谢：

- **[Deep Agents](https://github.com/langchain-ai/deepagents)** — LangChain 官方 Agent Harness，提供 LangGraph 编排引擎、Middleware 管道架构、Backend 抽象层等核心能力
- **[OpenHarness](https://github.com/HKUDS/OpenHarness)** — Claude Code 的 Python 开源复刻，提供权限系统、Hook 系统、记忆系统、多 Agent 编排等参考实现

感谢两个项目的开发者和社区为开源 Agent 生态做出的贡献。

## 许可证

MIT License
