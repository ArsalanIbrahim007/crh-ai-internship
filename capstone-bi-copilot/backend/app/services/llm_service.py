from __future__ import annotations

import asyncio

import httpx

from app.core.config import get_settings


class LLMService:
    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        s = get_settings()
        if not s.gemini_api_key:
            return self._offline(user_prompt)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{s.gemini_model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=35) as client:
                    r = await client.post(url, headers={"x-goog-api-key": s.gemini_api_key}, json=payload)
                    r.raise_for_status()
                    data = r.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in (503, 429) and attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                if e.response.status_code in (503, 429):
                    return self._offline(user_prompt)
                raise RuntimeError(f"LLM provider request failed: {type(e).__name__}") from e
            except httpx.RequestError as e:
                last_error = e
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return self._offline(user_prompt)
            except Exception as e:
                raise RuntimeError(f"LLM provider request failed: {type(e).__name__}") from e
        if last_error and (
            (isinstance(last_error, httpx.HTTPStatusError) and last_error.response.status_code in (503, 429))
            or isinstance(last_error, httpx.RequestError)
        ):
            return self._offline(user_prompt)
        raise RuntimeError(f"LLM provider request failed after retries: {type(last_error).__name__}") from last_error

    def _offline(self, prompt: str) -> str:
        return "I can process this request locally where deterministic analytics or document retrieval is available. Configure GEMINI_API_KEY for general generative responses."


llm_service = LLMService()
