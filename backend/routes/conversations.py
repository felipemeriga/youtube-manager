from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client

from auth import get_current_user
from config import settings

router = APIRouter()


def get_supabase():
    return create_client(settings.supabase_url, settings.supabase_service_key)


@router.get("/api/conversations")
async def list_conversations(user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("conversations").select("*").eq("user_id", user_id).order("updated_at", desc=True).execute()
    return result.data


@router.post("/api/conversations")
async def create_conversation(user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("conversations").insert({"user_id": user_id}).execute()
    return result.data[0]


@router.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    conv = sb.table("conversations").select("*").eq("id", conversation_id).eq("user_id", user_id).single().execute()
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = sb.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at").execute()
    return {**conv.data, "messages": messages.data}


@router.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    result = sb.table("conversations").delete().eq("id", conversation_id).eq("user_id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}
