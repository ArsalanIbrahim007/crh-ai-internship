from app.services.rag_service import RetrievedChunk, RAGService


def test_retrieved_chunk_fields() -> None:
    chunk = RetrievedChunk(source_id="s1", title="Policy", text="Leave policy", score=0.9)

    assert chunk.source_id == "s1"
    assert chunk.title == "Policy"
    assert chunk.text == "Leave policy"
    assert chunk.score == 0.9


async def test_empty_rag_answer() -> None:
    service = RAGService()
    answer, chunks = await service.answer("What does the policy say?")

    assert answer == "No grounded company source matched the question."
    assert chunks == []
