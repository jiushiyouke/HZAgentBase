# HZAgentBase 技术路线方案

## 一、项目定位

HZAgentBase 是一个可复用的 Agent Harness 基础设施库，为上层业务项目提供开箱即用的 Agent 创建能力。

**核心目标**：

- 其他项目通过 `pip install hz-agent-base` 即可创建 Agent
- 提供权限控制、Hook 系统、记忆系统、多 Agent 编排等基础能力
- 提供对话历史管理、输出清洗、内容护栏、人工审批、进化记忆等高级功能
- 支持多模型（Claude、GPT、Gemini、私有模型）

## 二、技术选型

| 层级       | 技术方案                                                | 来源          |
| -------- | --------------------------------------------------- | ----------- |
| Agent 编排 | LangGraph (StateGraph)                              | Deep Agents |
| 中间件管道    | AgentMiddleware 模式                                  | Deep Agents |
| 后端抽象     | BackendProtocol / SandboxBackendProtocol            | Deep Agents |
| 权限系统     | PermissionChecker + 三模式                             | OpenHarness |
| Hook 系统  | HookExecutor + 4种Hook类型                             | OpenHarness |
| 记忆系统     | 文件级 Markdown + YAML frontmatter                     | OpenHarness |
| 多 Agent  | Coordinator + Worker 模式                             | OpenHarness |
| 对话历史管理   | Token 估算 + 三种策略（截断/滑动窗口/摘要）                         | 自研          |
| 输出清洗     | PII 脱敏 + 敏感词 + Prompt 泄露检测                          | 自研          |
| 内容护栏     | ContentModerator / FactChecker / OutputValidator 协议 | 自研          |
| 人工审批     | glob 模式匹配 + 审批回调协议                                  | 自研          |
| 进化记忆     | 任务分类 + 经验存储 + 反思评分 + 自动重试                           | 自研          |
| 文件审计     | 操作日志 + 变更追踪 + HMAC 签名                               | 自研          |
| CLI      | Click + Rich                                        | 新建          |

**选择 Deep Agents 为骨架的原因**：

1. LangGraph 提供图状编排，比线性循环更灵活
2. Middleware 管道扩展性好，新功能不需要改核心
3. Backend 抽象层设计成熟，支持本地/沙箱/远程
4. 工程化程度高（CI/CD、评测体系、威胁模型）

**从 OpenHarness 移植的原因**：

1. 权限系统更完整（敏感路径、命令过滤、三模式）
2. Hook 系统更丰富（4种类型 vs 基础支持）
3. 记忆系统更成熟（搜索、相关性、自动提取）
4. Coordinator 多 Agent 编排更完善

**自研功能模块**：

1. 对话历史管理 — 解决长对话 token 超限问题
2. 输出清洗 — 符合数据安全合规要求（PII 脱敏）
3. 内容护栏 — 企业级内容审核和质量保证
4. 人工审批 — 高风险操作的安全控制
5. 进化记忆 — Agent 持续学习和自我改进能力

## 三、架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    业务项目 (pip install hz-agent-base)      │
│                                                             │
│    from hz_agent_base import create_agent                   │
│    agent = create_agent(model="claude-sonnet-4-6", ...)     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      HZAgentBase                            │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              create_agent() 入口                      │   │
│  └──────────────────┬───────────────────────────────────┘   │
│                     │                                       │
│  ┌──────────────────▼───────────────────────────────────┐   │
│  │            Middleware 管道（按序执行）                 │   │
│  │                                                      │   │
│  │   1. PermissionMiddleware       ← 权限检查           │   │
│  │   2. HookMiddleware             ← 生命周期事件       │   │
│  │   3. ConversationHistory        ← 对话历史管理       │   │
│  │   4. MemoryMiddleware           ← 记忆注入/提取      │   │
│  │   5. KnowledgeMiddleware        ← 知识库 RAG 检索    │   │
│  │   6. HumanApprovalMiddleware    ← 人工审批           │   │
│  │   7. EvolutionMemoryMiddleware  ← 进化记忆           │   │
│  │   8. FileAuditMiddleware        ← 文件审计           │   │
│  │   9. SanitizerMiddleware        ← 输出清洗           │   │
│  │  10. GuardrailsMiddleware       ← 内容护栏           │   │
│  │  11. [用户自定义 Middleware]                         │   │
│  │  12. ResilientMiddleware        ← 容错：重试/取消    │   │
│  │  13. CoordinatorMiddleware      ← 多 Agent 编排      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Backend 层                              │   │
│  │  LocalBackend | SandboxBackend | RemoteBackend       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              LLM Provider 层                         │   │
│  │  Claude | GPT | Gemini | Ollama | 自定义             │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 四、核心模块设计

### 4.1 权限系统

```python
# 三种模式
class PermissionMode(Enum):
    DEFAULT = "default"      # 写操作需确认
    PLAN = "plan"            # 阻止写操作
    FULL_AUTO = "full_auto"  # 允许所有操作

# 权限检查流程
1. 敏感路径检查（.ssh, .aws/credentials 等）→ 拒绝
2. 工具级别 allow/deny 列表
3. 路径 glob 规则匹配
4. 命令 deny 模式匹配
5. 模式兜底（DEFAULT 需确认，FULL_AUTO 放行）
```

### 4.2 Hook 系统

```python
# 支持的事件
class HookEvent(Enum):
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    USER_PROMPT_SUBMIT = "user_prompt_submit"

# 四种 Hook 类型
- CommandHook: 执行 shell 命令
- HttpHook: POST 到 URL
- PromptHook: LLM 验证条件
- AgentHook: 深度验证
```

### 4.3 记忆系统

```python
# 记忆类型
class MemoryType(Enum):
    USER = "user"        # 用户偏好
    FEEDBACK = "feedback" # 行为反馈
    PROJECT = "project"  # 项目上下文
    REFERENCE = "reference" # 外部引用

# 存储格式：Markdown + YAML frontmatter
---
name: user_role
description: 用户角色信息
metadata:
  type: user
---
用户是数据科学家，关注日志和可观测性
```

### 4.4 多 Agent 编排

```python
# Coordinator 模式
coordinator = create_agent(
    model="claude-sonnet-4-6",
    workers=[
        WorkerConfig(name="researcher", tools=["web_search", "read_file"]),
        WorkerConfig(name="coder", tools=["write_file", "edit_file", "bash"]),
    ]
)

# 子 Agent 类型
- SubAgent: 同步声明式
- CompiledSubAgent: 预编译
- AsyncSubAgent: 异步/远程
```

### 4.5 知识库协议（RAG）

```python
# 设计原则：HZAgentBase 只定义检索协议，不绑定具体实现
# 参考 LlamaIndex BaseRetriever 的最小接口设计

# 协议定义（HZAgentBase 中）
@dataclass(frozen=True)
class RetrievalResult:
    content: str       # 文档片段内容
    source: str = ""   # 来源标识（文件名、URL 等）
    score: float = 0.0 # 相关性分数 0~1

class Retriever(Protocol):
    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]: ...

# 实现此协议的检索器示例：
# - ChromaDB 向量存储
# - FAISS 向量索引
# - sentence-transformers 本地嵌入
# - PDF / Word / Markdown / TXT 文档加载

# 集成方式：通过 create_agent(retriever=...) 注入
agent = create_agent(retriever=my_retriever)
```

**架构决策**：知识库实现独立于 HZAgentBase，不引入 chromadb、PyTorch 等重依赖。
通过 Python `typing.Protocol` 实现运行时类型检查，任何实现 `retrieve()` 方法的对象均可接入。

### 4.6 对话历史管理

防止对话历史过长导致 token 超限：

```python
# 三种策略
- truncate: 超出 token 限制时截断最早消息（默认）
- sliding_window: 保留最近 N 条消息
- summary: 对早期消息生成摘要（需要 LLM）

# Token 估算
使用 4 字符/token 的快速估算，不依赖外部 tokenizer
```

### 4.7 输出清洗 (Sanitizer)

自动对模型输出进行脱敏处理：

```python
# PII 脱敏
- 手机号：138****5678
- 邮箱：***@example.com
- 身份证：110101****011234
- 银行卡：6222****0123

# 敏感词过滤
可配置敏感词列表，匹配后替换为 ***

# Prompt 泄露检测
检测系统提示词是否被泄露到输出中
```

### 4.8 内容护栏 (Guardrails)

对模型输出进行多维度校验：

```python
# 三个协议
class ContentModerator(Protocol):
    def moderate(self, content: str) -> tuple[bool, list[str]]: ...

class FactChecker(Protocol):
    def check(self, content: str, context: str = "") -> tuple[bool, list[str]]: ...

class OutputValidator(Protocol):
    def validate(self, content: str) -> tuple[bool, list[str]]: ...
```

### 4.9 人工审批 (Human-in-the-Loop)

高风险工具调用暂停等待人工确认：

```python
# 规则匹配
- tool_pattern: glob 模式匹配工具名（如 "bash"、"write_*"）
- arg_conditions: 匹配工具参数值（支持 glob）
- 优先级排序，高优先级规则先匹配

# 审批回调
class ApprovalCallback(Protocol):
    def request_approval(self, tool_name, tool_args, rule) -> bool: ...
```

### 4.10 进化记忆 (Evolution Memory)

跨会话经验积累 + 自我反思评分：

```python
# 任务自动分类
基于双关键字匹配：code_writing、data_analysis、research、documentation、general

# 反思维度（每个 0-1 分）
1. 完整性 — 任务是否完成
2. 准确性 — 结果是否正确
3. 效率 — 是否有更优方案
4. 风险 — 是否引入潜在问题
5. 可维护性 — 代码/方案是否易于维护

# 经验注入
执行任务前，自动检索同类历史经验作为参考
```

## 五、对外 API 设计

### 5.1 基础用法

```python
from hz_agent_base import create_agent

# 最简用法
agent = create_agent()
result = run_agent(agent, "帮我分析这个数据集", thread_id="user-1")

# 完整用法
agent = create_agent(
    model="claude-sonnet-4-6",
    tools=[my_custom_tool],
    permissions=PermissionSettings(mode="DEFAULT"),
    hooks=HookRegistry([...]),
    memory_path=".memory/",
    middleware=[MyCustomMiddleware()],
    backend=LocalBackend(),
)

# 带知识库的用法（需实现 Retriever 协议）
# from my_retriever import MyRetriever

retriever = ChromaRetriever("./knowledge_db")
retriever.load_directory("./docs/")

agent = create_agent(
    retriever=retriever,          # 知识库检索器
    knowledge_top_k=5,            # 每次检索 Top-K 条
)
```

### 5.2 提示词和规则管理

```python
# 目录结构
# prompts/
# ├── shared/rules/          # 所有 agent 共享的规则
# │   ├── safety.md
# │   └── format.md
# ├── coordinator/base.md    # 协调者人设
# ├── researcher/            # 研究员独立目录
# │   ├── base.md
# │   └── rules/search.md
# └── coder/                 # 程序员独立目录
#     ├── base.md
#     └── rules/code_style.md

from hz_agent_base import create_agent, WorkerConfig

agent = create_agent(
    # 主 agent：从目录加载，叠加共享规则
    system_prompt="./prompts/coordinator/",
    rules=["./prompts/shared/rules/"],

    # 每个 worker 独立管理提示词
    workers=[
        WorkerConfig(name="researcher", prompt_dir="./prompts/researcher/"),
        WorkerConfig(name="coder", prompt_dir="./prompts/coder/"),
    ],
)

# 也支持直接传字符串（向后兼容）
agent = create_agent(system_prompt="你是一个助手。")
```

### 5.3 业务项目集成方式

**方式一：直接依赖（推荐）**

```python
# 业务项目的 pyproject.toml
[project]
dependencies = [
    "hz-agent-base>=0.1.0",
]

# 业务项目的 agent.py
from hz_agent_base import create_agent, PermissionSettings

def create_my_agent():
    return create_agent(
        model="claude-sonnet-4-6",
        permissions=PermissionSettings(
            mode="DEFAULT",
            allowed_tools=["read_file", "glob", "grep"],
            denied_tools=["bash"],
        ),
        memory_path=".my_project_memory/",
    )
```

**方式二：继承扩展**

```python
from hz_agent_base import HZAgentBase, create_agent

class MyProjectAgent(HZAgentBase):
    def __init__(self, config):
        super().__init__(
            model=config.model,
            permissions=self._build_permissions(config),
        )
    
    def _build_permissions(self, config):
        # 自定义权限逻辑
        return PermissionSettings(...)
```

**方式三：Middleware 扩展**

```python
from hz_agent_base.middleware import AgentMiddleware

class BusinessLogicMiddleware(AgentMiddleware):
    """注入业务特定的上下文和逻辑"""
    
    def wrap_model_call(self, request, handler):
        # 注入业务上下文
        request["system"] += "\n\n" + self.get_business_context()
        
        # 调用下一个 middleware
        response = handler(request)
        
        # 后处理
        self.log_interaction(request, response)
        
        return response

# 使用
agent = create_agent(
    middleware=[BusinessLogicMiddleware()]
)
```

## 六、分阶段执行计划

### 阶段一：项目骨架 ✅

- [x] 创建项目结构
- [x] 配置 Python 3.11 虚拟环境
- [x] pyproject.toml 配置
- [x] 基础包结构和 __init__.py
- [x] 安装核心依赖
- [x] .env 配置管理（python-dotenv）
- [x] DeepSeek API 集成和测试
- [x] 多用户线程隔离验证

### 阶段二：权限系统 ✅

- [x] 从 OpenHarness 移植 PermissionChecker
- [x] 包装为 Deep Agents Middleware
- [x] 修复 Middleware API（ModelRequest 数据类适配）
- [x] 单元测试（15 个用例）

### 阶段三：Hook 系统 ✅

- [x] 从 OpenHarness 移植 Hook 事件和类型
- [x] 移植 HookRegistry 和 HookExecutor
- [x] 包装为 Middleware
- [x] 单元测试（13 个用例）

### 阶段四：记忆系统 ✅

- [x] 从 OpenHarness 移植记忆管理器
- [x] 移植搜索和相关性算法
- [x] 包装为 Middleware
- [x] 单元测试（15 个用例）

### 阶段五：知识库协议 + 文件审计 ✅

- [x] 定义 Retriever 协议（参考 LlamaIndex BaseRetriever）
- [x] 实现 KnowledgeMiddleware
- [x] 集成到 create\_agent()（retriever 参数）
- [x] 实现 FileAuditMiddleware（审计 + 变更追踪）
- [x] 集成到 create\_agent()（filesystem 参数，可开关）
- [x] 审计日志支持 JSONL 持久化
- [x] 单元测试（知识库 12 个 + 文件审计 20 个）
- [ ] **独立知识库实现**（ChromaDB + embedding）

### 阶段六：多 Agent 编排 ✅

- [x] 从 OpenHarness 移植 Coordinator 模式
- [x] 实现 TeamRegistry（团队注册和成员管理）
- [x] 修复 CoordinatorMiddleware（ModelRequest API 适配）
- [x] 集成到 create\_agent()（workers 参数，自动传递 subagents）
- [x] 导出 WorkerConfig
- [x] 单元测试（18 个用例）

### 阶段七：提示词管理系统 ✅

- [x] PromptManager — 从目录加载 base.md + rules/\*.md
- [x] 共享规则支持（shared\_rules 参数，所有 agent 共享）
- [x] load\_prompt 便捷函数（支持字符串/文件路径/目录路径）
- [x] create\_agent() 的 system\_prompt 支持文件路径
- [x] create\_agent() 新增 rules 参数（共享规则目录）
- [x] WorkerConfig 新增 prompt\_dir 字段（每个 worker 独立提示词目录）
- [x] 单元测试（16 个用例）

### 阶段八：CLI 和示例 ✅

- [x] 更新 CLI：支持 --rules、--prompt、--filesystem 参数
- [x] CLI 使用 run\_agent() 替代直接 invoke
- [x] 新增 version 子命令
- [x] 更新 basic\_agent.py、custom\_permissions.py、multi\_user.py
- [x] 新增 with\_prompts.py（提示词管理示例）
- [x] 新增 with\_filesystem.py（文件审计示例）
- [x] 新增 server\_integration.py（FastAPI 服务器集成示例）
- [x] 更新 multi\_agent.py、with\_hooks.py

### 阶段九：文档和发布（进行中）

- [x] API 文档（docs/api\_reference.md）
- [x] README 更新（完整参数参考、中间件管道、知识库、文件审计、提示词管理）
- [x] PyPI 发布元数据（classifiers、project.urls）
- [ ] 使用指南
- [ ] PyPI 实际发布

### 阶段十：容错机制 ✅

- [x] 超时控制（MODEL\_REQUEST\_TIMEOUT，LLM API 调用超时）
- [x] 失败重试（ResilientMiddleware，指数退避，max\_retries 可配置）
- [x] 递归限制（recursion\_limit 参数，防止 Agent 死循环）
- [x] 用户取消（CancellationChecker 协议，支持 Redis/DB/内存等后端）
- [x] 终止条件（StopCondition 协议，支持轮次限制/规则引擎/外部 API）
- [x] ResilientMiddleware 集成到 create\_agent() 管道
- [x] 单元测试（容错相关测试用例）

### 阶段十一：安全加固 ✅

- [x] 路径穿越防护（Path.resolve() 规范化）
- [x] Shell 注入防护（shell=False + shlex.split）
- [x] 正则命令黑名单（13 种危险命令模式）
- [x] LLM Hook 默认阻止（模型未配置时 blocked）
- [x] 跨用户记忆隔离（isolate\_by\_user 参数）
- [x] 审计日志 HMAC-SHA256 签名 + verify\_log()
- [x] Workspace 限制生效
- [x] HTTP Hook URL 白名单（allowed\_hosts）
- [x] API Key 启动校验
- [x] .gitignore 补全
- [x] 安全单元测试（25 个用例）

### 阶段十二：高并发优化 ✅

- [x] 记忆 LRU+TTL 缓存（MemoryCache）
- [x] 跨平台文件锁（FileLock，Windows msvcrt / Unix fcntl）
- [x] 审计批量缓冲写入（BufferedAuditLog）
- [x] Hook 全局线程池并行执行
- [x] 并发压力测试（100 线程，12 个用例）

### 阶段十三：高级中间件功能 ✅

- [x] 对话历史管理（ConversationHistoryMiddleware，3 种策略）
- [x] 输出清洗（SanitizerMiddleware，PII/敏感词/泄露检测）
- [x] 内容护栏（GuardrailsMiddleware，审核/事实检查/格式验证）
- [x] 人工审批（HumanApprovalMiddleware，glob 模式匹配）
- [x] 进化记忆（EvolutionMemoryMiddleware，经验存储+自我反思+任务分类）
- [x] 单元测试（60+ 个用例）
- [x] 全功能示例（full\_featured.py）

## 七、依赖清单

```toml
[project]
name = "hz-agent-base"
version = "0.1.0"
requires-python = ">=3.11,<3.13"

dependencies = [
    "deepagents>=0.6.4,<0.7.0",
    "langchain-anthropic>=0.3.0",
    "langchain-openai>=0.3.0",
    "langgraph>=0.4.0",
    "pydantic>=2.0",
    "click>=8.0",
    "rich>=13.0",
    "openai>=1.0",
    "python-dotenv>=1.0",
]

# 知识库功能由独立的 Retriever 实现提供
# 可选实现：ChromaDB、FAISS、Elasticsearch 等
# 内部依赖：chromadb / faiss-cpu, sentence-transformers
```

## 八、风险和应对

| 风险                 | 影响             | 应对          |
| ------------------ | -------------- | ----------- |
| Deep Agents API 变更 | 中间件接口变化        | 锁定版本，升级前测试  |
| OpenHarness 代码质量   | 移植后有 bug       | 逐模块写单元测试    |
| LangGraph 学习曲线     | 开发效率           | 先跑通示例，再深入定制 |
| 性能开销               | Middleware 链过长 | 按需启用，性能基准测试 |

## 九、目录结构

```
HZAgentBase/
├── pyproject.toml
├── README.md
├── docs/
│   ├── technical_roadmap.md
│   └── api_reference.md
├── src/
│   └── hz_agent_base/
│       ├── __init__.py                # 公开 API
│       ├── agent.py                   # create_agent() 入口
│       ├── middleware/
│       │   ├── __init__.py
│       │   ├── permission.py          # 权限中间件
│       │   ├── hook.py                # Hook 中间件
│       │   ├── memory.py              # 记忆中间件
│       │   ├── knowledge.py           # 知识库中间件
│       │   ├── filesystem.py          # 文件审计中间件
│       │   ├── conversation_history.py # 对话历史管理中间件
│       │   ├── sanitizer.py           # 输出清洗中间件
│       │   ├── guardrails.py          # 内容护栏中间件
│       │   ├── human_approval.py      # 人工审批中间件
│       │   ├── evolution_memory.py    # 进化记忆中间件
│       │   └── resilient.py           # 容错中间件（重试/取消/终止）
│       ├── conversation_history/      # 对话历史工具
│       │   ├── __init__.py
│       │   └── tokenizer.py           # Token 估算
│       ├── sanitizer/                 # 清洗工具
│       │   ├── __init__.py
│       │   └── pii.py                 # PII 脱敏
│       ├── guardrails/                # 护栏协议
│       │   ├── __init__.py
│       │   └── protocols.py           # ContentModerator / FactChecker / OutputValidator
│       ├── human_approval/            # 人工审批
│       │   ├── __init__.py
│       │   └── rules.py               # 审批规则
│       ├── evolution_memory/          # 进化记忆
│       │   ├── __init__.py
│       │   ├── types.py               # 核心类型（TaskExperience 等）
│       │   ├── evaluator.py           # 反思评估器
│       │   └── store.py               # 经验存储
│       ├── audit/                     # 文件审计
│       │   ├── __init__.py
│       │   ├── operations.py          # 操作分类
│       │   └── auditlog.py            # 审计日志
│       ├── resilience/
│       │   ├── __init__.py
│       │   └── protocols.py           # CancellationChecker / StopCondition 协议
│       ├── knowledge/
│       │   ├── __init__.py
│       │   └── protocol.py            # Retriever 协议定义
│       ├── prompts/
│       │   ├── __init__.py
│       │   └── manager.py             # PromptManager 提示词管理
│       ├── permissions/
│       │   ├── __init__.py
│       │   ├── checker.py             # PermissionChecker
│       │   ├── modes.py               # 权限模式
│       │   └── settings.py            # 权限配置
│       ├── hooks/
│       │   ├── __init__.py
│       │   ├── events.py              # HookEvent
│       │   ├── schemas.py             # Hook 定义
│       │   ├── registry.py            # HookRegistry
│       │   └── executor.py            # HookExecutor
│       ├── memory/
│       │   ├── __init__.py
│       │   ├── manager.py             # 记忆管理
│       │   ├── relevance.py           # 记忆搜索与相关性算法
│       │   └── cache.py               # LRU+TTL 缓存 + 跨平台文件锁
│       ├── coordinator/
│       │   ├── __init__.py
│       │   ├── coordinator.py         # Coordinator 模式
│       │   ├── worker.py              # Worker 配置
│       │   └── team.py                # TeamRegistry
│       ├── tools/
│       │   └── __init__.py
│       └── backends/
│           └── __init__.py
├── tests/
│   ├── conftest.py
│   ├── test_agent.py
│   ├── test_config.py
│   ├── test_permissions.py
│   ├── test_hooks.py
│   ├── test_memory.py
│   ├── test_middleware.py
│   ├── test_knowledge.py
│   ├── test_filesystem.py
│   ├── test_coordinator.py
│   ├── test_prompts.py
│   ├── test_security.py               # 安全加固测试（25 个用例）
│   ├── test_concurrency.py            # 并发压力测试（12 个用例）
│   ├── test_memory_cache.py           # 缓存和文件锁测试（16 个用例）
│   ├── test_conversation_history.py   # 对话历史测试（13 个用例）
│   ├── test_sanitizer.py              # 输出清洗测试（15 个用例）
│   ├── test_guardrails.py             # 内容护栏测试（12 个用例）
│   ├── test_human_approval.py         # 人工审批测试（14 个用例）
│   └── test_evolution_memory.py       # 进化记忆测试（16 个用例）
└── examples/
    ├── basic_agent.py                 # 最简用法
    ├── custom_permissions.py          # 权限控制
    ├── multi_user.py                  # 多用户隔离
    ├── multi_agent.py                 # 多 Agent 编排
    ├── with_hooks.py                  # Hook 系统
    ├── with_memory.py                 # 记忆系统
    ├── with_prompts.py                # 提示词管理
    ├── with_filesystem.py             # 文件审计
    ├── full_featured.py               # 全功能示例（所有中间件）
    └── server_integration.py          # FastAPI 服务器集成
```

