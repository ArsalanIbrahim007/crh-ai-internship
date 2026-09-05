"""Memory tools — recall and write to long-term memory."""

from __future__ import annotations

from memory.long_term_memory import LongTermMemory
from tools.base import register_tool

# Singleton memory instance
_memory = LongTermMemory()

_RECALL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "memory_recall",
        "description": (
            "Search long-term memory for past initiatives, architectural decisions, "
            "and retrospective lessons. Returns the most relevant entries."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for memory recall.",
                },
                "category": {
                    "type": "string",
                    "enum": ["initiative", "decision", "retrospective"],
                    "description": "Optional category filter.",
                },
            },
            "required": ["query"],
        },
    },
}


@register_tool(_RECALL_SCHEMA)
def memory_recall(query: str, category: str | None = None) -> str:
    entries = _memory.recall(query, category=category)  # type: ignore[arg-type]
    if not entries:
        return "No relevant memories found."

    parts = []
    for e in entries:
        parts.append(
            f"**[{e.category}] {e.title}**\n{e.content}"
        )
    return "\n\n---\n\n".join(parts)


_WRITE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "memory_write",
        "description": (
            "Store a new entry in long-term memory. Use for recording decisions, "
            "lessons learned, or initiative outcomes for future reference."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["initiative", "decision", "retrospective"],
                    "description": "The type of memory to store.",
                },
                "title": {
                    "type": "string",
                    "description": "Short title for the memory entry.",
                },
                "content": {
                    "type": "string",
                    "description": "The detailed content to remember.",
                },
            },
            "required": ["category", "title", "content"],
        },
    },
}


@register_tool(_WRITE_SCHEMA)
def memory_write(category: str, title: str, content: str) -> str:
    entry_id = _memory.store(
        category=category,  # type: ignore[arg-type]
        title=title,
        content=content,
    )
    return f"Stored memory #{entry_id}: [{category}] {title}"
