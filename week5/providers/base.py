"""Common interface for every model backend.

The agent talks only to this interface, so swapping providers is a one-line
change and nothing else in the codebase has to know which is running.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """One tool the model asked to run."""
    name: str
    arguments: dict[str, Any]
    id: str = ""
    raw: str = ""


@dataclass
class Response:
    """What came back from one generation."""
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    parse_failed: bool = False
    model_used: str = ""

    @property
    def wants_tool(self) -> bool:
        return len(self.tool_calls) > 0


class Provider(ABC):
    """A model backend."""

    name: str = "unnamed"

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        model: str | None = None,
    ) -> Response:
        raise NotImplementedError

    def close(self) -> None:
        pass
