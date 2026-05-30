# HZAgentBase 功能规划

## 高优先级

### 1. 对话历史管理

**问题**：长对话 token 超限，LLM 报错或截断。

**方案**：新增 `HistoryMiddleware`，在调用 LLM 前自动管理历史。

- `strategy="sliding"`：保留最近 N 条消息，丢弃更早的
- `strategy="summary"`：用 LLM 对旧消息生成摘要，保留摘要 + 最近 N 条

**改动**：新增 `middleware/history.py`，`create_agent()` 加 `history` 参数。

---

### 2. 输出清洗

**问题**：LLM 可能输出敏感信息（手机号、身份证、密码等）。

**方案**：新增 `SanitizerMiddleware`，在 LLM 响应后用正则过滤敏感信息。

- 内置常用规则（手机号、身份证、邮箱、密码）
- 支持自定义正则规则
- 支持自定义替换文本

**改动**：新增 `middleware/sanitizer.py`，`create_agent()` 加 `sanitizer` 参数。

---

### 3. Guardrails

**问题**：LLM 输出可能包含幻觉、违规内容、格式错误。

**方案**：新增 `GuardrailMiddleware`，用规则或 LLM 校验输出。

- `FormatRule`：检查输出格式（JSON/Markdown 结构）
- `ContentRule`：检查违规内容（敏感词、有害信息）
- `HallucinationRule`：对比知识库，检测幻觉
- 支持自定义规则

**改动**：新增 `middleware/guardrails/` 目录，内置常用规则。

---

### 4. Agent 自我反思

**问题**：Agent 输出质量不稳定，有时答非所问。

**方案**：新增 `ReflectionMiddleware`，让 Agent 评估自己的输出。

- LLM 生成回答后，用 LLM 评估回答质量（准确性、完整性）
- 评分低于阈值时，加入反馈重新生成
- 最多重试 N 次

**改动**：新增 `middleware/reflection.py`，`create_agent()` 加 `reflection` 参数。

---

### 5. Human-in-the-loop

**问题**：关键操作（写文件、执行命令）需要人工确认。

**方案**：利用 Deep Agents 的 `interrupt_on` 机制。

- `create_agent(interrupt_on={"write_file": True})`：写文件时暂停
- Web 端新增确认接口 `/chat/confirm`
- 用户确认后继续执行，拒绝则跳过

**改动**：`create_agent()` 透传 `interrupt_on` 参数，新增 Web 端确认示例。

---

### 6. 跨会话 Agent 记忆

**问题**：当前记忆是用户级别的，Agent 自身的经验没有积累。

**方案**：新增 `AgentMemoryMiddleware`，独立于用户记忆。

- Agent 记忆存储在 `.agent_memory/` 目录
- 调用前注入历史经验到系统提示词
- 调用后提取新经验（"用 X 方法解决了 Y 问题"）
- 与用户记忆完全隔离

**改动**：新增 `middleware/agent_memory.py`，`create_agent()` 加 `agent_memory` 参数。

---

## 低优先级

### 7. 工具版本管理

**方案**：工具注册时带版本号，Agent 根据配置选择版本。支持向后兼容。

### 8. 可观测性

**方案**：新增 `ObservabilityMiddleware`，记录每个中间件的耗时、token 消耗、请求链路。

### 9. 沙箱执行

**方案**：依赖 Deep Agents 的 `SandboxBackend`，HZAgentBase 只需透传配置。

---

## 暂不需要

- CLI 测试覆盖
- Token 用量追踪（可看 API 后台）
- 限流控制（单团队使用）
- PEP 561 py.typed 标记
