"""Core agent creation entry point."""

from __future__ import annotations

import uuid
from typing import Any, Callable, Sequence

from deepagents import create_deep_agent
from deepagents.graph import CompiledStateGraph
from deepagents.backends import BackendProtocol
from langchain_openai import ChatOpenAI

from .config import DEEPSEEK_API_KEY, DEFAULT_MODEL, DEEPSEEK_BASE_URL
from .middleware import AgentMiddleware
from .middleware.permission import PermissionMiddleware
from .middleware.hook import HookMiddleware
from .middleware.memory import MemoryMiddleware
from .middleware.knowledge import KnowledgeMiddleware
from .middleware.filesystem import FilesystemMiddleware
from .knowledge.protocol import Retriever
from .coordinator.worker import WorkerConfig
from .coordinator.coordinator import CoordinatorMiddleware
from .permissions import PermissionSettings
from .hooks import HookRegistry


def _get_model(model: str | Any | None = None) -> Any:
    """Resolve model string to a LangChain chat model instance.

    Args:
        model: Model name string or a pre-configured model instance.

    Returns:
        A LangChain chat model instance.
    """
    if model is None:
        model = DEFAULT_MODEL

    # If already a model instance, return as-is
    if hasattr(model, "invoke"):
        return model

    # String model name - create ChatOpenAI for DeepSeek
    if isinstance(model, str):
        # DeepSeek uses OpenAI-compatible API
        if "deepseek" in model.lower():
            return ChatOpenAI(
                model=model,
                base_url=DEEPSEEK_BASE_URL,
                api_key=DEEPSEEK_API_KEY,
            )
        # Default to ChatOpenAI for other models
        return ChatOpenAI(model=model)

    return model


def create_agent(
    model: str | Any | None = None,
    tools: Sequence[Any] | None = None,
    *,
    system_prompt: str | None = None,
    permissions: PermissionSettings | None = None,
    hooks: HookRegistry | None = None,
    memory_path: str | None = None,
    retriever: Retriever | None = None,
    knowledge_top_k: int = 5,
    filesystem: bool | dict[str, Any] = False,
    workers: list[WorkerConfig] | None = None,
    middleware: Sequence[AgentMiddleware] | None = None,
    backend: BackendProtocol | None = None,
    **kwargs,
) -> CompiledStateGraph:
    """Create an agent with HZAgentBase harness.

    Args:
        model: LLM model name or instance. Defaults to deepseek-v4-flash.
        tools: Custom tools to register.
        system_prompt: Custom system prompt.
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
        **kwargs: Additional arguments passed to create_deep_agent().

    Returns:
        Compiled LangGraph agent ready to run.
        Thread-safe: the same instance can serve multiple users concurrently.
    """
    harness_middleware: list[AgentMiddleware] = []

    # 1. Permission middleware (first - gates all tool calls)
    if permissions is None:
        permissions = PermissionSettings()
    harness_middleware.append(PermissionMiddleware(permissions))

    # 2. Hook middleware (lifecycle events)
    if hooks is not None:
        harness_middleware.append(HookMiddleware(hooks))

    # 3. Memory middleware (inject/extract persistent knowledge)
    if memory_path is not None:
        harness_middleware.append(MemoryMiddleware(memory_path))

    # 4. Knowledge middleware (RAG retrieval from knowledge base)
    if retriever is not None:
        harness_middleware.append(KnowledgeMiddleware(retriever, top_k=knowledge_top_k))

    # 5. Filesystem middleware (audit and change tracking)
    if filesystem:
        fs_opts = filesystem if isinstance(filesystem, dict) else {}
        harness_middleware.append(FilesystemMiddleware(**fs_opts))

    # 6. User-provided middleware
    if middleware:
        harness_middleware.extend(middleware)

    # 7. Coordinator middleware (multi-agent orchestration)
    coordinator = None
    if workers:
        coordinator = CoordinatorMiddleware(workers)
        harness_middleware.append(coordinator)

    # Resolve model
    resolved_model = _get_model(model)

    # 构建 create_deep_agent 参数
    agent_kwargs: dict[str, Any] = {
        "model": resolved_model,
        "tools": tools,
        "system_prompt": system_prompt,
        "middleware": harness_middleware,
        "backend": backend,
    }

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

    Returns:
        The agent's response state including messages.
    """
    if thread_id is None:
        thread_id = str(uuid.uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    input_state = {
        "messages": [{"role": "user", "content": message}],
    }

    return agent.invoke(input_state, config=config)
