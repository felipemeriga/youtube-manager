from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import get_current_user
from services.supabase_pool import get_async_client

DEFAULT_MESSAGE_LIMIT = 50


class CreateConversationRequest(BaseModel):
    mode: str = "thumbnail"


class UpdateConversationRequest(BaseModel):
    model: str | None = None


router = APIRouter()


@router.get("/api/conversations")
async def list_conversations(user_id: str = Depends(get_current_user)):
    sb = await get_async_client()
    # Only fetch fields the sidebar list actually renders. Full conversation
    # details (including the message body and model) come from the detail
    # endpoint when a row is selected.
    result = await (
        sb.table("conversations")
        .select("id, title, updated_at, created_at, mode")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return result.data


@router.post("/api/conversations")
async def create_conversation(
    request: Optional[CreateConversationRequest] = None,
    user_id: str = Depends(get_current_user),
):
    sb = await get_async_client()
    mode = request.mode if request else "thumbnail"
    result = await (
        sb.table("conversations").insert({"user_id": user_id, "mode": mode}).execute()
    )
    return result.data[0]


@router.get("/api/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user),
    limit: int = Query(DEFAULT_MESSAGE_LIMIT, ge=1, le=200),
    before: str | None = Query(None),
):
    sb = await get_async_client()
    conv = await (
        sb.table("conversations")
        .select("*")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    query = (
        sb.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if before:
        query = query.lt("created_at", before)
    messages_result = await query.execute()
    # Reverse so messages are in chronological order
    messages = list(reversed(messages_result.data))
    has_more = len(messages_result.data) == limit

    return {**conv.data, "messages": messages, "has_more": has_more}


@router.patch("/api/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    request: UpdateConversationRequest,
    user_id: str = Depends(get_current_user),
):
    sb = await get_async_client()
    updates = {}
    if request.model is not None:
        updates["model"] = request.model
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await (
        sb.table("conversations")
        .update(updates)
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result.data[0]


@router.delete("/api/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str, user_id: str = Depends(get_current_user)
):
    sb = await get_async_client()
    result = await (
        sb.table("conversations")
        .delete()
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}
