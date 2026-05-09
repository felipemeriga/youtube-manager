"""Storage path helpers and Supabase upload/download/sign wrappers for clips.

All paths are relative to the `clips` bucket. RLS isolation is enforced by
prefixing every key with `{user_id}/`.
"""
import asyncio
import logging
from pathlib import Path

import httpx

from config import settings
from services.supabase_pool import get_async_client

logger = logging.getLogger(__name__)


def job_prefix(user_id: str, job_id: str) -> str:
    return f"{user_id}/{job_id}"


def source_key(user_id: str, job_id: str) -> str:
    return f"{job_prefix(user_id, job_id)}/source.mp4"


def preview_key(user_id: str, job_id: str, candidate_id: str) -> str:
    return f"{job_prefix(user_id, job_id)}/previews/{candidate_id}.mp4"


def preview_poster_key(user_id: str, job_id: str, candidate_id: str) -> str:
    return f"{job_prefix(user_id, job_id)}/previews/{candidate_id}.jpg"


def final_key(user_id: str, job_id: str, candidate_id: str) -> str:
    return f"{job_prefix(user_id, job_id)}/finals/{candidate_id}.mp4"


_UPLOAD_RETRIES = 3
_UPLOAD_TIMEOUT = 120  # seconds — rendered videos can be 20-50 MB


async def upload_file(local_path: Path, storage_key: str, content_type: str = "video/mp4") -> None:
    """Upload a local file to the clips bucket with retry on timeout/502."""
    sb = await get_async_client()
    data = local_path.read_bytes()
    last_exc: Exception | None = None
    for attempt in range(_UPLOAD_RETRIES):
        try:
            # Widen the timeout on the storage session for large video uploads.
            # The Supabase storage client exposes the httpx client as `.session`.
            original_timeout = sb.storage.session.timeout
            sb.storage.session.timeout = httpx.Timeout(_UPLOAD_TIMEOUT)
            try:
                await sb.storage.from_(settings.clips_bucket).upload(
                    storage_key, data, {"contentType": content_type, "upsert": "true"}
                )
            finally:
                sb.storage.session.timeout = original_timeout
            return
        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.ConnectTimeout) as exc:
            last_exc = exc
            logger.warning("Upload timeout (attempt %d/%d): %s", attempt + 1, _UPLOAD_RETRIES, exc)
            await asyncio.sleep(2 ** attempt)
    raise RuntimeError(f"Upload failed after {_UPLOAD_RETRIES} attempts: {last_exc}") from last_exc


async def download_file(storage_key: str, local_path: Path) -> None:
    sb = await get_async_client()
    data = await sb.storage.from_(settings.clips_bucket).download(storage_key)
    local_path.write_bytes(data)


async def signed_url(storage_key: str, ttl_seconds: int = 3600) -> str:
    sb = await get_async_client()
    res = await sb.storage.from_(settings.clips_bucket).create_signed_url(
        storage_key, ttl_seconds
    )
    return res["signedURL"]


async def remove_keys(storage_keys: list[str]) -> None:
    if not storage_keys:
        return
    sb = await get_async_client()
    await sb.storage.from_(settings.clips_bucket).remove(storage_keys)
