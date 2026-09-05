from fastapi.testclient import TestClient

from app.agents import supervisor as supervisor_module
from app.main import app


client = TestClient(app)


def test_chat_api_returns_contract(monkeypatch) -> None:
    async def fake_complete(system_prompt: str, user_prompt: str) -> str:
        return "Mocked analytics answer"

    monkeypatch.setattr(supervisor_module.llm_service, "complete", fake_complete)

    response = client.post("/api/chat", json={"query_text": "Show sales for last month"})

    assert response.status_code == 200
    data = response.json()
    assert data["request_id"].startswith("req_")
    assert data["conversation_id"].startswith("conv_")
    assert data["message_id"].startswith("msg_")
    assert isinstance(data["answer"], str)
    assert data["intent"] == "analytics"


def test_chat_preserves_conversation_id(monkeypatch) -> None:
    async def fake_complete(system_prompt: str, user_prompt: str) -> str:
        return "Mocked general answer"

    monkeypatch.setattr(supervisor_module.llm_service, "complete", fake_complete)

    first = client.post("/api/chat", json={"query_text": "Hello"}).json()
    second = client.post(
        "/api/chat",
        json={
            "conversation_id": first["conversation_id"],
            "query_text": "What next?",
        },
    ).json()

    assert second["conversation_id"] == first["conversation_id"]


def test_document_intent_routes_to_document_search() -> None:
    response = client.post(
        "/api/chat",
        json={"query_text": "What does the company policy document say?"},
    )

    assert response.json()["intent"] == "document_search"


def test_general_chat_uses_mocked_llm(monkeypatch) -> None:
    async def fake_complete(system_prompt: str, user_prompt: str) -> str:
        return "I can help you analyze business information and answer questions."

    monkeypatch.setattr(supervisor_module.llm_service, "complete", fake_complete)

    response = client.post(
        "/api/chat",
        json={
            "conversation_id": None,
            "query_text": "Hello, what can you help me with?",
            "attachment_ids": [],
            "voice_mode": False,
        },
    )

    data = response.json()
    assert response.status_code == 200
    assert data["intent"] == "general_chat"
    assert data["answer"] == "I can help you analyze business information and answer questions."
    assert data["error"] is None
    assert data["requires_approval"] is False
    assert data["kpis"] == []
    assert data["sources"] == []
