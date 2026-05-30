"""Core agent creation entry point."""

from __future__ import annotations

import uuid
from typing import Any, Callable, Sequence

from deepagents import create_deep_agent
from deepagents.graph import CompiledStateGraph
from deepagents.backends import BackendProtocol
from langchain_openai import ChatOpenAI

from .config import (
    DEFAULT_MODEL, MODEL_API_KEY, MODEL_BASE_URL,
    AUDIT_LOG_PATH, KNOWLEDGE_TOP_K,
    MODEL_REQUEST_TIMEOUT, MODEL_MAX_RETRIES, RECURSION_LIMIT,
)
from .middleware import AgentMiddleware
from .middleware.permission import PermissionMiddleware
from .middleware.hook import HookMiddleware
from .middleware.memory import MemoryMiddleware
from .middleware.knowledge import KnowledgeMiddleware
from .middleware.filesystem import FileAuditMiddleware
from .resilience.protocols import CancellationChecker, StopCondition
from .middleware.resilient import ResilientMiddleware
from .knowledge.protocol import Retriever
from .coordinator.worker import WorkerConfig
from .coordinator.coordinator import CoordinatorMiddleware
from .prompts.manager import load_prompt
from .permissions import PermissionSettings
from .hooks import HookRegistry

# 各提供商的默认 API 地址（MODEL_BASE_URL 未设置时使用）
_PROVIDER_DEFAULT_URLS = {
    # 云端提供商
    "deepseek": "https://api.deepseek.com/v1",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    # 本地服务
    "ollama": "http://localhost:11434/v1",
    "vllm": "http://localhost:8000/v1",
    "lmstudio": "http://localhost:1234/v1",
    "localai": "http://localhost:8080/v1",
}


def _get_model(
    model: str | Any | None = None,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Any:
    """Resolve model string to a LangChain chat model instance.

    根据 DEFAULT_MODEL 的值自动选择提供商，统一使用 MODEL_API_KEY 认证：
    - deepseek-*  → DeepSeek API
    - gpt-* / o1-* / o3-* → OpenAI API
    - claude-*    → Anthropic API（langchain-anthropic）
    - gemini-*    → Google Gemini API（langchain-google-genai）
    - 其他        → OpenAI 兼容方式（Ollama、vLLM、LM Studio 等，需设置 MODEL_BASE_URL）

    也可以直接传入已配置好的 LangChain 模型实例，会原样返回。

    Args:
        model: Model name string or a pre-configured model instance.
        api_key: API key override. If None, uses MODEL_API_KEY from config.
        base_url: Base URL override. If None, uses MODEL_BASE_URL from config.

    Returns:
        A LangChain chat model instance.
    """
    if model is None:
        model = DEFAULT_MODEL

    # 已经是模型实例，直接返回
    if hasattr(model, "invoke"):
        return model

    if not isinstance(model, str):
        return model

    # 解析 api_key 和 base_url：参数 > 全局配置
    resolved_key = api_key or MODEL_API_KEY
    resolved_base = base_url or MODEL_BASE_URL
    timeout = MODEL_REQUEST_TIMEOUT

    model_lower = model.lower()

    # Anthropic（claude-*）— 使用独立 SDK，不走 base_url
    if "claude" in model_lower:
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model, api_key=resolved_key,
                timeout=timeout,
            )
        except ImportError:
            raise ImportError(
                "使用 Claude 模型需要安装 langchain-anthropic: "
                "pip install langchain-anthropic"
            )

    # Google Gemini — 使用独立 SDK，不走 base_url
    if "gemini" in model_lower:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model, google_api_key=resolved_key,
                timeout=timeout,
            )
        except ImportError:
            raise ImportError(
                "使用 Gemini 模型需要安装 langchain-google-genai: "
                "pip install langchain-google-genai"
            )

    # DeepSeek — 使用 langchain-deepseek 官方包（支持 reasoning_content）
    if "deepseek" in model_lower:
        effective_url = resolved_base or _PROVIDER_DEFAULT_URLS["deepseek"]
        try:
            from langchain_deepseek import ChatDeepSeek
            return ChatDeepSeek(
                model=model, api_key=resolved_key, base_url=effective_url,
                timeout=timeout,
            )
        except ImportError:
            # 降级到 ChatOpenAI（不支持 reasoning_content）
            return ChatOpenAI(
                model=model, api_key=resolved_key, base_url=effective_url,
                request_timeout=timeout,
            )

    # 以下均为 OpenAI 兼容 API（OpenAI、Ollama 等）
    # 确定 base_url：用户显式设置 > 提供商默认 > 不传（让 SDK 自己决定）
    if not resolved_base:
        if any(model_lower.startswith(p) for p in ("gpt-", "o1-", "o3-")):
            resolved_base = _PROVIDER_DEFAULT_URLS["openai"]

    kwargs: dict[str, Any] = {
        "model": model,
        "api_key": resolved_key,
        "request_timeout": timeout,
    }
    if resolved_base:
        kwargs["base_url"] = resolved_base

    return ChatOpenAI(**kwargs)


def create_agent(
    model: str | Any | None = None,
    tools: Sequence[Any] | None = None,
    *,
    system_prompt: str | None = None,
    rules: list[str] | None = None,
    permissions: PermissionSettings | None = None,
    hooks: HookRegistry | None = None,
    memory_path: str | None = None,
    memory_isolate_by_user: bool = True,
    retriever: Retriever | None = None,
    knowledge_top_k: int = KNOWLEDGE_TOP_K,
    filesystem: bool | dict[str, Any] = False,
    workers: list[WorkerConfig] | None = None,
    middleware: Sequence[AgentMiddleware] | None = None,
    backend: BackendProtocol | None = None,
    skills: list[str] | None = None,
    cancellation_checker: Any | None = None,
    stop_condition: Any | None = None,
    max_retries: int = MODEL_MAX_RETRIES,
    api_key: str | None = None,
    base_url: str | None = None,
    **kwargs,
) -> CompiledStateGraph:
    """Create an agent with HZAgentBase harness.

    Args:
        model: LLM model name or instance. Defaults to DEFAULT_MODEL from .env.
               根据名称自动匹配提供商，也可传入预配置的模型实例。
        tools: Custom tools to register.
        system_prompt: Custom system prompt. 支持三种形式：
            - 字符串：直接作为提示词文本
            - 文件路径（.md）：从文件加载
            - 目录路径：从目录加载 base.md + rules/
        rules: 共享规则目录列表。目录下的 .md 文件自动加载，
               拼接到 system_prompt 之后。所有 agent（含 workers）共享。
        permissions: Permission settings. If None, uses DEFAULT mode.
        hooks: Hook registry for lifecycle events.
        memory_path: Path to memory directory for persistent knowledge.
        retriever: Knowledge base retriever for RAG. Any object implementing
                   the Retriever protocol (e.g., from hz-knowledge-base).
        knowledge_top_k: Number of knowledge results to retrieve per query.
        filesystem: Enable file operation audit and change tracking.
                    - True: enable with defaults (audit=True, track_changes=True)
                    - dict: pass options (audit, track_changes, workspace, log_path)
                    - False: disabled (default)
        workers: Worker agent configs for multi-agent orchestration.
                 Creates a Coordinator with sub-agents.
        middleware: Additional custom middleware.
        backend: Filesystem/sandbox backend.
        api_key: API key override for multi-tenant. If None, uses MODEL_API_KEY from .env.
        base_url: Base URL override for multi-tenant. If None, uses MODEL_BASE_URL from .env.
        **kwargs: Additional arguments passed to create_deep_agent().

    Returns:
        Compiled LangGraph agent ready to run.
        Thread-safe: the same instance can serve multiple users concurrently.
    """
    # 加载提示词（支持字符串、文件路径、目录路径）
    resolved_prompt = load_prompt(system_prompt, shared_rules=rules)

    # 提前解析 model，供 HookMiddleware 使用（PromptHook / AgentHook 需要 LLM）
    resolved_model = _get_model(model, api_key=api_key, base_url=base_url)

    harness_middleware: list[AgentMiddleware] = []

    # 1. Permission middleware (first - gates all tool calls)
    if permissions is None:
        permissions = PermissionSettings()
    harness_middleware.append(PermissionMiddleware(permissions))

    # 2. Hook middleware (lifecycle events)
    if hooks is not None:
        harness_middleware.append(HookMiddleware(hooks, model=resolved_model))

    # 3. Memory middleware (inject/extract persistent knowledge)
    if memory_path is not None:
        harness_middleware.append(MemoryMiddleware(memory_path, isolate_by_user=memory_isolate_by_user))

    # 4. Knowledge middleware (RAG retrieval from knowledge base)
    if retriever is not None:
        harness_middleware.append(KnowledgeMiddleware(retriever, top_k=knowledge_top_k))

    # 5. Filesystem middleware (audit and change tracking)
    if filesystem:
        # 默认配置：开启审计、开启变更追踪、日志路径从 .env 读取
        default_fs_opts = {"log_path": AUDIT_LOG_PATH}
        if isinstance(filesystem, dict):
            # 移除 audit 键，防止意外关闭审计（传 dict 表示配置，关闭请用 False）
            fs_opts = {k: v for k, v in filesystem.items() if k != "audit"}
            default_fs_opts.update(fs_opts)
        harness_middleware.append(FileAuditMiddleware(**default_fs_opts))

    # 6. User-provided middleware
    if middleware:
        harness_middleware.extend(middleware)

    # 7. Resilient middleware (retry, cancellation, stop condition)
    if cancellation_checker is not None or stop_condition is not None or max_retries > 0:
        harness_middleware.append(ResilientMiddleware(
            cancellation_checker=cancellation_checker,
            stop_condition=stop_condition,
            max_retries=max_retries,
        ))

    # 8. Coordinator middleware (multi-agent orchestration)
    coordinator = None
    if workers:
        coordinator = CoordinatorMiddleware(workers, shared_rules=rules)
        harness_middleware.append(coordinator)

    # 构建 create_deep_agent 参数
    agent_kwargs: dict[str, Any] = {
        "model": resolved_model,
        "tools": tools,
        "system_prompt": resolved_prompt,
        "middleware": harness_middleware,
        "backend": backend,
    }

    # 技能目录列表
    if skills:
        agent_kwargs["skills"] = skills

    # 有 workers 时传入 subagents
    if coordinator:
        agent_kwargs["subagents"] = coordinator.subagents

    # 用户传入的 kwargs 覆盖默认值
    agent_kwargs.update(kwargs)

    return create_deep_agent(**agent_kwargs)


def run_agent(
    agent: CompiledStateGraph,
    message: str,
    *,
    thread_id: str | None = None,
    user_id: str | None = None,
    recursion_limit: int = RECURSION_LIMIT,
) -> dict[str, Any]:
    """Run an agent with a single message, with thread isolation.

    Each call is fully isolated via thread_id. Different users should
    use different thread_id values to ensure state isolation.

    Args:
        agent: The compiled agent from create_agent().
        message: The user message to send.
        thread_id: Unique thread identifier. Auto-generated if not provided.
                   Use different thread_id for different users/sessions.
        user_id: Optional user identifier for logging.
        recursion_limit: Agent 最大执行步数，防止死循环。默认从 .env 读取。

    Returns:
        The agent's response state including messages.
    """
    if agent is None:
        raise ValueError("agent must not be None. Use create_agent() to create one.")
    if not message or not isinstance(message, str):
        raise ValueError("message must be a non-empty string.")

    if thread_id is None:
        thread_id = str(uuid.uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id or thread_id or "default-user",
        }
    }

    input_state = {
        "messages": [{"role": "user", "content": message}],
    }

    return agent.invoke(input_state, config=config, recursion_limit=recursion_limit)
