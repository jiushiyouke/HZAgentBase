# HZAgentBase

可复用的 Agent Harness 基础设施库。

基于 [Deep Agents](https://github.com/langchain-ai/deepagents) 和 [OpenHarness](https://github.com/HKUDS/OpenHarness) 构建，为上层业务项目提供开箱即用的 Agent 创建能力。

## 功能特性

- **权限系统** — 三种模式（DEFAULT / PLAN / FULL_AUTO），细粒度工具调用控制
- **Hook 系统** — 生命周期事件钩子（4 种类型：Command / Http / Prompt / Agent）
- **记忆系统** — 基于文件的持久化跨会话记忆，支持相关性搜索和自动提取
- **知识库 RAG** — 通过 Retriever 协议接入任意知识库实现，松耦合设计
- **文件审计** — 文件操作审计日志 + 变更追踪，支持 JSONL 持久化
- **提示词管理** — 目录式提示词加载（base.md + rules/*.md），支持共享规则
- **多 Agent 编排** — Coordinator / Worker 模式，每个 worker 独立提示词和工具集
- **多用户隔离** — 基于 LangGraph thread_id 的状态隔离，同一 agent 实例可并发服务多个用户
- **可插拔后端** — 由 Deep Agents 提供，支持本地 / 沙箱 / 远程执行环境
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

复制 `.env-example` 为 `.env` 并填入配置：

```bash
cp .env-example .env
```

支持多模型提供商，根据 `DEFAULT_MODEL` 的值自动选择对应的 API：

| 模型前缀 | 提供商 | 说明 |
|---------|--------|------|
| `deepseek-*` | DeepSeek | OpenAI 兼容，自动设置 base_url |
| `gpt-*` / `o1-*` / `o3-*` | OpenAI | 自动设置 base_url |
| `claude-*` | Anthropic | 需 `pip install langchain-anthropic` |
| `gemini-*` | Google Gemini | 需 `pip install langchain-google-genai` |
| 其他 | OpenAI 兼容 | 适用于 Ollama、vLLM 等本地服务 |

主要配置项：

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `DEFAULT_MODEL` | 默认模型名称 | `deepseek-v4-flash` |
| `MODEL_API_KEY` | API Key（统一配置） | — |
| `MODEL_BASE_URL` | API 地址（可选，通常不需要） | 各提供商自动设置 |
| `PERMISSION_MODE` | 权限模式 | `default` |
| `MEMORY_PATH` | 记忆存储路径 | `.memory` |
| `AUDIT_LOG_PATH` | 审计日志路径 | `.audit/audit.jsonl` |
| `KNOWLEDGE_TOP_K` | 知识库检索条数 | `5` |

## 中间件管道

`create_agent()` 按以下顺序组装中间件管道，每个中间件可拦截和修改模型请求：

```
1. PermissionMiddleware   ← 权限检查（默认开启）
2. HookMiddleware         ← 生命周期事件（需传入 hooks 参数）
3. MemoryMiddleware       ← 记忆注入/提取（需传入 memory_path）
4. KnowledgeMiddleware    ← 知识库 RAG 检索（需传入 retriever）
5. FilesystemMiddleware   ← 文件审计 + 变更追踪（需传入 filesystem=True）
6. [用户自定义 Middleware] ← 通过 middleware 参数传入
7. CoordinatorMiddleware  ← 多 Agent 编排（需传入 workers）
```

| 中间件 | 默认状态 | 启用方式 |
|--------|---------|---------|
| Permission | 开启 | 无需额外参数，可通过 `permissions` 自定义 |
| Hook | 关闭 | `hooks=HookRegistry(...)` |
| Memory | 关闭 | `memory_path=".memory/"` |
| Knowledge | 关闭 | `retriever=your_retriever` |
| Filesystem | 关闭 | `filesystem=True` 或 `filesystem={...}` |
| Coordinator | 关闭 | `workers=[WorkerConfig(...)]` |

## 权限系统

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

三种模式：
- **DEFAULT** — 写操作需要用户确认
- **PLAN** — 阻止所有写操作（只读模式）
- **FULL_AUTO** — 允许所有操作（需谨慎使用）

## Hook 系统

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

支持的事件：`SESSION_START`、`SESSION_END`、`PRE_TOOL_USE`、`POST_TOOL_USE`、`USER_PROMPT_SUBMIT`、`STOP`

## 记忆系统

```python
from hz_agent_base import create_agent

agent = create_agent(memory_path=".memory/")
```

记忆以 Markdown + YAML frontmatter 格式存储，支持：
- 自动从对话中提取记忆（基于关键词模式匹配）
- 基于 token 重叠的相关性搜索
- 按类型分类（user / feedback / project / reference）

## 知识库 RAG

HZAgentBase 通过 `Retriever` 协议接入知识库，不绑定具体实现：

```python
from hz_agent_base import create_agent, Retriever, RetrievalResult

# 实现 Retriever 协议（或使用 hz-knowledge-base 提供的实现）
class MyRetriever:
    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        # 检索逻辑...
        return [RetrievalResult(content="...", source="doc.md", score=0.9)]

agent = create_agent(
    retriever=MyRetriever(),
    knowledge_top_k=5,
)
```




## 文件审计

```python
agent = create_agent(filesystem=True)

# 或自定义配置
agent = create_agent(filesystem={
    "audit": True,           # 开启操作审计
    "track_changes": True,   # 开启变更追踪
    "log_path": ".audit/audit.jsonl",  # 审计日志路径
    "workspace": "/path/to/project",   # 工作目录
})
```

审计日志以 JSONL 格式记录每次文件操作（工具名、文件路径、操作类型、时间戳、是否成功）。

## 提示词管理

`system_prompt` 参数支持三种形式：

```python
# 1. 直接传字符串
agent = create_agent(system_prompt="你是一个助手。")

# 2. 传 .md 文件路径
agent = create_agent(system_prompt="./prompts/coordinator/base.md")

# 3. 传目录路径（自动加载 base.md + rules/*.md）
agent = create_agent(system_prompt="./prompts/coordinator/")
```

共享规则目录下的 `.md` 文件会自动拼接到所有 agent（含 workers）的提示词之后：

```python
agent = create_agent(
    system_prompt="./prompts/coordinator/",
    rules=["./prompts/shared/rules/"],  # 所有 agent 共享
)
```

## 多 Agent 编排

```python
from hz_agent_base import create_agent, run_agent, WorkerConfig

workers = [
    WorkerConfig(
        name="researcher",
        prompt="你是研究助手，负责搜索和分析信息。",
        tools=["web_search", "read_file", "glob"],
    ),
    WorkerConfig(
        name="coder",
        prompt_dir="./prompts/coder/",  # 从目录加载提示词
        tools=["write_file", "edit_file", "bash"],
    ),
]

agent = create_agent(
    workers=workers,
    rules=["./prompts/shared/rules/"],  # 共享规则
)

result = run_agent(agent, "研究 Python logging 最佳实践，然后写个配置文件")
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

## 自定义 Middleware

继承 `AgentMiddleware` 实现业务逻辑扩展：

```python
from hz_agent_base import create_agent, AgentMiddleware

class BusinessContextMiddleware(AgentMiddleware):
    def __init__(self, context: str):
        self.context = context

    def wrap_model_call(self, request, handler):
        enriched = request.system_prompt + "\n\n" + self.context
        return handler(request.override(system_prompt=enriched))

agent = create_agent(middleware=[BusinessContextMiddleware("当前环境: 生产")])
```

## 后端（Backend）

后端由 Deep Agents 提供，决定 Agent 工具（bash、文件读写等）在哪里执行。HZAgentBase 直接透传，不做额外封装。

| 后端 | 说明 |
|------|------|
| `LocalBackend` | 本地机器直接执行（默认） |
| `SandboxBackend` | Docker / VM 沙箱内执行，适合生产环境和多租户隔离 |
| `RemoteBackend` | 远程服务器执行，适合云函数和 K8s Job |

```python
from hz_agent_base import create_agent
from deepagents.backends import LocalShellBackend

# 指定后端
agent = create_agent(backend=LocalShellBackend())
```

不传 `backend` 参数时使用 Deep Agents 的默认后端。

## CLI 工具

```bash
# 交互式对话
hz-agent chat

# 带权限和审计
hz-agent chat --permission full_auto --filesystem

# 带共享规则
hz-agent chat --rules ./prompts/shared/rules/

# 单次执行
hz-agent run "帮我分析这段代码" --thread user-1

# 查看版本
hz-agent version
```

## create_agent() 参数参考

| 参数 | 类型 | 说明 |
|------|------|------|
| `model` | `str \| Any` | LLM 模型名称或实例，默认 deepseek-v4-flash |
| `tools` | `Sequence[Any]` | 自定义工具列表 |
| `system_prompt` | `str \| None` | 提示词（字符串 / .md 文件路径 / 目录路径） |
| `rules` | `list[str] \| None` | 共享规则目录列表，所有 agent 共享 |
| `permissions` | `PermissionSettings \| None` | 权限配置，默认 DEFAULT 模式 |
| `hooks` | `HookRegistry \| None` | Hook 注册表 |
| `memory_path` | `str \| None` | 记忆存储目录路径 |
| `retriever` | `Retriever \| None` | 知识库检索器（实现 Retriever 协议） |
| `knowledge_top_k` | `int` | 知识库每次检索条数，默认 5 |
| `filesystem` | `bool \| dict` | 文件审计配置，False 为关闭 |
| `workers` | `list[WorkerConfig] \| None` | Worker 配置列表，启用多 Agent 编排 |
| `middleware` | `Sequence[AgentMiddleware] \| None` | 自定义中间件列表 |
| `backend` | `BackendProtocol \| None` | 文件系统/沙箱后端 |

## 项目结构

```
HZAgentBase/
├── src/hz_agent_base/
│   ├── agent.py              # create_agent() / run_agent() 入口
│   ├── cli.py                # CLI 工具
│   ├── config.py             # 配置管理
│   ├── middleware/            # 中间件实现
│   │   ├── permission.py     # 权限中间件
│   │   ├── hook.py           # Hook 中间件
│   │   ├── memory.py         # 记忆中间件
│   │   ├── knowledge.py      # 知识库 RAG 中间件
│   │   └── filesystem.py     # 文件审计中间件
│   ├── permissions/           # 权限系统（Checker / Modes / Settings）
│   ├── hooks/                 # Hook 系统（Events / Registry / Executor）
│   ├── memory/                # 记忆系统（Manager / Relevance）
│   ├── knowledge/             # 知识库协议（Retriever Protocol）
│   ├── coordinator/           # 多 Agent 编排（Coordinator / Worker / Team）
│   ├── prompts/               # 提示词管理（PromptManager）
│   ├── tools/                 # 工具扩展
│   └── backends/              # 后端抽象
├── tests/                     # 单元测试（142 个用例）
├── examples/                  # 使用示例
│   ├── basic_agent.py         # 最简用法
│   ├── custom_permissions.py  # 权限控制
│   ├── multi_user.py          # 多用户隔离
│   ├── multi_agent.py         # 多 Agent 编排
│   ├── with_hooks.py          # Hook 系统
│   ├── with_memory.py         # 记忆系统
│   ├── with_knowledge.py      # 知识库 RAG
│   ├── with_prompts.py        # 提示词管理
│   ├── with_filesystem.py     # 文件审计
│   ├── custom_middleware.py   # 自定义中间件
│   └── server_integration.py  # FastAPI 服务器集成
└── docs/
    ├── technical_roadmap.md   # 技术路线图
    └── api_reference.md       # API 参考文档
```

## 致谢

本项目基于以下开源项目构建，特此致谢：

- **[Deep Agents](https://github.com/langchain-ai/deepagents)** — LangChain 官方 Agent Harness，提供 LangGraph 编排引擎、Middleware 管道架构、Backend 抽象层等核心能力
- **[OpenHarness](https://github.com/HKUDS/OpenHarness)** — Claude Code 的 Python 开源复刻，提供权限系统、Hook 系统、记忆系统、多 Agent 编排等参考实现

感谢两个项目的开发者和社区为开源 Agent 生态做出的贡献。

## 许可证

MIT License
