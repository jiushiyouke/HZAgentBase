"""Core agent creation entry point."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from deepagents import create_deep_agent
from deepagents.graph import CompiledStateGraph
from deepagents.backends import BackendProtocol
from langchain_openai import ChatOpenAI

from .middleware import AgentMiddleware
from .middleware.permission import PermissionMiddleware
from .middleware.hook import HookMiddleware
from .middleware.memory import MemoryMiddleware
from .permissions import PermissionSettings
from .hooks import HookRegistry

DEFAULT_MODEL = "deepseek-v4-flash"


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
                base_url="https://api.deepseek.com/v1",
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
        middleware: Additional custom middleware.
        backend: Filesystem/sandbox backend.
        **kwargs: Additional arguments passed to create_deep_agent().

    Returns:
        Compiled LangGraph agent ready to run.
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

    # 4. User-provided middleware
    if middleware:
        harness_middleware.extend(middleware)

    # Resolve model
    resolved_model = _get_model(model)

    return create_deep_agent(
        model=resolved_model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=harness_middleware,
        backend=backend,
        **kwargs,
    )
