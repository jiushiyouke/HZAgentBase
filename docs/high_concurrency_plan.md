# 高并发改造技术路线

## 一、背景与目标

当前 HZAgentBase 定位为"单用户/少量用户的 Agent 开发框架"，所有 I/O 操作均为同步直读直写，无缓存、无锁、无异步。

**改造目标**：支撑 1000 个 Agent 并发运行，各模块响应时间不随用户数线性增长。

**分支**：`feat/high-concurrency`，完成后 PR 合入 `main`。

---

## 二、现状问题清单

| 模块 | 问题 | 严重程度 | 1000 并发影响 |
|------|------|---------|-------------|
| `memory/relevance.py` | 每次请求全量扫描磁盘读取所有记忆文件 | 致命 | 10000+ 文件读取/请求 |
| `memory/manager.py` | 无文件锁，并发写入竞态条件 | 高 | 数据丢失/重复 |
| `middleware/filesystem.py` | 每次事件 open/close 文件 | 高 | syscall 爆炸 |
| `hooks/executor.py` | Hook 串行执行 + 每实例独立线程池 | 中 | 延迟叠加 + 线程数爆炸 |

---

## 三、改造方案

### 3.1 记忆系统改造（P0）

**涉及文件**：
- `src/hz_agent_base/memory/relevance.py`
- `src/hz_agent_base/memory/manager.py`
- `src/hz_agent_base/middleware/memory.py`

**现状**：
```
用户请求 → select_relevant_memories() → glob 所有 .md → 逐个 read_text() → 分词 → 评分
```
每次请求都从磁盘读取全部记忆文件，无缓存。

**改造方案**：

#### A. 内存 LRU 缓存

```python
class MemoryCache:
    """记忆文件的内存缓存，避免每次请求都读磁盘。"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 60):
        self._cache: dict[str, tuple[MemoryEntry, float]] = {}
        self._max_size = max_size
        self._ttl = ttl_seconds

    def get(self, path: Path) -> MemoryEntry | None:
        """从缓存获取记忆条目，过期返回 None。"""
        ...

    def put(self, path: Path, entry: MemoryEntry) -> None:
        """写入缓存，LRU 淘汰。"""
        ...

    def invalidate(self, path: Path) -> None:
        """使指定条目失效（写入时调用）。"""
        ...

    def invalidate_all(self) -> None:
        """清空缓存。"""
        ...
```

集成到 `select_relevant_memories()`：
- 加载记忆前先查缓存
- 缓存命中直接返回，未命中才读磁盘
- `MemoryManager.add_memory()` 写入后调用 `cache.invalidate()`

#### B. 文件锁

```python
class FileLock:
    """跨进程文件锁，防止并发写入竞态。"""

    def __init__(self, lock_path: Path):
        self._lock_path = lock_path

    def __enter__(self):
        # Windows: msvcrt.locking
        # Linux: fcntl.flock
        ...

    def __exit__(self, *args):
        ...
```

集成到 `MemoryManager`：
- `add_memory()` 写文件前加锁
- `_update_index()` 更新索引前加锁
- 使用 `with` 语句确保异常时也能释放锁

**预期效果**：

| 指标 | 改造前 | 改造后 |
|------|--------|--------|
| 每请求磁盘读取 | O(N) 全部文件 | O(1) 缓存命中 |
| 并发写入安全 | 无保护 | 文件锁保护 |
| 首次加载延迟 | 取决于文件数 | 同（冷启动） |

---

### 3.2 审计系统改造（P0）

**涉及文件**：
- `src/hz_agent_base/middleware/filesystem.py`

**现状**：
```python
def _persist(self, op: FileOperation):
    # 每次写一行都 open → write → close
    with open(self.log_path, "a") as f:
        f.write(json.dumps(record) + "\n")
```

**改造方案**：

```python
class BufferedAuditLog(AuditLog):
    """带缓冲的审计日志，批量写入。"""

    def __init__(self, *, log_path: str = "", buffer_size: int = 100, flush_interval: float = 5.0):
        super().__init__(log_path=log_path)
        self._buffer: list[str] = []
        self._buffer_size = buffer_size
        self._flush_interval = flush_interval
        self._last_flush = time.time()
        self._lock = threading.Lock()

    def add(self, op: FileOperation) -> None:
        """添加到内存缓冲区，满或超时才写磁盘。"""
        super().add(op)  # 内存记录
        if self.log_path:
            line = json.dumps(self._to_record(op), ensure_ascii=False) + "\n"
            with self._lock:
                self._buffer.append(line)
                if len(self._buffer) >= self._buffer_size:
                    self._flush()

    def _flush(self) -> None:
        """批量写入磁盘。"""
        if not self._buffer:
            return
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.writelines(self._buffer)
        self._buffer.clear()
        self._last_flush = time.time()

    def _should_flush(self) -> bool:
        return time.time() - self._last_flush >= self._flush_interval
```

同时修复内存无限增长：
- `self.operations` 改为 `collections.deque(maxlen=10000)` 环形缓冲区

**预期效果**：

| 指标 | 改造前 | 改造后 |
|------|--------|--------|
| 文件 open/close 次数 | 每事件 1 次 | 每 100 事件 1 次 |
| 写入延迟 | 每次阻塞 | 异步批量 |
| 内存占用 | 无限增长 | 上限 10000 条 |

---

### 3.3 Hook 并行执行（P1）

**涉及文件**：
- `src/hz_agent_base/hooks/executor.py`
- `src/hz_agent_base/agent.py`（传递共享线程池）

**现状**：
```python
# 串行执行
for hook in hooks:
    result = self._execute_single(hook, payload)
    results.append(result)

# 每个 HookExecutor 实例创建独立的 ThreadPoolExecutor
# 1000 Agent × 5 workers = 5000 线程
```

**问题**：
- Hook 串行执行，延迟叠加
- 每个 HookExecutor 实例创建独立线程池，1000 并发时线程数爆炸

**改造方案：全局共享线程池**

```python
# 模块级全局线程池（所有 HookExecutor 共享）
_global_hook_pool: ThreadPoolExecutor | None = None

def get_hook_pool(max_workers: int = 20) -> ThreadPoolExecutor:
    """获取全局共享的 Hook 线程池（单例）。"""
    global _global_hook_pool
    if _global_hook_pool is None:
        _global_hook_pool = ThreadPoolExecutor(max_workers=max_workers)
    return _global_hook_pool


class HookExecutor:
    def __init__(self, registry, model=None):
        self.registry = registry
        self.model = model
        # 不再创建自己的线程池，使用全局共享池
        self._pool = get_hook_pool()

    def execute(self, event, payload, tool_name=None) -> AggregatedHookResult:
        hooks = self.registry.get_hooks(event)
        matched = [h for h in hooks if not h.matcher or not tool_name
                   or fnmatch.fnmatch(tool_name, h.matcher)]

        if not matched:
            return AggregatedHookResult(results=[])

        # 并行提交所有 hook
        futures = {
            self._pool.submit(self._execute_single, hook, payload): hook
            for hook in matched
        }

        results = []
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            # 任一 hook 阻止则取消剩余
            if result.blocked and futures[future].block_on_failure:
                for f in futures:
                    f.cancel()
                break

        return AggregatedHookResult(results=results)
```

**设计要点**：
- 全局线程池默认 `max_workers=20`，1000 个 Agent 共享，线程数可控
- 保留 `block_on_failure` 短路语义（任一完成的 hook 阻止即取消其余）
- `create_agent()` 可通过参数覆盖全局池的大小

**预期效果**：

| 指标 | 改造前 | 改造后 |
|------|--------|--------|
| 3 个 Hook 延迟 | T1 + T2 + T3 | max(T1, T2, T3) |
| 1000 Agent 线程数 | 5000（每实例 5） | 20（全局共享） |
| 阻塞语义 | 保持 | 保持（第一个阻止即停） |

---

### 3.4 补充 Skills 支持（P1）

**涉及文件**：
- `src/hz_agent_base/agent.py`（`create_agent()` 新增 `skills` 参数）
- `src/hz_agent_base/coordinator/worker.py`（`WorkerConfig` 新增 `skills` 字段）
- `src/hz_agent_base/coordinator/coordinator.py`（构建 SubAgent 时传递 skills）

**现状**：
deepagents 原生支持 `skills` 参数（技能文件目录列表），通过 `SkillsMiddleware` 从 backend 加载技能文件（`.md` 格式的提示词）。但 HZAgentBase 的 `create_agent()` 和 `WorkerConfig` 都没有暴露此能力。

**改造方案**：

```python
# agent.py — create_agent() 新增 skills 参数
def create_agent(
    ...,
    skills: list[str] | None = None,  # 新增
    ...,
) -> CompiledStateGraph:
    ...
    agent_kwargs: dict[str, Any] = {
        "model": resolved_model,
        "tools": tools,
        "system_prompt": resolved_prompt,
        "middleware": harness_middleware,
        "backend": backend,
        "skills": skills,  # 透传给 create_deep_agent
    }
    ...
```

```python
# worker.py — WorkerConfig 新增 skills 字段
@dataclass
class WorkerConfig:
    name: str
    prompt: str = ""
    prompt_dir: str = ""
    tools: list[str] = field(default_factory=list)
    model: str | None = None
    team: str = "default"
    color: str = "blue"
    skills: list[str] = field(default_factory=list)  # 新增：技能目录列表
```

```python
# coordinator.py — 构建 SubAgent 时传递 skills
self.subagents: list[SubAgent] = []
for w in workers:
    sub: SubAgent = SubAgent(
        name=w.name,
        description=w.prompt[:80] if w.prompt else w.name,
        system_prompt=self._resolve_prompt(w),
        tools=w.tools if w.tools else None,
    )
    if w.model is not None:
        sub["model"] = w.model
    if w.skills:  # 新增
        sub["skills"] = w.skills
    self.subagents.append(sub)
```

**预期效果**：
- `create_agent(skills=["/skills/user/"])` — 主 Agent 加载技能
- `WorkerConfig(skills=["/skills/coder/"])` — 每个 Worker 独立技能
- 技能文件为 `.md` 格式，由 deepagents 的 `SkillsMiddleware` 自动加载

---

## 四、实施顺序

```
Phase 1: 记忆系统改造（记忆缓存 + 文件锁）
  ├── 1.1 实现 MemoryCache（LRU + TTL）
  ├── 1.2 实现 FileLock（跨进程锁）
  ├── 1.3 集成到 MemoryManager 和 relevance.py
  ├── 1.4 单元测试
  └── 1.5 并发压力测试

Phase 2: 审计系统改造（缓冲写入）
  ├── 2.1 实现 BufferedAuditLog
  ├── 2.2 内存上限（deque maxlen）
  ├── 2.3 集成到 FileAuditMiddleware
  ├── 2.4 单元测试
  └── 2.5 并发压力测试

Phase 3: Hook 并行执行
  ├── 3.1 实现全局共享线程池（模块级单例）
  ├── 3.2 改造 HookExecutor 使用共享池
  ├── 3.3 保留 block_on_failure 短路语义
  ├── 3.4 单元测试
  └── 3.5 并发压力测试

Phase 4: 补充 Skills 支持
  ├── 4.1 create_agent() 新增 skills 参数
  ├── 4.2 WorkerConfig 新增 skills 字段
  ├── 4.3 CoordinatorMiddleware 构建 SubAgent 时传递 skills
  ├── 4.4 更新示例（with_skills.py）
  └── 4.5 单元测试

Phase 5: 集成测试与合入
  ├── 5.1 全量回归测试（142 个已有用例全部通过）
  ├── 5.2 1000 并发模拟测试
  ├── 5.3 更新文档（README、API 参考、技术路线图）
  └── 5.4 PR 合入 main
```

---

## 五、验收标准

| 指标 | 目标 |
|------|------|
| 1000 并发请求的 P99 延迟 | < 5 秒（不含 LLM 调用时间） |
| 记忆系统每请求磁盘读取 | 缓存命中时 0 次 |
| 审计日志写入 syscall 数 | 每 100 事件 ≤ 1 次 |
| Hook 3 个并行延迟 | 取最大而非求和 |
| 全局线程池线程数 | 固定 20，不随 Agent 数增长 |
| Skills 参数透传 | 主 Agent 和 Worker 均可配置 skills |
| 已有 142 个测试 | 全部通过 |
| 内存占用（1000 用户 × 10 记忆） | < 100MB |

---

## 六、不改造的模块

| 模块 | 原因 |
|------|------|
| `agent.py` | LangGraph 原生支持 thread_id 隔离，无瓶颈 |
| `coordinator/` | 构建时只读，运行时无 I/O |
| `permissions/` | 纯内存计算，无瓶颈 |
| `prompts/` | 构建时一次性读取，运行时无 I/O |
| `config.py` | 模块级一次性加载，无瓶颈 |
| `knowledge.py` | Retriever 是外部实现，自带索引和缓存；用户查询几乎不重复，加缓存收益低 |

---

## 七、知识库不改造的原因

知识库 RAG（`KnowledgeMiddleware`）不在本次改造范围内，理由：

1. **Retriever 是外部实现**：HZAgentBase 只定义协议，实际检索由 ChromaDB 等外部组件完成，这些组件自带索引和缓存
2. **查询几乎不重复**：用户每次提问内容不同，LRU 缓存命中率极低
3. **本地检索已够快**：ChromaDB 本地向量检索是毫秒级，加缓存收益不明显
4. **增加复杂度不值得**：缓存引入 TTL、失效策略、内存管理等额外复杂度，投入产出比低

如果未来 Retriever 是远程 API（网络延迟高），可以在 `Retriever` 实现侧加缓存，而非在 HZAgentBase 层加。
