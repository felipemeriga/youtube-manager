"""TTL retention sweep.

Triggered by an external scheduler hitting POST /api/clips/cleanup with the
service token. Removes source MP4s and unselected preview files for any job
past expires_at, deletes orphan candidate rows, and marks the job 'expired'.
Final renders are NEVER auto-deleted.
"""
import logging

from services.supabase_pool import get_async_client

from .storage import remove_keys

logger = logging.getLogger(__name__)


async def sweep_expired() -> dict:
    sb = await get_async_client()
    expired = await (
        sb.table("clip_jobs")
        .select("id, user_id, source_storage_key")
        .lt("expires_at", "now()")
        .neq("status", "expired")
        .execute()
    )
    expired_jobs = expired.data or []
    if not expired_jobs:
        return {"jobs_expired": 0, "files_removed": 0}

    job_ids = [j["id"] for j in expired_jobs]
    cands = await (
        sb.table("clip_candidates")
        .select("id, preview_storage_key, preview_poster_key, final_storage_key")
        .in_("job_id", job_ids)
        .execute()
    )
    keys_to_remove: list[str] = []
    for j in expired_jobs:
        if j.get("source_storage_key"):
            keys_to_remove.append(j["source_storage_key"])
    for c in cands.data or []:
        if c.get("preview_storage_key"):
            keys_to_remove.append(c["preview_storage_key"])
        if c.get("preview_poster_key"):
            keys_to_remove.append(c["preview_poster_key"])

    await remove_keys(keys_to_remove)

    # Delete orphan candidate rows (no final render)
    await (
        sb.table("clip_candidates")
        .delete()
        .in_("job_id", job_ids)
        .is_("final_storage_key", "null")
        .execute()
    )

    await (
        sb.table("clip_jobs")
        .update({"status": "expired", "source_storage_key": None})
        .in_("id", job_ids)
        .execute()
    )

    return {"jobs_expired": len(expired_jobs), "files_removed": len(keys_to_remove)}
