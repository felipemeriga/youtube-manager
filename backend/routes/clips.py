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


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request, user_id: str = Depends(get_current_user)):
    sb = await get_async_client()
    job_res = await (
        sb.table("clip_jobs").select("id").eq("id", job_id).eq("user_id", user_id).single().execute()
    )
    if not job_res.data:
        raise HTTPException(status_code=404, detail="Job not found")

    queue = broker.subscribe(job_id)

    async def event_stream():
        import json
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("type") in ("ready", "error", "render_complete_all"):
                        break
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"  # SSE comment line keeps connection alive
        finally:
            broker.unsubscribe(job_id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


class RenderRequest(BaseModel):
    candidate_ids: list[str]


@router.post("/jobs/{job_id}/render", status_code=202)
async def render_finals(
    job_id: str,
    req: RenderRequest,
    user_id: str = Depends(get_current_user),
):
    sb = await get_async_client()
    job_res = await (
        sb.table("clip_jobs").select("*").eq("id", job_id).eq("user_id", user_id).single().execute()
    )
    if not job_res.data:
        raise HTTPException(status_code=404, detail="Job not found")
    if job_res.data["status"] not in ("ready", "completed"):
        raise HTTPException(status_code=400, detail=f"Cannot render — job status is {job_res.data['status']}")

    await (
        sb.table("clip_candidates")
        .update({"selected": True})
        .in_("id", req.candidate_ids)
        .execute()
    )
    await (
        sb.table("clip_jobs")
        .update({"status": "rendering", "current_stage": "final_render", "progress_pct": 0})
        .eq("id", job_id)
        .execute()
    )

    from services.clips.job_runner import run_finals_pipeline
    tmp_dir = Path(settings.clips_tmp_dir)
    task = asyncio.create_task(run_finals_pipeline(
        job_id=job_id, user_id=user_id, candidate_ids=req.candidate_ids, tmp_dir=tmp_dir,
    ))
    register_task(job_id, task)
    return {"status": "rendering", "candidate_ids": req.candidate_ids}


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, user_id: str = Depends(get_current_user)):
    sb = await get_async_client()
    job_res = await (
        sb.table("clip_jobs").select("id, status").eq("id", job_id).eq("user_id", user_id).single().execute()
    )
    if not job_res.data:
        raise HTTPException(status_code=404, detail="Job not found")
    cancel_task(job_id)
    await (
        sb.table("clip_jobs")
        .update({"status": "failed", "error_message": "Cancelled by user"})
        .eq("id", job_id)
        .execute()
    )
    return {"status": "cancelled"}


@router.get("/candidates/{candidate_id}/preview-url")
async def get_preview_url(candidate_id: str, user_id: str = Depends(get_current_user)):
    sb = await get_async_client()
    # RLS will ensure the candidate belongs to a job owned by user_id
    res = await (
        sb.table("clip_candidates")
        .select("id, preview_storage_key, job_id")
        .eq("id", candidate_id)
        .single()
        .execute()
    )
    if not res.data or not res.data.get("preview_storage_key"):
        raise HTTPException(status_code=404, detail="Preview not available")
    url = await signed_url(res.data["preview_storage_key"], ttl_seconds=3600)
    return {"url": url}


@router.get("/candidates/{candidate_id}/final-url")
async def get_final_url(candidate_id: str, user_id: str = Depends(get_current_user)):
    sb = await get_async_client()
    res = await (
        sb.table("clip_candidates")
        .select("id, final_storage_key")
        .eq("id", candidate_id)
        .single()
        .execute()
    )
    if not res.data or not res.data.get("final_storage_key"):
        raise HTTPException(status_code=404, detail="Final not rendered")
    url = await signed_url(res.data["final_storage_key"], ttl_seconds=3600)
    return {"url": url}


@router.post("/cleanup")
async def cleanup_endpoint(x_service_token: str = Header(default="")):
    if not settings.clips_cleanup_token or x_service_token != settings.clips_cleanup_token:
        raise HTTPException(status_code=401, detail="Invalid service token")
    return await sweep_expired()
