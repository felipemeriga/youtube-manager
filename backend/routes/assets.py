from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from supabase import create_client

from auth import get_current_user
from config import settings

router = APIRouter()

VALID_BUCKETS = {"reference-thumbs", "personal-photos", "fonts", "outputs"}
MAX_FILE_SIZES = {
    "reference-thumbs": 10 * 1024 * 1024,
    "personal-photos": 10 * 1024 * 1024,
    "fonts": 5 * 1024 * 1024,
    "outputs": 10 * 1024 * 1024,
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

    sb = get_supabase()
    storage_path = f"{user_id}/{file.filename}"
    sb.storage.from_(bucket).upload(
        storage_path, content, {"content-type": file.content_type}
    )
    return {"name": file.filename, "bucket": bucket, "path": storage_path}


@router.delete("/api/assets/{bucket}/{filename}")
async def delete_asset(
    bucket: str, filename: str, user_id: str = Depends(get_current_user)
):
    validate_bucket(bucket)
    sb = get_supabase()
    storage_path = f"{user_id}/{filename}"
    sb.storage.from_(bucket).remove([storage_path])
    return {"status": "deleted", "name": filename}


@router.get("/api/assets/{bucket}/{filename}")
async def download_asset(
    bucket: str, filename: str, user_id: str = Depends(get_current_user)
):
    validate_bucket(bucket)
    sb = get_supabase()
    storage_path = f"{user_id}/{filename}"
    data = sb.storage.from_(bucket).download(storage_path)
    from fastapi.responses import Response

    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
