from uuid import uuid4

from app.schemas.contracts import ChatRequest, ChatResponse, SourceRef
from app.services.llm_service import llm_service
from app.services.rag_service import rag_service


class Supervisor:
    async def handle_chat(self, request: ChatRequest) -> ChatResponse:
        conversation_id = request.conversation_id or f"conv_{uuid4().hex}"
        request_id = f"req_{uuid4().hex}"
        message_id = f"msg_{uuid4().hex}"
        intent = self._classify_intent(request.query_text)

        try:
            if intent == "document_search":
                answer, chunks = await rag_service.answer(request.query_text)
                sources = [
                    SourceRef(
                        source_id=chunk.source_id,
                        title=chunk.title,
                        snippet=chunk.text[:180],
                    )
                    for chunk in chunks
                ]
            elif intent == "tool_action":
                answer = "Tool actions are not enabled in Phase 1."
                sources = []
            else:
                answer = await llm_service.complete(
                    system_prompt=(
                        "Answer conversational and business questions clearly. "
                        "Do not invent company document facts without retrieved sources."
                    ),
                    user_prompt=request.query_text,
                )
                sources = []
            error = None
        except RuntimeError:
            answer = "I could not complete that request. Please try again."
            sources = []
            error = {"error_code": "LLM_PROVIDER_ERROR", "message": answer}

        return ChatResponse(
            request_id=request_id,
            conversation_id=conversation_id,
            message_id=message_id,
            answer=answer,
            intent=intent,
            sources=sources,
            error=error,
        )

    def _classify_intent(self, query_text: str) -> str:
        normalized = query_text.lower()
        tool_terms = ("schedule", "meeting", "send an email", "email", "calendar")
        document_terms = ("document", "policy", "contract", "file", "pdf", "leave")
        analytics_terms = (
            "sales",
            "revenue",
            "profit",
            "performance",
            "analyze",
            "analysis",
            "compare",
            "kpi",
            "forecast",
            "region",
            "month",
        )
        general_chat_terms = (
            "hello",
            "hi",
            "hey",
            "what can you help",
            "who are you",
            "help me with",
        )
        if any(term in normalized for term in tool_terms):
            return "tool_action"
        if any(term in normalized for term in document_terms):
            return "document_search"
        if any(term in normalized for term in analytics_terms):
            return "analytics"
        if any(term in normalized for term in general_chat_terms):
            return "general_chat"
        return "general_chat"


supervisor = Supervisor()
