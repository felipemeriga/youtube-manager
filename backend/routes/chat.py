from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import create_client

from auth import get_current_user
from config import settings
from services.script_pipeline import handle_script_chat_message
from services.thumbnail_pipeline import handle_chat_message

router = APIRouter()


def get_supabase():
    return create_client(settings.supabase_url, settings.supabase_service_key)


class ChatRequest(BaseModel):
    conversation_id: str
    content: str
    type: str = "text"


@router.post("/api/chat")
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    conv = (
        sb.table("conversations")
        .select("mode")
        .eq("id", request.conversation_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    mode = conv.data.get("mode", "thumbnail") if conv.data else "thumbnail"

    if mode == "script":
        stream = handle_script_chat_message(
            conversation_id=request.conversation_id,
            content=request.content,
            user_id=user_id,
        )
    else:
        stream = handle_chat_message(
            conversation_id=request.conversation_id,
            content=request.content,
            msg_type=request.type,
            user_id=user_id,
        )

    return StreamingResponse(stream, media_type="text/event-stream")
