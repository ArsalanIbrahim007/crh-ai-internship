from app.schemas.contracts import ChatResponse


def test_chat_response_defaults() -> None:
    response = ChatResponse(
        request_id="r",
        conversation_id="c",
        message_id="m",
        answer="ok",
        intent="analytics",
    )

    assert response.chart_spec.type == "none"
    assert response.kpis == []
    assert response.sources == []
    assert response.tool_calls == []
    assert response.requires_approval is False
    assert response.error is None
