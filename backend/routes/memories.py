from fastapi import APIRouter, Depends, Response

from auth import get_current_user
from services.supabase_pool import get_sync_client

router = APIRouter()


@router.get("/api/memories")
async def list_memories(user_id: str = Depends(get_current_user)):
    sb = get_sync_client()
    result = (
        sb.table("user_memories")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.delete("/api/memories/{memory_id}", status_code=204)
async def delete_memory(memory_id: str, user_id: str = Depends(get_current_user)):
    sb = get_sync_client()
    sb.table("user_memories").delete().eq("id", memory_id).eq(
        "user_id", user_id
    ).execute()
    return Response(status_code=204)
