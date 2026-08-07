"""Common interface for every model backend.

The agent talks only to this interface, so swapping local Mistral for a hosted API is a
one-line change and nothing else in the codebase has to know which is running.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """One tool the model asked to run."""
    name: str
    arguments: dict[str, Any]
    raw: str = ""          # what the model actually emitted, kept for debugging


@dataclass
class Response:
    """What came back from one generation."""
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    # generation stats, useful for the reliability numbers in the writeup
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    parse_failed: bool = False   # model tried to call a tool but emitted invalid JSON

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
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> Response:
        """Run one turn.

        messages follows the OpenAI convention: a list of dicts with 'role' and 'content'.
        Roles used here are system, user, assistant and tool.

        tools is a list of JSON schema tool definitions, or None for a plain completion.

        Temperature defaults to 0 because tool calling needs to be reproducible - a model
        that picks a different tool on each run is impossible to debug or benchmark.
        """
        raise NotImplementedError

    def close(self) -> None:
        """Release resources. Local providers free GPU memory here."""
        pass
