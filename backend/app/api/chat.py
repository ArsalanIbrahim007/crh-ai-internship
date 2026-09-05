from fastapi import APIRouter

from app.agents.supervisor import supervisor
from app.schemas.contracts import ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await supervisor.handle_chat(request)
