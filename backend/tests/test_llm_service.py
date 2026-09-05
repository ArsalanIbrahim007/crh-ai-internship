from types import SimpleNamespace

import httpx
import pytest

from app.services.llm_service import LLMService


class FakeAsyncClient:
    response: httpx.Response | None = None
    exception: Exception | None = None
    last_request: dict | None = None

    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, endpoint: str, json: dict, headers: dict) -> httpx.Response:
        FakeAsyncClient.last_request = {
            "endpoint": endpoint,
            "json": json,
            "headers": headers,
        }
        if FakeAsyncClient.exception:
            raise FakeAsyncClient.exception
        assert FakeAsyncClient.response is not None
        return FakeAsyncClient.response


def make_service(api_key: str = "test-key", model: str = "gemini-2.5-flash") -> LLMService:
    settings = SimpleNamespace(llm_api_key=api_key, llm_model=model)
    return LLMService(settings=settings)


def response(status_code: int, payload: dict) -> httpx.Response:
    return httpx.Response(status_code=status_code, json=payload)


@pytest.fixture(autouse=True)
def reset_fake_client(monkeypatch):
    FakeAsyncClient.response = None
    FakeAsyncClient.exception = None
    FakeAsyncClient.last_request = None
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)


@pytest.mark.asyncio
async def test_successful_gemini_response() -> None:
    FakeAsyncClient.response = response(
        200,
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Hello! I can help with business analysis."}
                        ]
                    }
                }
            ]
        },
    )

    result = await make_service().complete("system", "Hello")

    assert result == "Hello! I can help with business analysis."
    assert FakeAsyncClient.last_request is not None
    assert FakeAsyncClient.last_request["endpoint"].endswith(
        "/models/gemini-2.5-flash:generateContent"
    )
    assert "x-goog-api-key" in FakeAsyncClient.last_request["headers"]
    assert FakeAsyncClient.last_request["json"]["contents"][0]["parts"][0]["text"] == "Hello"


@pytest.mark.asyncio
async def test_missing_candidates() -> None:
    FakeAsyncClient.response = response(200, {"candidates": []})

    with pytest.raises(RuntimeError, match="no candidates"):
        await make_service().complete("system", "Hello")


@pytest.mark.asyncio
async def test_empty_parts() -> None:
    FakeAsyncClient.response = response(200, {"candidates": [{"content": {"parts": []}}]})

    with pytest.raises(RuntimeError, match="no text"):
        await make_service().complete("system", "Hello")


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 429, 500])
async def test_http_failures(status_code: int) -> None:
    FakeAsyncClient.response = response(
        status_code,
        {"error": {"status": "INVALID_ARGUMENT", "message": "Sanitized provider message"}},
    )

    with pytest.raises(RuntimeError, match="Gemini request failed"):
        await make_service().complete("system", "Hello")


@pytest.mark.asyncio
async def test_timeout() -> None:
    FakeAsyncClient.exception = httpx.TimeoutException("timeout")

    with pytest.raises(RuntimeError, match="timed out"):
        await make_service().complete("system", "Hello")


@pytest.mark.asyncio
async def test_malformed_provider_response() -> None:
    FakeAsyncClient.response = httpx.Response(200, content=b"not-json")

    with pytest.raises(RuntimeError, match="malformed Gemini response"):
        await make_service().complete("system", "Hello")


@pytest.mark.asyncio
async def test_api_key_missing_uses_development_response() -> None:
    result = await make_service(api_key="").complete("system", "Hello")

    assert result.startswith("Development mock response:")
    assert FakeAsyncClient.last_request is None
