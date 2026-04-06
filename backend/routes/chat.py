from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import get_current_user
from services.thumbnail_pipeline import handle_chat_message

router = APIRouter()


class ChatRequest(BaseModel):
    conversation_id: str
    content: str
    type: str = "text"


@router.post("/api/chat")
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user)):
    return StreamingResponse(
        handle_chat_message(
            conversation_id=request.conversation_id,
            content=request.content,
            msg_type=request.type,
            user_id=user_id,
        ),
        media_type="text/event-stream",
    )
