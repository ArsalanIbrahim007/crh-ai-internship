"""Groq backend with model-fallback chain and rate-limit handling.

Groq rate limits are per-model, not per-key. A single-model client fails
the moment a quota trips.  This provider rotates through a fallback chain
so the system stays live even when the primary model is throttled.
"""

import json
import os
import re
import time
import uuid

from groq import Groq, RateLimitError, APIError, BadRequestError, NotFoundError

from .base import Provider, Response, ToolCall

MAX_RETRIES = 3

_RL_WINDOW = re.compile(r"(tokens|requests) per (day|minute|hour)", re.I)
_RL_RETRY = re.compile(r"try again in ([\dhms.]+)", re.I)

# Recover tool calls the model wrote as text instead of structured output.
_TEXT_TOOL = re.compile(
    r"<function[/= ]*(\w+)\s*(\{.*?\})\s*</function>",
    re.S,
)


def _parse_wait(s: str) -> float | None:
    """Parse Groq's 'try again in 1.5s' / '2m30s' into seconds."""
    try:
        s = s.strip().lower()
        if s.endswith('s') and 'm' not in s and 'h' not in s:
            return float(s[:-1])
        total = 0.0
        for part in re.findall(r'([\d.]+)([hms])', s):
            val = float(part[0])
            if part[1] == 'h': total += val * 3600
            elif part[1] == 'm': total += val * 60
            else: total += val
        return total if total > 0 else None
    except (ValueError, IndexError):
        return None


class GroqProvider(Provider):
    """Groq-hosted inference with automatic model fallback."""

    def __init__(
        self,
        model: str | None = None,
        fallback_models: list[str] | None = None,
        api_key: str | None = None,
    ):
        from config import DEFAULT_MODEL, FALLBACK_MODELS, GROQ_API_KEY

        key = api_key or GROQ_API_KEY or os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Add it to .env or pass api_key=."
            )

        self.client = Groq(api_key=key, timeout=60.0)
        self.primary_model = model or DEFAULT_MODEL
        self.fallback_models = fallback_models or list(FALLBACK_MODELS)
        self.name = f"groq:{self.primary_model}"

        # running totals
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_calls = 0
        self.failed_parses = 0
        self._exhausted: set[str] = set()  # models with daily quota hit

    def _model_chain(self) -> list[str]:
        """Primary model first, then fallbacks, skipping daily-exhausted ones."""
        chain = [self.primary_model] + self.fallback_models
        return [m for m in chain if m not in self._exhausted]

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 900,
        temperature: float = 0.0,
        model: str | None = None,
    ) -> Response:
        chain = [model] if model else self._model_chain()
        if not chain:
            raise RuntimeError("All models in the fallback chain are exhausted.")

        last_error = None
        for current_model in chain:
            try:
                return self._call(
                    messages, tools, max_tokens, temperature, current_model
                )
            except RateLimitError as e:
                msg = str(e)
                last_error = e
                window = _RL_WINDOW.search(msg)
                is_daily = window and window.group(2).lower() == "day"
                if is_daily:
                    self._exhausted.add(current_model)

                # If 'request too large' — reduce max_tokens and retry same model
                if "request too large" in msg.lower() or "expected output tokens exceed" in msg.lower():
                    max_tokens = min(max_tokens, 800)
                    continue

                # Parse 'try again in Xs' and wait
                retry_match = _RL_RETRY.search(msg)
                if retry_match and not is_daily:
                    wait_str = retry_match.group(1)
                    wait_secs = _parse_wait(wait_str)
                    if wait_secs and wait_secs < 120:
                        time.sleep(wait_secs + 1)
                        continue

                # try next model in chain
                continue
            except BadRequestError as e:
                # Model wrote tool call as text — try to salvage
                if "failed to call a function" in str(e).lower():
                    return self._salvage_text_tool_call(str(e), current_model)
                raise
            except (NotFoundError, APIError) as e:
                # Model removed or unavailable — try next
                last_error = e
                continue

        raise RuntimeError(
            f"All models exhausted or rate-limited. Last error: {last_error}"
        )

    def _call(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        max_tokens: int,
        temperature: float,
        model: str,
    ) -> Response:
        kwargs: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        t0 = time.time()
        for attempt in range(MAX_RETRIES):
            try:
                raw = self.client.chat.completions.create(**kwargs)
                break
            except RateLimitError:
                if attempt == MAX_RETRIES - 1:
                    raise
                wait = 2 ** attempt + 1
                time.sleep(wait)
            except APIError as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(2)
        else:
            raise RuntimeError("Exhausted retries")

        elapsed = time.time() - t0
        choice = raw.choices[0]
        msg = choice.message

        usage = raw.usage
        self.total_prompt_tokens += usage.prompt_tokens if usage else 0
        self.total_completion_tokens += usage.completion_tokens if usage else 0
        self.total_calls += 1

        response = Response(
            text=msg.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            seconds=elapsed,
            model_used=model,
        )

        # Parse structured tool calls
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                    response.tool_calls.append(
                        ToolCall(
                            name=tc.function.name,
                            arguments=args,
                            id=tc.id or str(uuid.uuid4()),
                            raw=tc.function.arguments,
                        )
                    )
                except (json.JSONDecodeError, ValueError):
                    self.failed_parses += 1
                    response.parse_failed = True

        # Fallback: recover tool calls written as text
        if not response.tool_calls and response.text:
            recovered = self._recover_text_tool_calls(response.text)
            if recovered:
                response.tool_calls = recovered[:1]
                response.text = ""

        return response

    def _recover_text_tool_calls(self, text: str) -> list[ToolCall]:
        calls = []
        for m in _TEXT_TOOL.finditer(text):
            try:
                args = json.loads(m.group(2))
                calls.append(
                    ToolCall(
                        name=m.group(1),
                        arguments=args,
                        id=str(uuid.uuid4()),
                        raw=m.group(0),
                    )
                )
            except (json.JSONDecodeError, ValueError):
                pass
        return calls

    def _salvage_text_tool_call(self, error_text: str, model: str) -> Response:
        """When Groq rejects a request because the model wrote the call as text."""
        calls = self._recover_text_tool_calls(error_text)
        if calls:
            return Response(
                tool_calls=calls[:1],
                model_used=model,
            )
        return Response(
            text=f"Model produced an unparseable tool call: {error_text[:200]}",
            parse_failed=True,
            model_used=model,
        )
