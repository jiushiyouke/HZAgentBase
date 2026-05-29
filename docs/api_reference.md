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
    memory_path=".memory/",
    memory_isolate_by_user=True,
    retriever=my_retriever,
    knowledge_top_k=5,
    filesystem=True,
    workers=[WorkerConfig(...)],
    middleware=[MyMiddleware()],
    backend=LocalBackend(),
    cancellation_checker=my_checker,
    stop_condition=my_condition,
    max_retries=2,
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
| `memory_path` | `str \| None` | `None` | 记忆存储目录路径 |
| `memory_isolate_by_user` | `bool` | `True` | 记忆按用户隔离，每个用户独立记忆目录 |
| `retriever` | `Retriever \| None` | `None` | 知识库检索器 |
| `knowledge_top_k` | `int` | `5` | 每次检索 Top-K 条 |
| `filesystem` | `bool \| dict` | `False` | 文件审计配置 |
| `workers` | `list[WorkerConfig] \| None` | `None` | Worker 配置列表 |
| `middleware` | `Sequence[AgentMiddleware] \| None` | `None` | 自定义中间件列表 |
| `backend` | `BackendProtocol \| None` | `None` | 文件系统/沙箱后端 |
| `cancellation_checker` | `CancellationChecker \| None` | `None` | 取消检查器，实现 `is_cancelled(thread_id)` 方法 |
| `stop_condition` | `StopCondition \| None` | `None` | 终止条件，实现 `should_stop(messages)` 方法 |
| `max_retries` | `int` | `2` | LLM 调用失败时的最大重试次数（指数退避） |

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
