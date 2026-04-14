import asyncio
import logging
import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from supabase import create_client
from supabase._async.client import create_client as create_async_client

from auth import get_current_user
from config import settings


def sanitize_filename(name: str) -> str:
    """Normalize unicode and strip characters that Supabase Storage rejects."""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w.\-]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "file"


logger = logging.getLogger(__name__)

router = APIRouter()

VALID_BUCKETS = {
    "reference-thumbs",
    "personal-photos",
    "logos",
    "outputs",
    "scripts",
    "fonts",
}
MAX_FILE_SIZES = {
    "reference-thumbs": 10 * 1024 * 1024,
    "personal-photos": 10 * 1024 * 1024,
    "logos": 5 * 1024 * 1024,
    "outputs": 10 * 1024 * 1024,
    "scripts": 5 * 1024 * 1024,
    "fonts": 5 * 1024 * 1024,
}


def get_supabase():
    return create_client(settings.supabase_url, settings.supabase_service_key)


def validate_bucket(bucket: str):
    if bucket not in VALID_BUCKETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid bucket: {bucket}. Must be one of {VALID_BUCKETS}",
        )


@router.get("/api/assets/{bucket}")
async def list_assets(bucket: str, user_id: str = Depends(get_current_user)):
    validate_bucket(bucket)
    sb = get_supabase()
    files = sb.storage.from_(bucket).list(path=user_id)
    for f in files:
        f["public_url"] = sb.storage.from_(bucket).get_public_url(
            f"{user_id}/{f['name']}"
        )
    return files


@router.post("/api/assets/{bucket}/upload")
async def upload_asset(
    bucket: str, file: UploadFile = File(...), user_id: str = Depends(get_current_user)
):
    validate_bucket(bucket)
    content = await file.read()
    max_size = MAX_FILE_SIZES[bucket]
    if len(content) > max_size:
        raise HTTPException(
            status_code=400, detail=f"File too large. Max {max_size // (1024 * 1024)}MB"
        )

    import uuid

    sb = get_supabase()
    safe_name = sanitize_filename(file.filename or "file")
    # Add unique prefix to avoid 409 Duplicate on re-uploads
    name_parts = safe_name.rsplit(".", 1)
    if len(name_parts) == 2:
        unique_name = f"{name_parts[0]}_{uuid.uuid4().hex[:6]}.{name_parts[1]}"
    else:
        unique_name = f"{safe_name}_{uuid.uuid4().hex[:6]}"
    storage_path = f"{user_id}/{unique_name}"
    sb.storage.from_(bucket).upload(
        storage_path, content, {"content-type": file.content_type}
    )

    if (
        bucket == "personal-photos"
        and settings.anthropic_api_key
        and settings.voyage_api_key
    ):
        asyncio.create_task(_index_uploaded_photo(user_id, unique_name, content))

    return {"name": unique_name, "bucket": bucket, "path": storage_path}


async def _index_uploaded_photo(
    user_id: str, filename: str, image_bytes: bytes
) -> None:
    from services.photo_indexer import index_photo

    sb = await create_async_client(settings.supabase_url, settings.supabase_service_key)
    await index_photo(sb, user_id, filename, image_bytes)


@router.post("/api/assets/personal-photos/reindex")
async def reindex_photos(user_id: str = Depends(get_current_user)):
    """Index all existing personal photos with descriptions + embeddings."""
    if not settings.anthropic_api_key or not settings.voyage_api_key:
        raise HTTPException(
            status_code=400,
            detail="Anthropic and Voyage API keys required for indexing",
        )

    sb_sync = get_supabase()
    files = sb_sync.storage.from_("personal-photos").list(path=user_id)
    photo_names = [f["name"] for f in files if f.get("name")]

    if not photo_names:
        return {"indexed": 0, "total": 0}

    sb_async = await create_async_client(
        settings.supabase_url, settings.supabase_service_key
    )

    # Check which are already indexed
    existing = (
        await sb_async.table("photo_embeddings")
        .select("file_name")
        .eq("user_id", user_id)
        .execute()
    )
    indexed_names = {row["file_name"] for row in (existing.data or [])}
    to_index = [n for n in photo_names if n not in indexed_names]

    from services.photo_indexer import index_photo

    indexed = 0
    for name in to_index:
        try:
            data = await sb_async.storage.from_("personal-photos").download(
                f"{user_id}/{name}"
            )
            await index_photo(sb_async, user_id, name, data)
            indexed += 1
        except Exception:
            logger.exception("failed to index %s", name)

    return {
        "indexed": indexed,
        "total": len(photo_names),
        "skipped": len(indexed_names),
    }


@router.delete("/api/assets/{bucket}/{filename}")
async def delete_asset(
    bucket: str, filename: str, user_id: str = Depends(get_current_user)
):
    validate_bucket(bucket)
    sb = get_supabase()
    storage_path = f"{user_id}/{filename}"
    sb.storage.from_(bucket).remove([storage_path])
    return {"status": "deleted", "name": filename}


@router.get("/api/assets/{bucket}/signed/{filename}")
async def get_signed_url(
    bucket: str, filename: str, user_id: str = Depends(get_current_user)
):
    """Get a temporary signed URL for an asset (valid 1 hour)."""
    validate_bucket(bucket)
    sb = get_supabase()
    storage_path = f"{user_id}/{filename}"
    result = sb.storage.from_(bucket).create_signed_url(storage_path, 3600)
    if result and result.get("signedURL"):
        return {"signed_url": result["signedURL"]}
    raise HTTPException(status_code=404, detail="File not found")


@router.post("/api/assets/batch-signed-urls")
async def get_batch_signed_urls(
    request: dict, user_id: str = Depends(get_current_user)
):
    """Get signed URLs for multiple files at once.

    Body: {"bucket": "outputs", "filenames": ["file1.png", "file2.png"]}
    """
    bucket = request.get("bucket", "")
    filenames = request.get("filenames", [])
    validate_bucket(bucket)
    sb = get_supabase()
    paths = [f"{user_id}/{f}" for f in filenames]
    result = sb.storage.from_(bucket).create_signed_urls(paths, 3600)
    return result


@router.post("/api/assets/batch-thumbnails")
async def get_batch_thumbnails(request: dict, user_id: str = Depends(get_current_user)):
    """Download, resize and return multiple images as base64 in a single request.

    Body: {"bucket": "personal-photos", "filenames": ["a.jpg", "b.jpg"], "w": 200}
    Returns: {"a.jpg": "data:image/jpeg;base64,...", "b.jpg": "..."}
    """
    import base64
    import io

    from PIL import Image

    bucket = request.get("bucket", "")
    filenames = request.get("filenames", [])
    w = request.get("w", 200)
    validate_bucket(bucket)

    sb_async = await create_async_client(
        settings.supabase_url, settings.supabase_service_key
    )

    async def _resize_one(name: str) -> tuple[str, str]:
        try:
            data = await sb_async.storage.from_(bucket).download(f"{user_id}/{name}")
            img = Image.open(io.BytesIO(data))
            img.thumbnail((w, w), Image.LANCZOS)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=70)
            b64 = base64.b64encode(buf.getvalue()).decode()
            return name, f"data:image/jpeg;base64,{b64}"
        except Exception:
            return name, ""

    results = await asyncio.gather(*[_resize_one(n) for n in filenames])
    return {name: data_uri for name, data_uri in results if data_uri}


@router.get("/api/assets/{bucket}/{filename}")
async def download_asset(
    bucket: str,
    filename: str,
    user_id: str = Depends(get_current_user),
    w: int | None = None,
):
    validate_bucket(bucket)
    sb = get_supabase()
    storage_path = f"{user_id}/{filename}"
    data = sb.storage.from_(bucket).download(storage_path)

    # Optional resize: ?w=200 returns a JPEG thumbnail
    if w and 0 < w <= 1024:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(data))
        img.thumbnail((w, w), Image.LANCZOS)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=80)
        data = buf.getvalue()
        from fastapi.responses import Response

        return Response(
            content=data,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    from fastapi.responses import Response

    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
