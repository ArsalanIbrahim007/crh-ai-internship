"""Tool definitions and registry.

Each tool is:
  1. A plain Python function that does the work.
  2. A JSON schema (OpenAI function-calling format) that tells the model
     what the tool does and what arguments it takes.

The agent loop calls tools by name through TOOL_REGISTRY.
"""

from __future__ import annotations

from typing import Any, Callable


# Global registry: tool_name → (callable, json_schema)
TOOL_REGISTRY: dict[str, tuple[Callable[..., str], dict]] = {}


def register_tool(schema: dict) -> Callable:
    """Decorator that registers a function as a callable tool."""
    def decorator(fn: Callable[..., str]) -> Callable[..., str]:
        name = schema["function"]["name"]
        TOOL_REGISTRY[name] = (fn, schema)
        return fn
    return decorator


def get_tool_schemas(tool_names: list[str] | None = None) -> list[dict]:
    """Return JSON schemas for the given tool names (or all tools)."""
    if tool_names is None:
        return [schema for _, schema in TOOL_REGISTRY.values()]
    return [
        TOOL_REGISTRY[name][1]
        for name in tool_names
        if name in TOOL_REGISTRY
    ]


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Run a tool by name and return its string result."""
    if name not in TOOL_REGISTRY:
        return f"Error: Unknown tool '{name}'"
    fn, _ = TOOL_REGISTRY[name]
    try:
        return fn(**arguments)
    except Exception as e:
        return f"Error executing {name}: {e}"
