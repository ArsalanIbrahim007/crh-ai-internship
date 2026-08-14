"""Groq chat with automatic model fallback.

Rate limits are per model, not per key, so a single-model client fails the
demo the moment a daily quota trips. The fallback chain is walked on 429 and
on server errors; the model that answered is returned so the UI can show it.
"""
from __future__ import annotations

import time
from functools import lru_cache

from config import DEFAULT_MODEL, FALLBACK_MODELS, GROQ_API_KEY


@lru_cache(maxsize=1)
def client():
    from groq import Groq
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY missing from week3/.env")
    return Groq(api_key=GROQ_API_KEY)


def chat(messages: list[dict], model: str | None = None,
         temperature: float = 0.1, max_tokens: int = 1400,
         json_mode: bool = False) -> dict:
    chain = [model or DEFAULT_MODEL] + [
        m for m in FALLBACK_MODELS if m != (model or DEFAULT_MODEL)
    ]
    errors: list[str] = []

    for candidate in chain:
        for attempt in range(2):
            try:
                t0 = time.perf_counter()
                kwargs = {
                    "model": candidate,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}

                resp = client().chat.completions.create(**kwargs)
                return {
                    "text": resp.choices[0].message.content or "",
                    "model": candidate,
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                    "prompt_tokens": resp.usage.prompt_tokens,
                    "completion_tokens": resp.usage.completion_tokens,
                    "fell_back": candidate != chain[0],
                }
            except Exception as exc:
                msg = str(exc)
                errors.append(f"{candidate}: {msg[:160]}")
                # per-minute limits clear quickly; per-day do not
                if "rate_limit" in msg.lower() and attempt == 0 \
                        and "per day" not in msg.lower():
                    time.sleep(3)
                    continue
                break

    raise RuntimeError("all models failed:\n  " + "\n  ".join(errors))


def available_models() -> list[str]:
    return [DEFAULT_MODEL] + [m for m in FALLBACK_MODELS if m != DEFAULT_MODEL]