import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMService:
    provider = "gemini"

    def __init__(self, settings: Any | None = None) -> None:
        self.settings = settings or get_settings()

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        settings = self.settings
        if not settings.llm_api_key.strip():
            logger.info("Gemini API key configured: False")
            return self._development_response(user_prompt)

        model_name = self._normalize_model_name(settings.llm_model)
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{model_name}:generateContent"
        )
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": settings.llm_api_key,
        }
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are the AI Business Intelligence Copilot. "
                            f"{system_prompt}"
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": {"temperature": 0.2},
        }
        timeout_seconds = 25
        logger.info("Gemini API key configured: True")
        logger.info("Gemini model: %s", model_name)

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                provider_response = await client.post(endpoint, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            logger.warning("Gemini request timed out")
            raise RuntimeError("LLM_PROVIDER_ERROR: Gemini request timed out") from exc
        except httpx.HTTPError as exc:
            logger.warning("Gemini request failed: network error")
            raise RuntimeError("LLM_PROVIDER_ERROR: language model request failed") from exc

        if provider_response.status_code >= 400:
            self._log_http_failure(provider_response)
            raise RuntimeError("LLM_PROVIDER_ERROR: Gemini request failed")

        try:
            response_json = provider_response.json()
        except ValueError as exc:
            logger.warning("Gemini response parsing failed")
            raise RuntimeError("LLM_PROVIDER_ERROR: malformed Gemini response") from exc

        response_text = self._extract_response_text(response_json)
        if not response_text:
            logger.warning("Gemini response contained no text")
            raise RuntimeError("LLM_PROVIDER_ERROR: Gemini response contained no text")
        return response_text

    def health(self) -> dict[str, str | bool]:
        settings = self.settings
        return {
            "configured": bool(settings.llm_api_key.strip()),
            "provider": self.provider,
            "model": self._normalize_model_name(settings.llm_model),
        }

    def _development_response(self, user_prompt: str) -> str:
        return (
            "Development mock response: I can help analyze business performance, "
            "summarize documents once indexed, and prepare decision-ready follow-ups. "
            f"You asked: {user_prompt}"
        )

    def _normalize_model_name(self, model_name: str) -> str:
        normalized = model_name.strip()
        if normalized.startswith("google/"):
            normalized = normalized.removeprefix("google/")
        if normalized.startswith("models/"):
            normalized = normalized.removeprefix("models/")
        return normalized or "gemini-2.5-flash"

    def _extract_response_text(self, response_json: dict[str, Any]) -> str:
        prompt_feedback = response_json.get("promptFeedback") or {}
        if prompt_feedback.get("blockReason"):
            logger.warning("Gemini response was blocked")
            raise RuntimeError("LLM_PROVIDER_ERROR: Gemini response was blocked")

        candidates = response_json.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            logger.warning("Gemini response contained no candidates")
            raise RuntimeError("LLM_PROVIDER_ERROR: Gemini response contained no candidates")

        candidate = candidates[0] or {}
        if candidate.get("finishReason") in {"SAFETY", "RECITATION", "PROHIBITED_CONTENT"}:
            logger.warning("Gemini response was blocked")
            raise RuntimeError("LLM_PROVIDER_ERROR: Gemini response was blocked")

        content = candidate.get("content") or {}
        parts = content.get("parts")
        if not isinstance(parts, list) or not parts:
            logger.warning("Gemini response contained no text")
            raise RuntimeError("LLM_PROVIDER_ERROR: Gemini response contained no text")

        text_parts = [part.get("text", "") for part in parts if isinstance(part, dict)]
        return "\n".join(text.strip() for text in text_parts if text.strip()).strip()

    def _log_http_failure(self, provider_response: httpx.Response) -> None:
        status_code = provider_response.status_code
        provider_message = self._sanitized_provider_message(provider_response)
        if provider_message:
            logger.warning("Gemini request failed: HTTP %s - %s", status_code, provider_message)
        else:
            logger.warning("Gemini request failed: HTTP %s", status_code)

    def _sanitized_provider_message(self, provider_response: httpx.Response) -> str:
        try:
            response_json = provider_response.json()
        except ValueError:
            return provider_response.text[:300]

        error = response_json.get("error")
        if isinstance(error, dict):
            message = str(error.get("message", ""))
            status = str(error.get("status", ""))
            return " ".join(part for part in (status, message) if part)[:300]
        return str(response_json)[:300]


llm_service = LLMService()
