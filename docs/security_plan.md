# 安全防护改造方案

## 一、风险总览

| 级别 | 数量 | 关键问题 |
|------|------|---------|
| CRITICAL | 1 | shell=True 命令注入 |
| HIGH | 4 | 路径穿越、跨用户记忆泄露、命令黑名单弱、LLM 安全决策 |
| MEDIUM | 4 | 知识库无访问控制、审计日志无完整性、workspace 未生效、HTTP Hook 泄露 |
| LOW | 4 | .gitignore 缺失、API Key 无校验、MD5 弱哈希、无 HTTPS 强制 |

**分支**：`feat/security-hardening`，完成后 PR 合入 `main`。

---

## 二、改造方案

### 2.1 CRITICAL — shell=True 命令注入

**涉及文件**：`src/hz_agent_base/hooks/executor.py`

**现状**：
```python
subprocess.run(hook.command, shell=True, ...)
```

**问题**：`shell=True` 将命令传给 `/bin/sh -c`（或 `cmd.exe`），如果 hook 命令包含用户可控数据，可注入任意命令。

**方案**：
1. 默认改为 `shell=False`，将命令字符串拆分为参数列表
2. 保留 `shell=True` 选项但需显式声明（`CommandHookDefinition(shell=True)`）
3. 使用 `shlex.split()` 安全拆分命令

```python
# 改造后
if hook.shell:
    # 显式声明 shell=True，用户自行承担风险
    result = subprocess.run(hook.command, shell=True, ...)
else:
    # 默认安全模式：拆分为参数列表
    args = shlex.split(hook.command)
    result = subprocess.run(args, shell=False, ...)
```

4. `CommandHookDefinition` 新增 `shell: bool = False` 字段

---

### 2.2 HIGH — 路径穿越

**涉及文件**：`src/hz_agent_base/permissions/checker.py`

**现状**：`_is_sensitive_path()` 和 `_check_path_rules()` 用 `fnmatch` 匹配原始路径字符串，`../` 可绕过。

**方案**：所有路径比较前先做 `Path.resolve()` 规范化。

```python
def _is_sensitive_path(self, file_path: str) -> bool:
    # 规范化路径（消除 ../、~、符号链接）
    normalized = str(Path(file_path).expanduser().resolve())
    for pattern in self.settings.sensitive_paths:
        if fnmatch.fnmatch(normalized, pattern):
            return True
    return False
```

同理修改 `_check_path_rules()` 和 `_check_denied_paths()`。

---

### 2.3 HIGH — 跨用户记忆泄露

**涉及文件**：`src/hz_agent_base/middleware/memory.py`

**现状**：所有用户共享同一个 `memory_path`，用户 A 的记忆可被用户 B 搜到。

**方案**：
1. `MemoryMiddleware` 支持 `user_id` 参数，记忆路径按用户隔离
2. 在 `wrap_model_call()` 中从 request 提取 `user_id`（或 `thread_id`），拼接到记忆路径
3. 保持向后兼容：不传 `user_id` 时行为不变（共享记忆）

```python
class MemoryMiddleware(AgentMiddleware):
    def __init__(self, memory_path: str, isolate_by_user: bool = False):
        self.base_path = memory_path
        self.isolate_by_user = isolate_by_user

    def _get_memory_path(self, request) -> str:
        if not self.isolate_by_user:
            return self.base_path
        # 从 request 提取 user_id 或 thread_id
        user_id = getattr(request, "user_id", None) or "shared"
        return str(Path(self.base_path) / user_id)
```

---

### 2.4 HIGH — 命令黑名单太弱

**涉及文件**：`src/hz_agent_base/permissions/settings.py`

**现状**：只有 5 个黑名单模式，子串匹配。

**方案**：
1. 扩充 `SENSITIVE_PATH_PATTERNS`，补充 Windows 路径和更多敏感位置
2. 扩充 `denied_commands`，覆盖更多危险命令模式
3. 使用正则匹配替代子串匹配

```python
denied_commands: list[str] = field(default_factory=lambda: [
    r"rm\s+-rf?\s+/",           # rm -rf /
    r"chmod\s+777",             # chmod 777
    r"curl\s.*\|\s*(ba)?sh",    # curl | sh
    r"wget\s.*\|\s*(ba)?sh",    # wget | sh
    r"eval\s+",                 # eval
    r"exec\s+",                 # exec
    r"\bnc\b",                  # netcat
    r"\bnmap\b",                # nmap
    r"mkfifo",                  # mkfifo
    r"python\s+-c\s+.*import\s+os",  # python -c "import os; os.system(...)"
])
```

同时在 `checker.py` 中将 `pattern in command` 改为 `re.search(pattern, command)`。

---

### 2.5 HIGH — LLM 做安全决策

**涉及文件**：`src/hz_agent_base/hooks/executor.py`

**现状**：PromptHook 和 AgentHook 用 LLM 判断是否放行，模型未配置时默认放行。

**方案**：
1. 模型未配置时默认**阻止**（而非放行），需要显式声明 `allow_without_model=True`
2. 添加配置选项控制默认行为

```python
def _execute_prompt(self, hook, payload):
    if not self.model:
        if hook.allow_without_model:
            return HookResult(success=True, reason="No model, allowed by config")
        return HookResult(
            success=False,
            blocked=True,
            reason="No model configured for PromptHook, blocked by default",
        )
```

3. 文档中明确说明：LLM 安全决策不可靠，关键安全检查应使用 CommandHook（确定性）而非 PromptHook（非确定性）

---

### 2.6 MEDIUM — 知识库无访问控制

**涉及文件**：`src/hz_agent_base/middleware/knowledge.py`

**方案**：
1. `Retriever` 协议新增可选的 `filter_by_user()` 方法
2. `KnowledgeMiddleware` 从 request 提取 `user_id`，传给 retriever
3. 不实现访问控制的 retriever 保持原有行为（全量返回）

```python
# 协议扩展
class Retriever(Protocol):
    def retrieve(self, query: str, top_k: int = 5) -> Sequence[RetrievalResult]: ...
    def retrieve_for_user(self, query: str, top_k: int, user_id: str) -> Sequence[RetrievalResult]:
        """可选：按用户过滤检索结果。默认实现返回全量。"""
        return self.retrieve(query, top_k)
```

---

### 2.7 MEDIUM — 审计日志完整性

**涉及文件**：`src/hz_agent_base/middleware/filesystem.py`

**方案**：
1. 每条日志记录末尾追加 HMAC 签名
2. 提供 `verify_log()` 方法校验日志完整性
3. 签名密钥从环境变量 `AUDIT_HMAC_KEY` 读取

```python
def _sign_record(self, record_json: str) -> str:
    """为日志记录生成 HMAC 签名。"""
    if not self._hmac_key:
        return record_json  # 无密钥时跳过签名
    sig = hmac.new(self._hmac_key, record_json.encode(), hashlib.sha256).hexdigest()[:16]
    return record_json + f',"__sig":"{sig}"'
```

---

### 2.8 MEDIUM — workspace 限制未生效

**涉及文件**：`src/hz_agent_base/middleware/filesystem.py`

**现状**：`workspace` 参数存了但没用。

**方案**：在 `_extract_and_log()` 中检查文件路径是否在 workspace 内。

```python
def _is_in_workspace(self, file_path: str) -> bool:
    """检查文件路径是否在允许的工作目录内。"""
    if not self.workspace:
        return True
    try:
        resolved = Path(file_path).resolve()
        workspace_resolved = Path(self.workspace).resolve()
        return str(resolved).startswith(str(workspace_resolved))
    except Exception:
        return False
```

---

### 2.9 MEDIUM — HTTP Hook 数据泄露

**涉及文件**：`src/hz_agent_base/hooks/executor.py`

**方案**：
1. `HttpHookDefinition` 新增 `allowed_hosts: list[str]` 字段
2. 执行前校验 URL 的 host 是否在白名单内

```python
def _execute_http(self, hook, payload):
    from urllib.parse import urlparse
    host = urlparse(hook.url).hostname
    if hook.allowed_hosts and host not in hook.allowed_hosts:
        return HookResult(success=False, blocked=True, reason=f"Host {host} not in allowed_hosts")
    ...
```

---

### 2.10 LOW — .gitignore 补全

**涉及文件**：`.gitignore`

**方案**：补充缺失的排除模式。

```gitignore
# 环境变量变体
.env.*
.env.local
.env.production
.env.staging

# 密钥和证书
*.pem
*.key
*.p12
*.pfx
credentials.json
secrets.json
service-account.json

# Claude Code 会话数据
.claude/
```

---

### 2.11 LOW — API Key 启动校验

**涉及文件**：`src/hz_agent_base/config.py`、`src/hz_agent_base/agent.py`

**方案**：
1. `config.py` 中 `MODEL_API_KEY` 为空时发出警告（不阻断，因为本地模型不需要 key）
2. `agent.py` 中 `_get_model()` 在需要 API Key 的提供商（DeepSeek、OpenAI、Anthropic）创建模型时校验 key 非空

```python
# agent.py
if "deepseek" in model_lower:
    if not MODEL_API_KEY:
        raise ValueError("DeepSeek 模型需要设置 MODEL_API_KEY 环境变量")
    ...
```

3. `MODEL_BASE_URL` 使用 HTTP 时发出安全警告

---

### 2.12 LOW — MD5 改 SHA-256

**涉及文件**：`src/hz_agent_base/memory/manager.py`

**方案**：将 `hashlib.md5` 改为 `hashlib.sha256`。

```python
def _content_signature(self, content: str) -> str:
    normalized = content.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]
```

---

## 三、实施顺序

```
Phase 1: 高危修复
  ├── 1.1 路径穿越修复（Path.resolve）
  ├── 1.2 shell=True 改造（默认 shell=False + shlex.split）
  ├── 1.3 命令黑名单扩充（正则匹配）
  ├── 1.4 LLM Hook 默认阻止（模型未配置时 blocked）
  └── 1.5 跨用户记忆隔离（isolate_by_user 参数）

Phase 2: 中危修复
  ├── 2.1 审计日志 HMAC 签名
  ├── 2.2 workspace 限制生效
  ├── 2.3 HTTP Hook URL 白名单
  └── 2.4 知识库检索按用户过滤

Phase 3: 低危修复
  ├── 3.1 .gitignore 补全
  ├── 3.2 API Key 启动校验
  └── 3.3 MD5 改 SHA-256

Phase 4: 测试与文档
  ├── 4.1 安全相关单元测试
  ├── 4.2 路径穿越攻击测试
  ├── 4.3 命令注入测试
  ├── 4.4 更新文档
  └── 4.5 PR 合入 main
```

---

## 四、验收标准

| 检查项 | 标准 |
|--------|------|
| `../` 路径穿越 | 被 `Path.resolve()` 消除，无法绕过敏感路径检查 |
| shell=True | 默认关闭，显式声明才开启 |
| 命令注入 | 正则匹配覆盖常见注入手法 |
| LLM Hook 无模型 | 默认阻止，不静默放行 |
| 跨用户记忆 | `isolate_by_user=True` 时按用户隔离 |
| 审计日志 | HMAC 签名，`verify_log()` 可校验完整性 |
| .gitignore | 覆盖 `.env.*`、`*.pem`、`*.key`、`credentials.json` |
| API Key | 空 key 时明确报错 |
| 测试覆盖 | 安全相关测试全部通过 |
