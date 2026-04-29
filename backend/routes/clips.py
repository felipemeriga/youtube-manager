import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import get_current_user
from config import settings
from services.clips.cleanup import sweep_expired
from services.clips.job_runner import (
    cancel_task, register_task, run_pipeline,
)
from services.clips.metadata import fetch_metadata
from services.clips.sse_broker import broker
from services.clips.storage import signed_url
from services.supabase_pool import get_async_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clips")


class PreflightRequest(BaseModel):
    youtube_url: str


class CreateJobRequest(BaseModel):
    youtube_url: str


@router.post("/jobs/preflight")
async def preflight(req: PreflightRequest, user_id: str = Depends(get_current_user)):
    try:
        metadata = await fetch_metadata(req.youtube_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch metadata: {e}")
    return {
        "youtube_video_id": metadata.youtube_video_id,
        "title": metadata.title,
        "duration_seconds": metadata.duration_seconds,
    }


@router.post("/jobs", status_code=201)
async def create_job(req: CreateJobRequest, user_id: str = Depends(get_current_user)):
    sb = await get_async_client()
    res = await (
        sb.table("clip_jobs")
        .insert({"user_id": user_id, "youtube_url": req.youtube_url, "status": "pending"})
        .execute()
    )
    job = res.data[0]
    tmp_dir = Path(settings.clips_tmp_dir)
    task = asyncio.create_task(run_pipeline(
        job_id=job["id"], user_id=user_id, url=req.youtube_url, tmp_dir=tmp_dir,
    ))
    register_task(job["id"], task)
    return job


@router.get("/jobs")
async def list_jobs(user_id: str = Depends(get_current_user)):
    sb = await get_async_client()
    res = await (
        sb.table("clip_jobs")
        .select("id, youtube_url, title, duration_seconds, status, progress_pct, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, user_id: str = Depends(get_current_user)):
    sb = await get_async_client()
    job_res = await (
        sb.table("clip_jobs").select("*").eq("id", job_id).eq("user_id", user_id).single().execute()
    )
    if not job_res.data:
        raise HTTPException(status_code=404, detail="Job not found")
    cand_res = await (
        sb.table("clip_candidates")
        .select("*")
        .eq("job_id", job_id)
        .order("hype_score", desc=True)
        .execute()
    )
    return {**job_res.data, "candidates": cand_res.data}
