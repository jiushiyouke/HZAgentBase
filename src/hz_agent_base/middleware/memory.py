"""Memory middleware - injects relevant memories and extracts new ones."""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware.types import AgentMiddleware

from ..memory.manager import MemoryManager
from ..memory.relevance import select_relevant_memories, format_relevant_memories


class MemoryMiddleware(AgentMiddleware):
    """Manages persistent cross-session memory.

    Before each turn: loads relevant memories into system prompt.
    After each turn: extracts and saves new memories from conversation.
    """

    def __init__(self, memory_path: str):
        self.manager = MemoryManager(memory_path)

    def wrap_model_call(self, request: dict[str, Any], handler) -> dict[str, Any]:
        """Inject memories before call, extract after."""
        # Get the latest user message for relevance search
        messages = request.get("messages", [])
        query = ""
        if messages:
            last_msg = messages[-1]
            if isinstance(last_msg, dict):
                query = last_msg.get("content", "")
            elif hasattr(last_msg, "content"):
                query = last_msg.content

        # Inject relevant memories into system prompt
        if query:
            memories = select_relevant_memories(query, self.manager.path, max_results=5)
            if memories:
                memory_context = format_relevant_memories(memories)
                current_system = request.get("system", "")
                request["system"] = f"{current_system}\n\n## Relevant Memories\n{memory_context}"

        # Call the next middleware / LLM
        response = handler(request)

        # Extract and save new memories from the conversation
        self.manager.extract_and_save(messages, response)

        return response
