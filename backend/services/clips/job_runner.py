"""Pipeline orchestration: run_pipeline runs all stages in sequence, updates
clip_jobs row, publishes SSE events, and inserts clip_candidates rows.

Maintains a registry of in-flight asyncio tasks for cancellation.
"""
import asyncio
import logging
import shutil
import uuid
from pathlib import Path

from config import settings
from services.supabase_pool import get_async_client

from .download import download_source
from .metadata import fetch_metadata
from .render_preview import render_all_previews
from .segment import segment_and_score
from .sse_broker import broker
from .transcript import fetch_transcript

logger = logging.getLogger(__name__)


_active_tasks: dict[str, asyncio.Task] = {}


def register_task(job_id: str, task: asyncio.Task) -> None:
    _active_tasks[job_id] = task


def get_task(job_id: str) -> asyncio.Task | None:
    task = _active_tasks.get(job_id)
    if task and task.done():
        _active_tasks.pop(job_id, None)
        return None
    return task


def cancel_task(job_id: str) -> bool:
    task = _active_tasks.pop(job_id, None)
    if task is None:
        return False
    task.cancel()
    return True


async def _update_job(job_id: str, fields: dict) -> None:
    sb = await get_async_client()
    await sb.table("clip_jobs").update(fields).eq("id", job_id).execute()


async def _publish_progress(job_id: str, stage: str, pct: int) -> None:
    await broker.publish(job_id, {"type": "progress", "stage": stage, "pct": pct})


async def run_pipeline(
    job_id: str,
    user_id: str,
    url: str,
    tmp_dir: Path,
) -> None:
    sb = await get_async_client()
    job_tmp = tmp_dir / job_id
    job_tmp.mkdir(parents=True, exist_ok=True)

    try:
        await _update_job(job_id, {"status": "processing", "current_stage": "metadata", "progress_pct": 1})
        await _publish_progress(job_id, "metadata", 1)
        metadata = await fetch_metadata(url)
        await _update_job(job_id, {
            "title": metadata.title,
            "duration_seconds": metadata.duration_seconds,
            "youtube_video_id": metadata.youtube_video_id,
            "current_stage": "download",
            "progress_pct": 5,
        })
        await _publish_progress(job_id, "download", 5)

        source = await download_source(url=url, user_id=user_id, job_id=job_id, tmp_dir=job_tmp)
        await _update_job(job_id, {"current_stage": "transcribe", "progress_pct": 25,
                                    "source_storage_key": f"{user_id}/{job_id}/source.mp4"})
        await _publish_progress(job_id, "transcribe", 25)

        # Extract audio for whisper fallback
        audio_path = job_tmp / "audio.mp3"
        audio_proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(source), "-vn", "-acodec", "libmp3lame", "-q:a", "5",
            str(audio_path),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await audio_proc.wait()

        cues = await fetch_transcript(url, audio_path, job_tmp)
        await _update_job(job_id, {"current_stage": "segment", "progress_pct": 45})
        await _publish_progress(job_id, "segment", 45)

        candidates = await segment_and_score(cues, duration_seconds=metadata.duration_seconds)
        await _update_job(job_id, {"current_stage": "preview_render", "progress_pct": 55})
        await _publish_progress(job_id, "preview_render", 55)

        # Pre-create candidate rows so we have IDs before render
        candidate_ids: list[tuple[str, object]] = []
        for c in candidates:
            cid = str(uuid.uuid4())
            await sb.table("clip_candidates").insert({
                "id": cid,
                "job_id": job_id,
                "start_seconds": c.start_seconds,
                "end_seconds": c.end_seconds,
                "duration_seconds": c.duration_seconds,
                "hype_score": c.hype_score,
                "hype_reasoning": c.hype_reasoning,
                "transcript_excerpt": c.transcript_excerpt,
            }).execute()
            candidate_ids.append((cid, c))

        total = len(candidate_ids)

        def on_progress(done: int, total_: int):
            pct = 55 + int(40 * (done / total_)) if total_ else 95
            asyncio.create_task(_publish_progress(job_id, "preview_render", pct))

        results = await render_all_previews(
            candidates=candidate_ids,
            source=source,
            user_id=user_id,
            job_id=job_id,
            tmp_dir=job_tmp,
            on_progress=on_progress,
        )

        succeeded = [r for r in results if not r.get("render_failed")]
        if total > 0 and len(succeeded) / total < 0.5:
            raise RuntimeError(f"Too many candidate renders failed ({len(succeeded)}/{total})")

        for r in results:
            updates = {"render_failed": r.get("render_failed", False)}
            if not r.get("render_failed"):
                updates["preview_storage_key"] = r["preview_storage_key"]
                updates["preview_poster_key"] = r["preview_poster_key"]
            await sb.table("clip_candidates").update(updates).eq("id", r["candidate_id"]).execute()

        await _update_job(job_id, {
            "status": "ready",
            "current_stage": "await_selection",
            "progress_pct": 100,
        })
        # Fetch final candidate list for SSE payload
        cand_res = await (
            sb.table("clip_candidates").select("*").eq("job_id", job_id).order("hype_score", desc=True).execute()
        )
        await broker.publish(job_id, {"type": "ready", "candidates": cand_res.data})

    except asyncio.CancelledError:
        await _update_job(job_id, {"status": "failed", "error_message": "Cancelled by user"})
        await broker.publish(job_id, {"type": "error", "message": "Cancelled by user"})
        raise
    except Exception as e:
        logger.exception("Pipeline failed for job %s", job_id)
        await _update_job(job_id, {"status": "failed", "error_message": str(e)[:500]})
        await broker.publish(job_id, {"type": "error", "message": str(e)})
    finally:
        _active_tasks.pop(job_id, None)
        if job_tmp.exists():
            shutil.rmtree(job_tmp, ignore_errors=True)


async def recover_orphans() -> int:
    """On app startup, mark any processing/rendering rows as failed."""
    sb = await get_async_client()
    res = await (
        sb.table("clip_jobs")
        .update({"status": "failed", "error_message": "Server restart"})
        .in_("status", ["processing", "rendering"])
        .execute()
    )
    return len(res.data or [])
