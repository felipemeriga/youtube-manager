from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from supabase import create_client

from auth import get_current_user
from config import settings


class PersonaRequest(BaseModel):
    channel_name: str
    language: str
    persona_text: str


router = APIRouter()


def get_supabase():
    return create_client(settings.supabase_url, settings.supabase_service_key)


@router.get("/api/personas")
async def get_persona(user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    result = (
        sb.table("channel_personas")
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Persona not found")
    return result.data


@router.put("/api/personas")
async def upsert_persona(
    request: PersonaRequest,
    user_id: str = Depends(get_current_user),
):
    sb = get_supabase()
    result = (
        sb.table("channel_personas")
        .upsert(
            {
                "user_id": user_id,
                "channel_name": request.channel_name,
                "language": request.language,
                "persona_text": request.persona_text,
            },
            on_conflict="user_id",
        )
        .execute()
    )
    return result.data[0]


@router.delete("/api/personas", status_code=204)
async def delete_persona(user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    sb.table("channel_personas").delete().eq("user_id", user_id).execute()
    return Response(status_code=204)
