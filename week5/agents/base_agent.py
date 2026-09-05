"""Base agent contract.

Every specialized agent (CEO, PM, Research, SWE, QA, Tech Writer) inherits
from BaseAgent.  The agent loop handles tool calling, RBAC enforcement,
and turn limits uniformly — subclasses only define their system prompt,
allowed tools, and role name.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from config import MAX_AGENT_TURNS
from providers.base import Provider, Response
from security.guardrails import agent_can_use_tool, check_injection
from tools.base import execute_tool, get_tool_schemas


class BaseAgent:
    """A specialized agent that runs an agentic tool-calling loop."""

    role: str = "base"
    system_prompt: str = "You are a helpful assistant."
    allowed_tools: list[str] = []

    def __init__(self, provider: Provider):
        self.provider = provider

    def run(self, task: str, context: str = "") -> dict[str, Any]:
        """Execute the agent loop and return structured output.

        Returns a dict with:
          - response: the final text output
          - tool_calls_made: list of (tool_name, arguments, result) tuples
          - turns: how many LLM calls were made
          - model_used: which model actually served the request
        """
        # Build allowed tool schemas
        tool_schemas = get_tool_schemas(self.allowed_tools) if self.allowed_tools else None

        messages: list[dict] = [
            {"role": "system", "content": self._build_system_prompt()},
        ]
        if context:
            messages.append({"role": "user", "content": f"Context:\n{context}"})
        messages.append({"role": "user", "content": task})

        tool_calls_made: list[tuple[str, dict, str]] = []
        model_used = ""

        for turn in range(MAX_AGENT_TURNS):
            resp = self.provider.chat(
                messages=messages,
                tools=tool_schemas,
                temperature=self._temperature(),
            )
            model_used = resp.model_used or model_used

            if not resp.wants_tool:
                # Final response — agent is done
                return {
                    "response": resp.text,
                    "tool_calls_made": tool_calls_made,
                    "turns": turn + 1,
                    "model_used": model_used,
                }

            # Process tool calls
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": resp.text or None}
            if resp.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in resp.tool_calls
                ]
            messages.append(assistant_msg)

            for tc in resp.tool_calls:
                # RBAC check — single enforcement point
                if not agent_can_use_tool(self.role, tc.name):
                    result = f"DENIED: {self.role} agent does not have permission to use '{tc.name}'."
                else:
                    result = execute_tool(tc.name, tc.arguments)

                tool_calls_made.append((tc.name, tc.arguments, result))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        # Exhausted turns
        return {
            "response": "[Agent reached maximum turn limit without a final response]",
            "tool_calls_made": tool_calls_made,
            "turns": MAX_AGENT_TURNS,
            "model_used": model_used,
        }

    def _build_system_prompt(self) -> str:
        return self.system_prompt

    def _temperature(self) -> float:
        from config import AGENT_TEMPERATURE
        return AGENT_TEMPERATURE
