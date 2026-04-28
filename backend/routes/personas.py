from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from auth import get_current_user
from services.supabase_pool import get_sync_client

DEFAULT_SCRIPT_SECTIONS = [
    {
        "name": "Hook / Opening",
        "description": "Provocative hook in the first 30 seconds",
        "enabled": True,
        "order": 0,
    },
    {
        "name": "Timing Table",
        "description": "Markdown table with Section, Time, Duration",
        "enabled": True,
        "order": 1,
    },
    {
        "name": "Stats & Data",
        "description": "6-10 verified statistics with real source URLs",
        "enabled": True,
        "order": 2,
    },
    {
        "name": "Talking Points",
        "description": "5-8 punchy one-liner quotes ready to say on camera",
        "enabled": True,
        "order": 3,
    },
    {
        "name": "Full Script",
        "description": "Word-for-word dialogue organized by section with timing",
        "enabled": True,
        "order": 4,
    },
    {
        "name": "Verified Sources",
        "description": "Numbered list of all sources with real URLs",
        "enabled": True,
        "order": 5,
    },
]


class PersonaRequest(BaseModel):
    channel_name: str
    language: str
    persona_text: str
    script_template: Optional[list[dict]] = None


router = APIRouter()


@router.get("/api/personas")
async def get_persona(user_id: str = Depends(get_current_user)):
    sb = get_sync_client()
    result = (
        sb.table("channel_personas")
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Persona not found")
    data = result.data
    if data.get("script_template") is None:
        data["script_template"] = DEFAULT_SCRIPT_SECTIONS
    return data


@router.put("/api/personas")
async def upsert_persona(
    request: PersonaRequest,
    user_id: str = Depends(get_current_user),
):
    sb = get_sync_client()
    payload = {
        "user_id": user_id,
        "channel_name": request.channel_name,
        "language": request.language,
        "persona_text": request.persona_text,
    }
    if request.script_template is not None:
        payload["script_template"] = request.script_template
    result = (
        sb.table("channel_personas").upsert(payload, on_conflict="user_id").execute()
    )
    return result.data[0]


@router.delete("/api/personas", status_code=204)
async def delete_persona(user_id: str = Depends(get_current_user)):
    sb = get_sync_client()
    sb.table("channel_personas").delete().eq("user_id", user_id).execute()
    return Response(status_code=204)
