import logging
from pathlib import Path

from services.youtube_saas import download_video_and_audio, fetch_video_info

from .render_preview import _video_dims
from .storage import source_key, upload_file

logger = logging.getLogger(__name__)


async def download_source(
    url: str,
    user_id: str,
    job_id: str,
    tmp_dir: Path,
) -> Path:
    """Download YouTube video via SaaS, mux to MP4, upload to Supabase.

    Returns the local file path of the muxed source MP4.
    """
    tmp_dir.mkdir(parents=True, exist_ok=True)
    local_path = tmp_dir / "source.mp4"
    info = await fetch_video_info(url)
    await download_video_and_audio(info, local_path)
    try:
        width, height = _video_dims(local_path)
        res = f"{width}x{height}"
    except Exception:
        res = "unknown"
    await upload_file(local_path, source_key(user_id, job_id), "video/mp4")
    logger.info(
        "Downloaded source for job %s, size=%d, resolution=%s",
        job_id,
        local_path.stat().st_size,
        res,
    )
    return local_path
