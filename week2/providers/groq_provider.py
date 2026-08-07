"""Groq backend.

Groq hosts open models on custom inference hardware. Nothing runs locally - this is an
HTTPS call - so the copilot needs a network connection but no GPU.

Model choice: llama-3.3-70b-versatile. Tool calling is where model size shows most, and a
70B model handles schema-following reliably where small models emit malformed JSON.

The free tier caps tokens per minute, and an agent loop is token-hungry because every turn
resends the whole conversation plus all tool schemas. Rate limit handling is therefore built
in rather than bolted on later.
"""

import json
import os
import random
import time

from groq import Groq, RateLimitError, APIError

from .base import Provider, Response, ToolCall

DEFAULT_MODEL = "llama-3.3-70b-versatile"
MAX_RETRIES = 4


class GroqProvider(Provider):
    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        key = api_key or os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Create week2/.env containing:\n"
                "    GROQ_API_KEY=gsk_your_key_here"
            )
        self.client = Groq(api_key=key)
        self.model = model
        self.name = f"groq:{model}"

        # running totals, so the app can show what a session cost
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_calls = 0
        self.rate_limit_waits = 0

    # ------------------------------------------------------------------
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> Response:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        started = time.perf_counter()
        completion = self._call_with_retry(kwargs)
        elapsed = time.perf_counter() - started

        msg = completion.choices[0].message
        usage = completion.usage

        self.total_prompt_tokens += usage.prompt_tokens
        self.total_completion_tokens += usage.completion_tokens
        self.total_calls += 1

        response = Response(
            text=(msg.content or "").strip(),
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            seconds=round(elapsed, 3),
        )

        for tc in (msg.tool_calls or []):
            raw = tc.function.arguments
            try:
                args = json.loads(raw)
                if not isinstance(args, dict):
                    raise ValueError("arguments were not a JSON object")
            except (json.JSONDecodeError, ValueError):
                # The model wanted a tool but produced arguments we cannot use. Record it
                # rather than crashing - the agent retries, and the count is a useful
                # reliability statistic.
                response.parse_failed = True
                continue
            response.tool_calls.append(
                ToolCall(name=tc.function.name, arguments=args, raw=raw)
            )

        return response

    # ------------------------------------------------------------------
    def _call_with_retry(self, kwargs: dict):
        """Exponential backoff with jitter on rate limits and transient errors.

        Jitter matters if this ever runs more than one request at a time - without it,
        retries synchronise and hit the limit together.
        """
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                return self.client.chat.completions.create(**kwargs)
            except RateLimitError as e:
                last_error = e
                self.rate_limit_waits += 1
                wait = (2 ** attempt) + random.uniform(0, 1)
                print(f"[groq] rate limited, waiting {wait:.1f}s "
                      f"(attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait)
            except APIError as e:
                # 5xx is worth retrying; a 4xx means the request itself is wrong
                status = getattr(e, "status_code", None)
                if status and status < 500:
                    raise
                last_error = e
                time.sleep(2 ** attempt)

        raise RuntimeError(
            f"Groq failed after {MAX_RETRIES} attempts. Last error: {last_error}"
        )

    # ------------------------------------------------------------------
    def usage_summary(self) -> dict:
        return {
            "provider": self.name,
            "calls": self.total_calls,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "rate_limit_waits": self.rate_limit_waits,
        }
