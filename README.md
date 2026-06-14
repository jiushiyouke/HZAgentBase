# HZAgentBase

可复用的 Agent Harness 基础设施库。

基于 [Deep Agents](https://github.com/langchain-ai/deepagents) 和 [OpenHarness](https://github.com/HKUDS/OpenHarness) 构建，为上层业务项目提供开箱即用的 Agent 创建能力。

## 功能特性

- **权限系统** — 三种模式（DEFAULT / PLAN / FULL_AUTO），细粒度工具调用控制
- **Hook 系统** — 生命周期事件钩子（4 种类型：Command / Http / Prompt / Agent），全局线程池并行执行
- **记忆系统** — 基于文件的持久化跨会话记忆，LRU 缓存 + 文件锁，支持相关性搜索和自动提取
- **知识库 RAG** — 通过 Retriever 协议接入任意知识库实现，松耦合设计
- **文件审计** — 文件操作审计日志 + 变更追踪，HMAC-SHA256 签名保证完整性，批量缓冲写入
- **对话历史管理** — Token 估算 + 三种策略（截断 / 滑动窗口 / 摘要），防止上下文超限
- **输出清洗** — PII 脱敏（手机/邮箱/身份证/银行卡）、敏感词过滤、Prompt 泄露检测
- **内容护栏 (Guardrails)** — 内容审核、事实校验、输出格式验证，可自定义校验器
- **人工审批** — 高风险操作暂停等待人工确认，支持 glob 模式匹配工具名和参数
- **进化记忆** — 跨会话经验积累 + 自我反思评分，任务自动分类，失败时自动重试
- **提示词管理** — 目录式提示词加载（base.md + rules/*.md），支持共享规则
- **多 Agent 编排** — Coordinator / Worker 模式，每个 worker 独立提示词、工具集和技能
- **容错机制** — LLM 调用超时控制、指数退避重试、递归深度限制、用户取消检查、终止条件
- **安全加固** — 路径穿越防护、shell 注入防护、正则命令黑名单、跨用户记忆隔离、HTTP Hook 白名单
- **高并发优化** — 记忆 LRU+TTL 缓存、审计批量缓冲写入、Hook 全局线程池并行执行
- **多用户隔离** — 基于 LangGraph thread_id 的状态隔离，同一 agent 实例可并发服务多个用户
- **异步 & 流式** — `arun_agent()` 异步调用、`run_agent_stream()` / `arun_agent_stream()` 逐 token 流式输出
- **全中间件异步支持** — 所有中间件均实现 `awrap_model_call` / `awrap_tool_call`，异步调用链完整
- **模型参数透传** — `model_kwargs` 支持各提供商特有参数（temperature、reasoning_effort 等）
- **便捷参数** — 一行代码启用功能模块（`memory_path=True`、`sanitizer=True` 等）
- **多租户支持** — `api_key` / `base_url` 参数支持不同用户使用不同 API 配置
- **中间件优先级** — 自定义中间件可指定执行位置（BEFORE_ALL / AFTER_ALL 等）
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

**异步调用：**

```python
from hz_agent_base import arun_agent

result = await arun_agent(agent, "分析数据", thread_id="user-a")
```

**流式输出（逐 token）：**

```python
from hz_agent_base import run_agent_stream

for token in run_agent_stream(agent, "写个报告"):
    print(token, end="", flush=True)  # 像打字一样逐字输出
```

**异步流式（FastAPI + SSE）：**

```python
from hz_agent_base import arun_agent_stream
from fastapi.responses import StreamingResponse

@app.post("/chat")
async def chat(message: str):
    async def generate():
        async for token in arun_agent_stream(agent, message):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

## 配置

复制 `.env-example` 为 `.env` 并填入配置：

```bash
cp .env-example .env
```

配置采用懒加载模式——`import hz_agent_base` 时不会读取 `.env`，只有第一次使用配置变量时才加载。

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
| `MODEL_REQUEST_TIMEOUT` | LLM API 调用超时（秒） | `600` |
| `MODEL_MAX_RETRIES` | LLM 调用失败重试次数 | `2` |
| `RECURSION_LIMIT` | Agent 最大执行步数，防止死循环 | `25` |
| `PERMISSION_MODE` | 权限模式 | `default` |
| `MEMORY_PATH` | 记忆存储路径 | `.memory` |
| `AUDIT_LOG_PATH` | 审计日志路径 | `.audit/audit.jsonl` |
| `KNOWLEDGE_TOP_K` | 知识库检索条数 | `5` |

## 多租户支持

`create_agent()` 支持 `api_key` 和 `base_url` 参数，不同租户可用不同 API 配置：

```python
# 租户 A 用 DeepSeek
agent_a = create_agent(model="deepseek-v4-flash", api_key="sk-aaa...")

# 租户 B 用 OpenAI
agent_b = create_agent(model="gpt-4", api_key="sk-bbb...", base_url="https://api.openai.com/v1")

# 也可以直接传预配置的模型实例
from langchain_openai import ChatOpenAI
agent_c = create_agent(model=ChatOpenAI(model="gpt-4", api_key="sk-ccc..."))
```

参数优先级：`api_key`/`base_url` 参数 > `.env` 全局配置 > 提供商默认值。

## 模型参数配置

通过 `model_kwargs` 传递额外参数给底层模型类，支持各提供商的特有参数：

```python
from hz_agent_base import create_agent

# DeepSeek 思考模式
agent = create_agent(
    model="deepseek-v4-pro",
    model_kwargs={
        "temperature": 0.1,
        "reasoning_effort": "high",      # 思考深度：high / medium / low
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
        "presence_penalty": 0.1,
    }
)

# Anthropic 参数
agent = create_agent(
    model="claude-3-opus",
    model_kwargs={
        "temperature": 0.5,
        "top_k": 40,
        "max_tokens": 8192,
    }
)
```

各提供商支持的参数：

| 提供商 | 常用参数 |
|--------|----------|
| DeepSeek | temperature, reasoning_effort, reasoning, top_p, max_tokens, presence_penalty, frequency_penalty, seed |
| OpenAI | temperature, top_p, max_tokens, presence_penalty, frequency_penalty, seed, logprobs |
| Anthropic | temperature, top_k, top_p, max_tokens, stop_sequences |
| Gemini | temperature, top_p, top_k, max_output_tokens, stop_sequences |

## 中间件管道

`create_agent()` 使用优先级排序机制组装中间件管道。每个中间件可拦截和修改模型请求，数字越小越先执行：

```
```
优先级    中间件                    说明
─────────────────────────────────────────────────────────────────
  0       BEFORE_ALL               ← 自定义中间件插入点（最前面）
  5       PermissionMiddleware     ← 权限检查（默认开启）
  8       HumanApprovalMiddleware  ← 人工审批
 10       HookMiddleware           ← 生命周期事件
 20       MemoryMiddleware         ← 记忆注入/提取
 22       EvolutionMemoryMiddleware← 进化记忆 + 自我反思
 25       KnowledgeMiddleware      ← 知识库 RAG 检索
 28       ConversationHistory      ← 对话历史管理
 30       DEFAULT                  ← 用户自定义中间件的默认位置
 32       GuardrailsMiddleware     ← 内容护栏
 33       SanitizerMiddleware      ← 输出清洗
 35       FileAuditMiddleware      ← 文件审计 + 变更追踪
 40       ResilientMiddleware      ← 容错：重试、取消、终止条件（默认开启）
 50       CoordinatorMiddleware    ← 多 Agent 编排
100       AFTER_ALL                ← 自定义中间件插入点（最后面）
```

| 中间件 | 优先级 | 默认状态 | 启用方式 |
|--------|--------|---------|---------|
| Permission | 5 | 开启 | 无需额外参数，可通过 `permissions` 自定义 |
| Hook | 10 | 关闭 | `hooks=HookRegistry(...)` |
| ConversationHistory | 28 | 关闭 | `conversation_history=True` 或 `conversation_history={...}` |
| Memory | 20 | 关闭 | `memory_path=True`（默认路径）或 `memory_path=".memory/"` |
| Knowledge | 25 | 关闭 | `retriever=your_retriever` |
| HumanApproval | 8 | 关闭 | `human_approval_rules=True`（默认规则）或 `human_approval_rules=[...]` |
| EvolutionMemory | 22 | 关闭 | `evolution_memory=True` 或 `evolution_memory={...}` |
| Filesystem | 35 | 关闭 | `filesystem=True` 或 `filesystem={...}` |
| Sanitizer | 33 | 关闭 | `sanitizer=True` 或 `sanitizer={...}` |
| Guardrails | 32 | 关闭 | `guardrails=True` 或 `guardrails={...}` |
| Resilient | 40 | 开启 | `max_retries=2`，可选 `cancellation_checker`、`stop_condition` |
| Coordinator | 50 | 关闭 | `workers=[WorkerConfig(...)]` |

**一行代码启用所有功能：**

```python
agent = create_agent(
    model="deepseek-v4-flash",
    memory_path=True,              # 记忆系统
    conversation_history=True,     # 对话历史管理
    evolution_memory=True,         # 进化记忆
    human_approval_rules=True,     # 人工审批
    sanitizer=True,                # 输出清洗
    guardrails=True,               # 内容护栏
    filesystem=True,               # 文件审计
)
```

**自定义中间件可插入任意位置：**

```python
from hz_agent_base import create_agent
from hz_agent_base.utils.constants import BEFORE_ALL, AFTER_ALL

agent = create_agent(
    middleware=[
        (RequestLogger(), BEFORE_ALL),     # 优先级 0，最前面执行
        (BusinessContext()),                # 优先级 30，默认位置
        (OutputSanitizer(), AFTER_ALL),    # 优先级 100，最后面执行
    ],
)
```

可用的优先级常量：`BEFORE_ALL=0`、`PERMISSION=5`、`HUMAN_APPROVAL=8`、`HOOKS=10`、`MEMORY=20`、`AGENT_MEMORY=22`、`KNOWLEDGE=25`、`CONVERSATION_HISTORY=28`、`DEFAULT=30`、`GUARDRAILS=32`、`SANITIZER=33`、`AUDIT=35`、`RESILIENT=40`、`COORDINATOR=50`、`AFTER_ALL=100`。

直接传入的中间件默认优先级为 `DEFAULT=30`（在 Filesystem 之后、Resilient 之前）。通过 `(middleware, priority)` 元组可指定任意优先级。

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

支持的事件：`SESSION_START`、`SESSION_END`、`PRE_TOOL_USE`、`POST_TOOL_USE`、`USER_PROMPT_SUBMIT`

## 记忆系统

```python
from hz_agent_base import create_agent

# 使用默认路径 .memory
agent = create_agent(memory_path=True)

# 自定义路径
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

# 实现 Retriever 协议
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

## 对话历史管理

防止对话历史过长导致 token 超限，支持三种策略：

```python
from hz_agent_base import create_agent

# 截断模式（默认）：超出 token 限制时直接截断最早的消息
agent = create_agent(conversation_history={"max_tokens": 16000, "strategy": "truncate"})

# 滑动窗口：保留最近的 N 条消息
agent = create_agent(conversation_history={"max_tokens": 16000, "strategy": "sliding_window"})

# 摘要模式：超出时对早期消息生成摘要（需要 model 支持）
agent = create_agent(conversation_history={"max_tokens": 16000, "strategy": "summary", "model": "deepseek-chat"})
```

配置项：

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `max_tokens` | `int` | 最大 token 限制 | `16000` |
| `strategy` | `str` | 策略：`truncate` / `sliding_window` / `summary` | `"truncate"` |
| `reserve_tokens` | `int` | 为响应保留的 token 数 | `2000` |
| `model` | `str` | 摘要使用的模型（仅 summary 策略） | `None` |

Token 估算使用 4 字符/token 的快速估算，不依赖外部 tokenizer。

## 输出清洗 (Sanitizer)

自动对模型输出进行脱敏处理：

```python
from hz_agent_base import create_agent

# 启用所有清洗功能
agent = create_agent(sanitizer=True)

# 自定义配置
agent = create_agent(sanitizer={
    "mask_pii": True,           # PII 脱敏（手机/邮箱/身份证/银行卡）
    "filter_sensitive": True,   # 敏感词过滤
    "detect_prompt_leak": True, # 检测系统提示词泄露
})
```

PII 脱敏效果：
- `13812345678` → `138****5678`
- `user@example.com` → `***@example.com`
- `110101199001011234` → `110101****011234`
- `6222021234567890123` → `6222****0123`

## 内容护栏 (Guardrails)

对模型输出进行多维度校验：

```python
from hz_agent_base import create_agent
from hz_agent_base.guardrails import ContentModerator, FactChecker, OutputValidator

# 使用默认配置（block_on_failure=True）
agent = create_agent(guardrails=True)

# 自定义内容审核器
class MyContentModerator(ContentModerator):
    def moderate(self, content: str) -> tuple[bool, list[str]]:
        issues = []
        if "违法" in content:
            issues.append("包含违法内容")
        return (len(issues) == 0, issues)

# 自定义事实检查器
class MyFactChecker(FactChecker):
    def check(self, content: str, context: str = "") -> tuple[bool, list[str]]:
        # 调用外部事实检查 API...
        return (True, [])

agent = create_agent(guardrails={
    "moderator": MyContentModerator(),
    "fact_checker": MyFactChecker(),
    "validator": None,  # 可选的输出格式验证器
})
```

校验器协议：

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

## 人工审批 (Human-in-the-Loop)

高风险工具调用暂停等待人工确认：

```python
from hz_agent_base import create_agent
from hz_agent_base.human_approval import ApprovalRule, ConsoleApprovalCallback

# 使用默认规则（bash、delete_file、write_file 等危险操作）
agent = create_agent(human_approval_rules=True)

# 自定义审批规则
rules = [
    # 匹配所有 bash 命令
    ApprovalRule(
        tool_pattern="bash",
        description="执行 bash 命令需要审批",
    ),
    # 匹配特定路径的文件写入
    ApprovalRule(
        tool_pattern="write_file",
        arg_conditions={"file_path": "**/config/**"},
        description="修改配置文件需要审批",
    ),
    # 匹配危险命令
    ApprovalRule(
        tool_pattern="bash",
        arg_conditions={"command": "*rm *"},
        description="删除命令需要审批",
        priority=10,  # 高优先级
    ),
]

# 使用控制台回调（生产环境可替换为 Web UI、Slack 等）
agent = create_agent(
    human_approval_rules=rules,
    human_approval_callback=ConsoleApprovalCallback(),
)
```

审批回调协议：

```python
from hz_agent_base.human_approval import ApprovalCallback

class MyApprovalCallback(ApprovalCallback):
    def request_approval(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        rule: ApprovalRule,
    ) -> bool:
        """返回 True 执行，False 跳过"""
        # 发送到 Web UI、Slack、企业微信等...
        ...
```

## 进化记忆 (Evolution Memory)

跨会话经验积累 + 自我反思评分，帮助 Agent 从成功和失败中学习：

```python
from hz_agent_base import create_agent

# 使用默认配置
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

**任务自动分类**：基于双关键字匹配，自动识别任务类型：
- 代码相关（code_writing）：`写` + `代码`/`脚本`/`Python` 等
- 数据分析（data_analysis）：`分析` + `数据`/`统计` 等
- 研究类（research）：`研究`/`调研` + `技术`/`方案` 等
- 文档类（documentation）：`写` + `文档`/`报告` 等
- 其他（general）

**反思评分维度**（每个 0-1 分）：
1. 完整性 — 任务是否完成
2. 准确性 — 结果是否正确
3. 效率 — 是否有更优方案
4. 风险 — 是否引入潜在问题
5. 可维护性 — 代码/方案是否易于维护

**经验注入**：执行任务前，自动检索同类历史经验作为参考。

## 容错机制

HZAgentBase 提供多层容错保护，防止 LLM 调用异常导致 Agent 不可用：

```python
from hz_agent_base import create_agent

# 基础容错（默认生效，无需配置）
agent = create_agent()  # 自动：超时 600s + 重试 2 次 + 递归限制 25 步

# 自定义重试次数
agent = create_agent(max_retries=3)

# 带取消检查（Web 场景：用户主动取消请求）
class RedisCancellationChecker:
    def __init__(self, redis_client):
        self.redis = redis_client
    def is_cancelled(self, thread_id: str) -> bool:
        return self.redis.exists(f"cancel:{thread_id}")

agent = create_agent(
    cancellation_checker=RedisCancellationChecker(redis_client),
)

# 带终止条件（限制 Agent 循环轮次）
class MaxRoundsCondition:
    def __init__(self, max_rounds: int = 5):
        self.max_rounds = max_rounds
    def should_stop(self, messages: list) -> bool:
        ai_count = sum(1 for m in messages if getattr(m, "type", "") == "ai")
        return ai_count >= self.max_rounds

agent = create_agent(stop_condition=MaxRoundsCondition(max_rounds=5))
```

**容错层次：**

| 层次 | 机制 | 配置 | 默认值 |
|------|------|------|--------|
| 超时控制 | LLM API 调用超时 | `MODEL_REQUEST_TIMEOUT` | 600 秒 |
| 失败重试 | 指数退避重试 | `max_retries` / `MODEL_MAX_RETRIES` | 2 次 |
| 递归限制 | Agent 最大执行步数 | `recursion_limit` / `RECURSION_LIMIT` | 25 步 |
| 用户取消 | 检查外部取消信号 | `cancellation_checker` | 无（需实现） |
| 终止条件 | 检查是否应停止循环 | `stop_condition` | 无（需实现） |

`cancellation_checker` 和 `stop_condition` 通过协议（Protocol）接入，支持任意后端（Redis、数据库、API 等）：

```python
from hz_agent_base import CancellationChecker, StopCondition

# 实现 CancellationChecker 协议
class MyChecker:
    def is_cancelled(self, thread_id: str) -> bool:
        ...

# 实现 StopCondition 协议
class MyCondition:
    def should_stop(self, messages: list) -> bool:
        ...
```

## 安全加固

HZAgentBase 内置多层安全防护：

- **路径穿越防护** — 所有路径经 `Path.resolve()` 规范化，防止 `../` 绕过敏感路径检查
- **Shell 注入防护** — Hook 命令默认 `shell=False`，使用 `shlex.split()` 安全拆分
- **正则命令黑名单** — 13 种危险命令模式（`rm -rf /`、`curl | sh`、`eval` 等）
- **跨用户记忆隔离** — `memory_isolate_by_user=True`（默认），按用户隔离记忆目录
- **审计日志完整性** — HMAC-SHA256 签名，`verify_log()` 校验
- **HTTP Hook 白名单** — `allowed_hosts` 限制外发请求目标
- **LLM Hook 默认阻止** — 模型未配置时 PromptHook/AgentHook 默认阻止而非放行
- **Workspace 限制** — 文件审计可限制操作范围在指定工作目录内

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

## 技能系统（Skills）

Skills 是给 Agent 注入专业能力的机制。每个 skill 是一个目录，核心是 `SKILL.md` 文件，deepagents 的 `SkillsMiddleware` 会自动加载并注入到系统提示词。

**目录结构：**
```
skills/
├── coding/
│   └── SKILL.md          # 编码规范、代码风格等指令
├── research/
│   └── SKILL.md          # 研究方法、引用格式等指令
└── security/
    └── SKILL.md          # 安全审查规则
```

**SKILL.md 示例：**
```markdown
---
name: coding-standards
description: Python 编码规范和最佳实践
---

## 编码规范
- 使用 type hints
- 函数不超过 50 行
- 每个公开方法必须有 docstring
```

**使用方式：**
```python
from hz_agent_base import create_agent, WorkerConfig

# 主 Agent 加载技能
agent = create_agent(
    skills=["./skills/coding/", "./skills/security/"],
)

# 每个 Worker 独立技能
workers = [
    WorkerConfig(
        name="coder",
        prompt="你是编程助手",
        skills=["./skills/coding/"],
    ),
    WorkerConfig(
        name="researcher",
        prompt="你是研究助手",
        skills=["./skills/research/"],
    ),
]
agent = create_agent(workers=workers)
```

加载机制：deepagents 会扫描目录下的子目录，读取 `SKILL.md` 的名称和描述注入系统提示词（渐进式披露：先展示摘要，Agent 需要时再读取完整内容）。

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
# 使用帮助
hz-agent help

# 交互式对话
hz-agent chat
hz-agent chat --stream               # 流式输出
hz-agent chat --auto --filesystem    # 全自动 + 审计

# 单次执行
hz-agent run "帮我分析这段代码"
hz-agent run "分析数据" --stream      # 流式输出
hz-agent run "写报告" --output json   # JSON 格式输出

# 配置管理
hz-agent config show                 # 查看所有配置
hz-agent config check                # 检查环境和 API 连通性
hz-agent config path                 # 显示 .env 路径

# 记忆管理
hz-agent memory list                 # 列出所有记忆
hz-agent memory show <name>          # 查看记忆内容
hz-agent memory search "Python"      # 搜索相关记忆
hz-agent memory clear                # 清空记忆

# 审计日志
hz-agent audit show                  # 查看审计日志
hz-agent audit stats                 # 统计汇总
hz-agent audit export                # 导出为 CSV
hz-agent audit verify                # 校验 HMAC 签名

# 版本信息
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
| `memory_path` | `str \| bool \| None` | 记忆存储路径，True 使用默认路径 `.memory` |
| `memory_isolate_by_user` | `bool` | 记忆按用户隔离，默认 True |
| `retriever` | `Retriever \| None` | 知识库检索器（实现 Retriever 协议） |
| `knowledge_top_k` | `int` | 知识库每次检索条数，默认 5 |
| `filesystem` | `bool \| dict` | 文件审计，True 使用默认配置 |
| `conversation_history` | `bool \| dict` | 对话历史管理，True 使用默认配置 |
| `evolution_memory` | `bool \| dict` | 进化记忆，True 使用默认配置 |
| `human_approval_rules` | `bool \| list[ApprovalRule] \| None` | 人工审批，True 使用默认规则 |
| `sanitizer` | `bool \| dict` | 输出清洗，True 启用 PII/敏感词/泄露检测 |
| `guardrails` | `bool \| dict` | 内容护栏，True 使用默认配置 |
| `workers` | `list[WorkerConfig] \| None` | Worker 配置列表，启用多 Agent 编排 |
| `middleware` | `Sequence[AgentMiddleware \| tuple] \| None` | 自定义中间件列表，支持 `(middleware, priority)` 元组 |
| `backend` | `BackendProtocol \| None` | 文件系统/沙箱后端 |
| `skills` | `list[str] \| None` | 技能目录列表，由 SkillsMiddleware 加载 |
| `cancellation_checker` | `CancellationChecker \| None` | 取消检查器（实现 CancellationChecker 协议） |
| `stop_condition` | `StopCondition \| None` | 终止条件（实现 StopCondition 协议） |
| `max_retries` | `int` | LLM 调用失败重试次数，默认 2 |
| `api_key` | `str \| None` | API Key 覆盖，多租户使用。None 时读 .env |
| `base_url` | `str \| None` | Base URL 覆盖，多租户使用。None 时读 .env |
| `model_kwargs` | `dict \| None` | 额外模型参数（temperature, reasoning_effort 等） |

## 项目结构

```
HZAgentBase/
├── src/hz_agent_base/
│   ├── agent.py                # create_agent() / run_agent() 入口
│   ├── cli.py                  # CLI 工具
│   ├── config.py               # 配置管理
│   ├── middleware/              # 中间件实现
│   │   ├── permission.py       # 权限中间件
│   │   ├── hook.py             # Hook 中间件
│   │   ├── memory.py           # 记忆中间件
│   │   ├── knowledge.py        # 知识库 RAG 中间件
│   │   ├── filesystem.py       # 文件审计中间件
│   │   ├── conversation_history.py  # 对话历史管理中间件
│   │   ├── sanitizer.py        # 输出清洗中间件
│   │   ├── guardrails.py       # 内容护栏中间件
│   │   ├── human_approval.py   # 人工审批中间件
│   │   ├── evolution_memory.py # 进化记忆中间件
│   │   └── resilient.py        # 容错中间件（重试 / 取消 / 终止）
│   ├── conversation_history/   # 对话历史工具（Token 估算、格式化）
│   ├── sanitizer/              # 清洗工具（PII 脱敏、敏感词）
│   ├── guardrails/             # 护栏协议（ContentModerator / FactChecker / OutputValidator）
│   ├── human_approval/         # 人工审批（规则匹配、回调协议）
│   ├── evolution_memory/       # 进化记忆（经验存储、反思评估、任务分类）
│   ├── audit/                  # 文件审计（操作日志、变更追踪）
│   ├── resilience/             # 容错协议（CancellationChecker / StopCondition）
│   ├── permissions/            # 权限系统（Checker / Modes / Settings）
│   ├── hooks/                  # Hook 系统（Events / Registry / Executor）
│   ├── memory/                 # 记忆系统（Manager / Relevance / Cache）
│   ├── knowledge/              # 知识库协议（Retriever Protocol）
│   ├── coordinator/            # 多 Agent 编排（Coordinator / Worker / Team）
│   ├── prompts/                # 提示词管理（PromptManager）
│   ├── tools/                  # 工具扩展
│   ├── backends/               # 后端抽象
│   └── utils/                  # 工具类（常量定义等）
├── tests/                      # 单元测试（280+ 个用例）
├── examples/                   # 使用示例
│   ├── basic_agent.py          # 最简用法
│   ├── custom_permissions.py   # 权限控制
│   ├── multi_user.py           # 多用户隔离
│   ├── multi_agent.py          # 多 Agent 编排
│   ├── with_hooks.py           # Hook 系统
│   ├── with_memory.py          # 记忆系统
│   ├── with_knowledge.py       # 知识库 RAG
│   ├── with_prompts.py         # 提示词管理
│   ├── with_filesystem.py      # 文件审计
│   ├── with_streaming.py       # 流式输出
│   ├── async_agent.py          # 异步调用
│   ├── multi_tenant.py         # 多租户支持
│   ├── middleware_priority.py  # 中间件优先级
│   ├── custom_middleware.py    # 自定义中间件
│   ├── full_featured.py        # 全功能示例（所有中间件）
│   └── server_integration.py   # FastAPI 服务器集成（含 SSE 流式）
└── docs/
    ├── technical_roadmap.md    # 技术路线图
    ├── api_reference.md        # API 参考文档
    └── security_plan.md        # 安全防护方案
```

## 致谢

本项目基于以下开源项目构建，特此致谢：

- **[Deep Agents](https://github.com/langchain-ai/deepagents)** — LangChain 官方 Agent Harness，提供 LangGraph 编排引擎、Middleware 管道架构、Backend 抽象层等核心能力
- **[OpenHarness](https://github.com/HKUDS/OpenHarness)** — Claude Code 的 Python 开源复刻，提供权限系统、Hook 系统、记忆系统、多 Agent 编排等参考实现

感谢两个项目的开发者和社区为开源 Agent 生态做出的贡献。

## 许可证

MIT License
