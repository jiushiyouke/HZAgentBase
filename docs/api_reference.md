# HZAgentBase API 参考

## 核心 API

### `create_agent()`

创建一个带 HZAgentBase harness 的 Agent。

```python
from hz_agent_base import create_agent

agent = create_agent(
    model="deepseek-v4-flash",
    tools=[...],
    system_prompt="...",
    rules=["./rules/"],
    permissions=PermissionSettings(...),
    hooks=HookRegistry(...),
    memory_path=True,  # 或 ".memory/"
    memory_isolate_by_user=True,
    retriever=my_retriever,
    knowledge_top_k=5,
    filesystem=True,
    conversation_history=True,
    evolution_memory=True,
    human_approval_rules=True,
    sanitizer=True,
    guardrails=True,
    workers=[WorkerConfig(...)],
    middleware=[MyMiddleware()],
    backend=LocalBackend(),
    cancellation_checker=my_checker,
    stop_condition=my_condition,
    max_retries=2,
    model_kwargs={"temperature": 0.7, "reasoning_effort": "high"},
)
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model` | `str \| Any \| None` | `None` | LLM 模型名称或实例。None 时使用 `DEFAULT_MODEL` 环境变量 |
| `tools` | `Sequence[Any] \| None` | `None` | 自定义工具列表 |
| `system_prompt` | `str \| None` | `None` | 提示词。支持字符串、`.md` 文件路径、目录路径 |
| `rules` | `list[str] \| None` | `None` | 共享规则目录列表。目录下 `.md` 文件自动加载，所有 agent 共享 |
| `permissions` | `PermissionSettings \| None` | `None` | 权限配置。None 时使用 DEFAULT 模式 |
| `hooks` | `HookRegistry \| None` | `None` | Hook 注册表 |
| `memory_path` | `str \| bool \| None` | `None` | 记忆存储路径。True 使用默认路径 `.memory` |
| `memory_isolate_by_user` | `bool` | `True` | 记忆按用户隔离，每个用户独立记忆目录 |
| `retriever` | `Retriever \| None` | `None` | 知识库检索器 |
| `knowledge_top_k` | `int` | `5` | 每次检索 Top-K 条 |
| `filesystem` | `bool \| dict` | `False` | 文件审计。True 使用默认配置 |
| `conversation_history` | `bool \| dict` | `False` | 对话历史管理。True 使用默认配置 |
| `evolution_memory` | `bool \| dict` | `False` | 进化记忆。True 使用默认配置 |
| `human_approval_rules` | `bool \| list[ApprovalRule] \| None` | `None` | 人工审批。True 使用默认规则 |
| `sanitizer` | `bool \| dict` | `False` | 输出清洗。True 使用默认配置 |
| `guardrails` | `bool \| dict` | `False` | 内容护栏。True 使用默认配置 |
| `workers` | `list[WorkerConfig] \| None` | `None` | Worker 配置列表 |
| `middleware` | `Sequence[AgentMiddleware \| tuple] \| None` | `None` | 自定义中间件列表，支持 `(middleware, priority)` 元组 |
| `backend` | `BackendProtocol \| None` | `None` | 文件系统/沙箱后端 |
| `cancellation_checker` | `CancellationChecker \| None` | `None` | 取消检查器，实现 `is_cancelled(thread_id)` 方法 |
| `stop_condition` | `StopCondition \| None` | `None` | 终止条件，实现 `should_stop(messages)` 方法 |
| `max_retries` | `int` | `2` | LLM 调用失败时的最大重试次数（指数退避） |
| `api_key` | `str \| None` | `None` | API Key 覆盖，多租户使用 |
| `base_url` | `str \| None` | `None` | Base URL 覆盖，多租户使用 |
| `model_kwargs` | `dict \| None` | `None` | 额外模型参数（temperature, reasoning_effort 等） |

**返回值：** `CompiledStateGraph` — 线程安全的编译 Agent 实例。

---

### `run_agent()`

运行 Agent 处理一条消息。

```python
from hz_agent_base import run_agent

result = run_agent(
    agent,
    "帮我分析这段代码",
    thread_id="user-1",
    user_id="alice",
)
```

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `agent` | `CompiledStateGraph` | `create_agent()` 返回的实例 |
| `message` | `str` | 用户消息 |
| `thread_id` | `str \| None` | 线程 ID，用于多用户隔离。None 时自动生成 |
| `user_id` | `str \| None` | 用户标识，用于日志记录 |
| `recursion_limit` | `int` | Agent 最大执行步数，防止死循环。默认从 `RECURSION_LIMIT` 环境变量读取（25） |

**返回值：** `dict[str, Any]` — 包含 `messages` 等字段的响应状态。

---

### `arun_agent()`

异步版本的 `run_agent()`，使用 `agent.ainvoke()` 调用。参数和返回值与 `run_agent()` 完全相同。

```python
from hz_agent_base import arun_agent

result = await arun_agent(
    agent,
    "帮我分析这段代码",
    thread_id="user-1",
    user_id="alice",
)
```

---

### `run_agent_stream()`

同步流式运行 Agent，逐 token 返回 LLM 输出。使用 `stream_events` 获取 token 级流式数据。

```python
from hz_agent_base import run_agent_stream

for token in run_agent_stream(agent, "写个报告"):
    print(token, end="", flush=True)
```

**参数：** 与 `run_agent()` 相同。

**返回值：** `Generator[str, None, None]` — 每次 yield 一个 token 字符串。

---

### `arun_agent_stream()`

异步流式版本，适用于 FastAPI + SSE 等异步场景。

```python
from hz_agent_base import arun_agent_stream

async for token in arun_agent_stream(agent, "写个报告"):
    await send_to_client(token)
```

**参数：** 与 `run_agent()` 相同。

**返回值：** `AsyncGenerator[str, None]` — 每次 yield 一个 token 字符串。

**FastAPI + SSE 示例：**

```python
from fastapi.responses import StreamingResponse

@app.post("/chat")
async def chat(message: str):
    async def generate():
        async for token in arun_agent_stream(agent, message):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

---

## 模型参数配置

通过 `model_kwargs` 传递额外参数给底层模型类。

```python
from hz_agent_base import create_agent

# DeepSeek 思考模式
agent = create_agent(
    model="deepseek-v4-pro",
    model_kwargs={
        "temperature": 0.1,
        "reasoning_effort": "high",      # 思考深度
        "reasoning": {"type": "enabled"}, # 启用思考模式
    }
)

# OpenAI 参数
agent = create_agent(
    model="gpt-4",
    model_kwargs={
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 4096,
    }
)
```

**各提供商支持的参数：**

| 提供商 | 参数 |
|--------|------|
| DeepSeek | temperature, reasoning_effort, reasoning, top_p, max_tokens, presence_penalty, frequency_penalty, seed |
| OpenAI | temperature, top_p, max_tokens, presence_penalty, frequency_penalty, seed, logprobs |
| Anthropic | temperature, top_k, top_p, max_tokens, stop_sequences |
| Gemini | temperature, top_p, top_k, max_output_tokens, stop_sequences |

---

## 权限系统

### `PermissionSettings`

```python
from hz_agent_base import PermissionSettings, PermissionMode

settings = PermissionSettings(
    mode=PermissionMode.DEFAULT,
    allowed_tools=["read_file", "glob", "grep"],
    denied_tools=["bash"],
    denied_paths=["**/.env*", "**/secrets/**"],
    denied_commands=["rm -rf", "DROP TABLE"],
)
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `mode` | `PermissionMode` | 权限模式 |
| `allowed_tools` | `list[str]` | 允许的工具列表。空表示允许所有 |
| `denied_tools` | `list[str]` | 拒绝的工具列表 |
| `denied_paths` | `list[str]` | 拒绝访问的路径 glob 模式 |
| `denied_commands` | `list[str]` | 拒绝的命令模式 |

> **注意：** 敏感路径（SSH 密钥、云凭证等）由系统内置的 `SENSITIVE_PATH_PATTERNS` 常量定义，始终拒绝访问，不可通过实例配置。

### `PermissionMode`

```python
class PermissionMode(Enum):
    DEFAULT = "default"      # 写操作需确认
    PLAN = "plan"            # 阻止写操作
    FULL_AUTO = "full_auto"  # 允许所有操作
```

---

## Hook 系统

### `HookRegistry`

```python
from hz_agent_base import HookRegistry, HookEvent
from hz_agent_base.hooks import (
    CommandHookDefinition,
    HttpHookDefinition,
    PromptHookDefinition,
    AgentHookDefinition,
)

registry = HookRegistry()

# 注册不同类型的 Hook
registry.register(CommandHookDefinition(
    event=HookEvent.POST_TOOL_USE,
    command='echo "Tool used"',
    block_on_failure=False,
))

registry.register(HttpHookDefinition(
    event=HookEvent.SESSION_START,
    url="https://example.com/webhook",
))
```

### `HookEvent`

```python
class HookEvent(Enum):
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    USER_PROMPT_SUBMIT = "user_prompt_submit"
```

---

## 记忆系统

### `MemoryManager`

```python
from hz_agent_base.memory import MemoryManager

manager = MemoryManager(".memory/")

# 添加记忆
manager.add_memory(
    title="用户偏好",
    content="用户偏好使用 Python 3.11",
    memory_type="user",
    description="用户的语言版本偏好",
)

# 列出记忆
memories = manager.list_memories()

# 从对话中自动提取记忆
saved = manager.extract_and_save(messages, response)
```

### `select_relevant_memories()`

```python
from hz_agent_base.memory import select_relevant_memories

memories = select_relevant_memories(
    query="Python 版本",
    memory_path=".memory/",
    max_results=5,
)
```

---

## 知识库协议

### `Retriever`（Protocol）

任何实现了 `retrieve()` 方法的对象均可作为知识库检索器：

```python
from hz_agent_base import Retriever, RetrievalResult

class MyRetriever:
    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        return [RetrievalResult(
            content="文档内容...",
            source="doc.md",
            score=0.9,
        )]
```

### `RetrievalResult`

```python
@dataclass(frozen=True)
class RetrievalResult:
    content: str       # 文档片段内容
    source: str = ""   # 来源标识（文件名、URL 等）
    score: float = 0.0 # 相关性分数 0~1
```

---

## 提示词管理

### `PromptManager`

```python
from hz_agent_base import PromptManager

# 从目录加载（base.md + rules/*.md）
pm = PromptManager("./prompts/coordinator/")
prompt = pm.build()

# 带共享规则
pm = PromptManager(
    "./prompts/coordinator/",
    shared_rules=["./prompts/shared/rules/"],
)
prompt = pm.build()

# 从单个文件加载
pm = PromptManager.from_file("./prompts/base.md")
prompt = pm.build()
```

### `load_prompt()`

便捷函数，自动判断输入类型：

```python
from hz_agent_base.prompts.manager import load_prompt

# None → 返回默认提示词
prompt = load_prompt(None)

# 字符串 → 直接作为提示词文本
prompt = load_prompt("你是一个助手。")

# .md 文件路径 → 从文件加载
prompt = load_prompt("./prompts/base.md")

# 目录路径 → 加载 base.md + rules/*.md
prompt = load_prompt("./prompts/coordinator/")

# 带共享规则
prompt = load_prompt("./prompts/coordinator/", shared_rules=["./rules/"])
```

---

## 多 Agent 编排

### `WorkerConfig`

```python
from hz_agent_base import WorkerConfig

worker = WorkerConfig(
    name="researcher",              # Worker 名称
    prompt="你是研究助手。",         # 提示词（字符串）
    prompt_dir="./prompts/researcher/",  # 或从目录加载（与 prompt 二选一）
    tools=["web_search", "read_file"],   # 可用工具列表
    model=None,                     # 可选：独立模型
    team="research",                # 团队名称
    color="green",                  # 日志颜色标识
)
```

---

## 自定义 Middleware

### `AgentMiddleware`

继承并实现 `wrap_model_call()` 方法：

```python
from hz_agent_base import AgentMiddleware

class MyMiddleware(AgentMiddleware):
    def wrap_model_call(self, request, handler):
        # request: ModelRequest 数据类
        #   - request.system_prompt: str
        #   - request.messages: list
        #   - request.tools: list
        #   - request.override(...): 创建修改后的新请求

        # 修改请求
        modified = request.override(system_prompt="新的提示词")

        # 调用下一个 middleware 或模型
        response = handler(modified)

        # 后处理
        return response
```

`ModelRequest` 是 Deep Agents 定义的数据类，关键属性：
- `system_prompt: str` — 系统提示词
- `messages: list` — 消息列表
- `tools: list` — 可用工具列表
- `override(**kwargs)` — 创建修改后的新实例（不修改原对象）

**中间件优先级：**

自定义中间件可通过 `(middleware, priority)` 元组指定执行位置：

```python
from hz_agent_base.utils.constants import BEFORE_ALL, AFTER_ALL, DEFAULT

agent = create_agent(
    middleware=[
        (RequestLogger(), BEFORE_ALL),     # 最前面
        (BusinessContext()),                # 默认位置（DEFAULT=30）
        (OutputSanitizer(), AFTER_ALL),    # 最后面
    ],
)
```

可用常量（数字越小越先执行）：

| 常量 | 值 | 说明 |
|------|-----|------|
| `BEFORE_ALL` | 0 | 最前面 |
| `PERMISSION` | 5 | 权限中间件位置 |
| `HUMAN_APPROVAL` | 8 | 人工审批中间件位置 |
| `HOOKS` | 10 | Hook 中间件位置 |
| `MEMORY` | 20 | 记忆中间件位置 |
| `AGENT_MEMORY` | 22 | 进化记忆中间件位置 |
| `KNOWLEDGE` | 25 | 知识库中间件位置 |
| `CONVERSATION_HISTORY` | 28 | 对话历史中间件位置 |
| `DEFAULT` | 30 | 用户自定义中间件默认位置 |
| `GUARDRAILS` | 32 | 内容护栏中间件位置 |
| `SANITIZER` | 33 | 输出清洗中间件位置 |
| `AUDIT` | 35 | 文件审计中间件位置 |
| `RESILIENT` | 40 | 容错中间件位置 |
| `COORDINATOR` | 50 | 多 Agent 编排中间件位置 |
| `AFTER_ALL` | 100 | 最后面 |

---

## 文件审计

### `FileAuditMiddleware`

通过 `create_agent(filesystem=True)` 启用，或传入配置字典：

```python
agent = create_agent(filesystem={
    "audit": True,           # 开启操作审计
    "track_changes": True,   # 开启变更追踪
    "log_path": ".audit/audit.jsonl",  # 审计日志路径
    "workspace": "/path/to/project",   # 工作目录
})
```

审计日志 JSONL 格式：

```json
{
    "timestamp": "2025-01-01T12:00:00",
    "tool_name": "write_file",
    "file_path": "/path/to/file.py",
    "operation": "write",
    "thread_id": "user-1",
    "diff": "--- a/file.py\n+++ b/file.py\n...",
    "success": true
}
```

---

## 容错机制

### `ResilientMiddleware`

容错中间件，提供重试、取消、终止条件能力。默认开启（`max_retries=2`）。

```python
from hz_agent_base import create_agent, CancellationChecker, StopCondition

# 默认容错（重试 2 次，超时 600s，递归限制 25 步）
agent = create_agent()

# 自定义重试次数
agent = create_agent(max_retries=3)

# 带取消检查
agent = create_agent(cancellation_checker=my_checker)

# 带终止条件
agent = create_agent(stop_condition=my_condition)

# 运行时限制递归深度
result = run_agent(agent, "你好", recursion_limit=10)
```

**容错执行流程：**

```
wrap_model_call 被调用
  ├── 1. 检查取消信号 → 已取消？返回"请求已被取消"
  ├── 2. 检查终止条件（调用前） → 应停止？返回"已满足终止条件"
  ├── 3. 调用模型（带重试）
  │     ├── attempt 1 → 成功 → 继续
  │     ├── attempt 1 → 失败 → 等待 1s
  │     ├── attempt 2 → 成功 → 继续
  │     └── attempt 2 → 失败 → 返回"模型暂时不可用"
  └── 4. 检查终止条件（调用后） → 应停止？直接返回结果
```

### `CancellationChecker`（Protocol）

取消检查器协议，检查用户是否已取消当前请求。

```python
from hz_agent_base import CancellationChecker

class RedisCancellationChecker:
    def __init__(self, redis_client):
        self.redis = redis_client

    def is_cancelled(self, thread_id: str) -> bool:
        return self.redis.exists(f"cancel:{thread_id}")
```

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `is_cancelled` | `thread_id: str` | `bool` | True 表示已取消，Agent 应终止 |

### `StopCondition`（Protocol）

终止条件协议，检查 Agent 是否应停止循环。

```python
from hz_agent_base import StopCondition

class MaxRoundsCondition:
    def __init__(self, max_rounds: int = 5):
        self.max_rounds = max_rounds

    def should_stop(self, messages: list) -> bool:
        ai_count = sum(1 for m in messages if getattr(m, "type", "") == "ai")
        return ai_count >= self.max_rounds
```

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `should_stop` | `messages: list` | `bool` | True 表示应终止，Agent 停止循环 |

---

## CLI 工具

HZAgentBase 提供命令行工具，用于开发调试和运维排查。

### 命令总览

```bash
hz-agent help                    # 使用示例和快速指引
hz-agent config show|check|path  # 配置管理
hz-agent chat [--stream]         # 交互式对话
hz-agent run [--stream]          # 单次执行
hz-agent memory list|show|search|clear  # 记忆管理
hz-agent audit show|stats|export|verify # 审计日志
hz-agent version                 # 版本信息
```

### `hz-agent help`

显示使用示例、常用命令、支持的模型列表和文档链接。

### `hz-agent config`

配置管理命令组。

| 子命令 | 说明 |
|--------|------|
| `config show` | 显示所有加载的配置（API Key 脱敏显示） |
| `config check` | 检查 .env 配置、Python 版本、依赖安装、API 连通性 |
| `config path` | 显示 .env 文件的加载路径 |

### `hz-agent chat`

交互式对话。

| 选项 | 说明 |
|------|------|
| `--model` | 指定模型（默认 deepseek-v4-flash） |
| `--auto` | 全自动模式（不需确认） |
| `--plan` | 只读模式（阻止写操作） |
| `--memory` | 记忆目录路径 |
| `--rules` | 共享规则目录路径 |
| `--prompt` | 系统提示词 |
| `--filesystem` | 开启文件审计 |
| `--stream` | 流式输出（逐字显示） |
| `--api-key` | API Key 覆盖（多租户测试） |

### `hz-agent run`

单次执行并输出结果。

| 选项 | 说明 |
|------|------|
| `--model` | 指定模型 |
| `--auto` | 全自动模式 |
| `--thread` | 指定线程 ID |
| `--stream` | 流式输出 |
| `--output json` | JSON 格式输出（方便脚本处理） |
| `--api-key` | API Key 覆盖 |

### `hz-agent memory`

记忆管理命令组。

| 子命令 | 说明 |
|--------|------|
| `memory list [--path]` | 列出所有记忆（显示名称、类型、描述） |
| `memory show <name> [--path]` | 查看指定记忆的完整内容 |
| `memory search <query> [--path] [--limit]` | 搜索相关记忆 |
| `memory clear [--path] [--confirm]` | 清空所有记忆（需确认） |

### `hz-agent audit`

审计日志管理命令组。

| 子命令 | 说明 |
|--------|------|
| `audit show [--limit] [--tool] [--file]` | 查看审计日志（支持过滤） |
| `audit stats` | 统计汇总（总操作数、成功率、工具排行、操作类型分布） |
| `audit export [--output]` | 导出审计日志为 CSV 文件 |
| `audit verify` | 校验审计日志的 HMAC 签名完整性 |

### `hz-agent version`

显示版本号、默认模型和 API 地址。

---

## 对话历史管理

### `ConversationHistoryMiddleware`

```python
from hz_agent_base import create_agent

# 默认配置（截断模式，16000 tokens）
agent = create_agent(conversation_history=True)

# 自定义配置
agent = create_agent(conversation_history={
    "max_tokens": 16000,
    "strategy": "truncate",  # truncate / sliding_window / summary
    "reserve_tokens": 2000,
    "model": "deepseek-chat",  # 仅 summary 策略需要
})
```

**策略说明：**

| 策略 | 说明 |
|------|------|
| `truncate` | 超出 token 限制时截断最早的消息（默认） |
| `sliding_window` | 保留最近的 N 条消息 |
| `summary` | 对早期消息生成摘要 |

---

## 输出清洗

### `SanitizerMiddleware`

```python
from hz_agent_base import create_agent

# 启用所有清洗功能
agent = create_agent(sanitizer=True)

# 自定义配置
agent = create_agent(sanitizer={
    "mask_pii": True,           # PII 脱敏
    "filter_sensitive": True,   # 敏感词过滤
    "detect_prompt_leak": True, # Prompt 泄露检测
})
```

**PII 脱敏规则：**

| 类型 | 原始值 | 脱敏值 |
|------|--------|--------|
| 手机号 | `13812345678` | `138****5678` |
| 邮箱 | `user@example.com` | `***@example.com` |
| 身份证 | `110101199001011234` | `110101****011234` |
| 银行卡 | `6222021234567890123` | `6222****0123` |

---

## 内容护栏

### `GuardrailsMiddleware`

```python
from hz_agent_base import create_agent
from hz_agent_base.guardrails import ContentModerator, FactChecker, OutputValidator

agent = create_agent(guardrails={
    "moderator": MyContentModerator(),    # 内容审核器
    "fact_checker": MyFactChecker(),      # 事实检查器
    "validator": MyOutputValidator(),     # 输出格式验证器
})
```

**协议定义：**

```python
from hz_agent_base.guardrails import ContentModerator, FactChecker, OutputValidator

# 内容审核
class MyModerator(ContentModerator):
    def moderate(self, content: str) -> tuple[bool, list[str]]:
        """返回 (通过, 问题列表)"""
        ...

# 事实检查
class MyChecker(FactChecker):
    def check(self, content: str, context: str = "") -> tuple[bool, list[str]]:
        """返回 (通过, 问题列表)"""
        ...

# 输出格式验证
class MyValidator(OutputValidator):
    def validate(self, content: str) -> tuple[bool, list[str]]:
        """返回 (通过, 问题列表)"""
        ...
```

---

## 人工审批

### `HumanApprovalMiddleware`

```python
from hz_agent_base import create_agent
from hz_agent_base.human_approval import ApprovalRule, ConsoleApprovalCallback

rules = [
    ApprovalRule(
        tool_pattern="bash",            # 匹配工具名（支持 glob）
        description="执行 bash 命令需要审批",
    ),
    ApprovalRule(
        tool_pattern="write_*",         # 匹配所有写操作
        arg_conditions={"file_path": "**/config/**"},  # 匹配参数值
        description="修改配置文件需要审批",
    ),
]

agent = create_agent(
    human_approval_rules=rules,
    human_approval_callback=ConsoleApprovalCallback(),
)
```

**`ApprovalRule` 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `tool_pattern` | `str` | 工具名 glob 模式 |
| `arg_conditions` | `dict[str, str]` | 参数匹配条件（值支持 glob） |
| `description` | `str` | 规则描述 |
| `priority` | `int` | 优先级（数值越大越先匹配） |

**`ApprovalCallback` 协议：**

```python
from hz_agent_base.human_approval import ApprovalCallback

class MyCallback(ApprovalCallback):
    def request_approval(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        rule: ApprovalRule,
    ) -> bool:
        """返回 True 执行，False 跳过"""
        ...
```

---

## 进化记忆

### `EvolutionMemoryMiddleware`

```python
from hz_agent_base import create_agent

# 默认配置
agent = create_agent(evolution_memory=True)

# 自定义配置
agent = create_agent(evolution_memory={
    "storage_path": ".evolution_memory",
    "enable_reflection": True,      # 启用自我反思评分
    "reflection_threshold": 0.7,    # 质量低于此值触发重试
    "max_retries": 1,               # 最大重试次数
    "inject_top_k": 3,              # 注入的历史经验条数
    "model": "deepseek-chat",       # 反思使用的模型
})
```

**任务分类规则：**

| 类型 | 匹配规则 |
|------|----------|
| `code_writing` | `写` + `代码`/`脚本`/`Python`/`程序` 等 |
| `data_analysis` | `分析` + `数据`/`统计`/`图表` 等 |
| `research` | `研究`/`调研` + `技术`/`方案`/`论文` 等 |
| `documentation` | `写` + `文档`/`报告`/`说明` 等 |
| `general` | 不匹配以上任何类型 |

**反思维度：**

| 维度 | 说明 |
|------|------|
| completeness | 任务是否完成 |
| accuracy | 结果是否正确 |
| efficiency | 是否有更优方案 |
| risk | 是否引入潜在问题 |
| maintainability | 代码/方案是否易于维护 |
