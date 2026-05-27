# HZAgentBase 技术路线方案

## 一、项目定位

HZAgentBase 是一个可复用的 Agent Harness 基础设施库，为上层业务项目提供开箱即用的 Agent 创建能力。

**核心目标**：
- 其他项目通过 `pip install hz-agent-base` 即可创建 Agent
- 提供权限控制、Hook 系统、记忆系统、多 Agent 编排等基础能力
- 支持多模型（Claude、GPT、Gemini、私有模型）

## 二、技术选型

| 层级 | 技术方案 | 来源 |
|------|----------|------|
| Agent 编排 | LangGraph (StateGraph) | Deep Agents |
| 中间件管道 | AgentMiddleware 模式 | Deep Agents |
| 后端抽象 | BackendProtocol / SandboxBackendProtocol | Deep Agents |
| 权限系统 | PermissionChecker + 三模式 | OpenHarness |
| Hook 系统 | HookExecutor + 4种Hook类型 | OpenHarness |
| 记忆系统 | 文件级 Markdown + YAML frontmatter | OpenHarness |
| 多 Agent | Coordinator + Worker 模式 | OpenHarness |
| CLI | Click + Rich | 新建 |

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
│  │  1. PermissionMiddleware  ← 权限检查                 │   │
│  │  2. HookMiddleware        ← 生命周期事件             │   │
│  │  3. MemoryMiddleware      ← 记忆注入/提取            │   │
│  │  4. FilesystemMiddleware  ← 文件操作                 │   │
│  │  5. SubAgentMiddleware    ← 子 Agent                 │   │
│  │  6. CoordinatorMiddleware ← 多 Agent 编排            │   │
│  │  7. SkillsMiddleware      ← 技能加载                 │   │
│  │  8. [用户自定义 Middleware]                           │   │
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
    STOP = "stop"

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

## 五、对外 API 设计

### 5.1 基础用法

```python
from hz_agent_base import create_agent

# 最简用法
agent = create_agent()
response = agent.run("帮我分析这个数据集")

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
```

### 5.2 业务项目集成方式

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

### 阶段一：项目骨架（当前）
- [x] 创建项目结构
- [x] 配置 Python 3.11 虚拟环境
- [ ] pyproject.toml 配置
- [ ] 基础包结构和 __init__.py
- [ ] 安装核心依赖

### 阶段二：权限系统（1-2天）
- [ ] 从 OpenHarness 移植 PermissionChecker
- [ ] 包装为 Deep Agents Middleware
- [ ] 单元测试
- [ ] 集成测试

### 阶段三：Hook 系统（1天）
- [ ] 从 OpenHarness 移植 Hook 事件和类型
- [ ] 移植 HookRegistry 和 HookExecutor
- [ ] 包装为 Middleware
- [ ] 单元测试

### 阶段四：记忆系统（1天）
- [ ] 从 OpenHarness 移植记忆管理器
- [ ] 移植搜索和相关性算法
- [ ] 包装为 Middleware
- [ ] 单元测试

### 阶段五：多 Agent 编排（2天）
- [ ] 从 OpenHarness 移植 Coordinator 模式
- [ ] 实现 TeamRegistry
- [ ] 包装为 Middleware
- [ ] 集成测试

### 阶段六：CLI 和示例（1天）
- [ ] Click + Rich CLI
- [ ] 基础交互式对话
- [ ] 示例项目

### 阶段七：文档和发布（1天）
- [ ] API 文档
- [ ] 使用指南
- [ ] PyPI 发布配置

**总计预估：7-10天**

## 七、依赖清单

```toml
[project]
name = "hz-agent-base"
version = "0.1.0"
requires-python = ">=3.11,<3.12"

dependencies = [
    "deepagents>=0.6.4,<0.7.0",
    "langchain-anthropic>=0.3.0",
    "langgraph>=0.4.0",
    "pydantic>=2.0",
    "click>=8.0",
    "rich>=13.0",
]
```

## 八、风险和应对

| 风险 | 影响 | 应对 |
|------|------|------|
| Deep Agents API 变更 | 中间件接口变化 | 锁定版本，升级前测试 |
| OpenHarness 代码质量 | 移植后有 bug | 逐模块写单元测试 |
| LangGraph 学习曲线 | 开发效率 | 先跑通示例，再深入定制 |
| 性能开销 | Middleware 链过长 | 按需启用，性能基准测试 |

## 九、目录结构

```
HZAgentBase/
├── pyproject.toml
├── README.md
├── docs/
│   └── technical_roadmap.md
├── src/
│   └── hz_agent_base/
│       ├── __init__.py           # 公开 API
│       ├── agent.py              # create_agent() 入口
│       ├── middleware/
│       │   ├── __init__.py
│       │   ├── base.py           # AgentMiddleware 基类
│       │   ├── permission.py     # 权限中间件
│       │   ├── hook.py           # Hook 中间件
│       │   └── memory.py         # 记忆中间件
│       ├── permissions/
│       │   ├── __init__.py
│       │   ├── checker.py        # PermissionChecker
│       │   ├── modes.py          # 权限模式
│       │   └── settings.py       # 权限配置
│       ├── hooks/
│       │   ├── __init__.py
│       │   ├── events.py         # HookEvent
│       │   ├── schemas.py        # Hook 定义
│       │   ├── registry.py       # HookRegistry
│       │   └── executor.py       # HookExecutor
│       ├── memory/
│       │   ├── __init__.py
│       │   ├── manager.py        # 记忆管理
│       │   ├── search.py         # 记忆搜索
│       │   └── relevance.py      # 相关性算法
│       ├── coordinator/
│       │   ├── __init__.py
│       │   ├── coordinator.py    # Coordinator 模式
│       │   ├── worker.py         # Worker 配置
│       │   └── team.py           # TeamRegistry
│       ├── tools/
│       │   └── __init__.py
│       └── backends/
│           └── __init__.py
├── tests/
│   ├── test_permissions.py
│   ├── test_hooks.py
│   ├── test_memory.py
│   └── test_coordinator.py
└── examples/
    ├── basic_agent.py
    ├── custom_middleware.py
    └── multi_agent.py
```
