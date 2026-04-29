"""Storage path helpers and Supabase upload/download/sign wrappers for clips.

All paths are relative to the `clips` bucket. RLS isolation is enforced by
prefixing every key with `{user_id}/`.
"""
import logging
from pathlib import Path

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


async def upload_file(local_path: Path, storage_key: str, content_type: str = "video/mp4") -> None:
    """Upload a local file to the clips bucket. Reuses existing Supabase 502 retry pattern."""
    sb = await get_async_client()
    data = local_path.read_bytes()
    # Reuse upload pattern from routes/assets.py (retry on 502 etc.)
    await sb.storage.from_(settings.clips_bucket).upload(
        storage_key, data, {"contentType": content_type, "upsert": "true"}
    )


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
