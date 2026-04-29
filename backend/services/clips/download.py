import asyncio
import logging
from pathlib import Path

from .storage import source_key, upload_file

logger = logging.getLogger(__name__)


async def _run_ytdlp_download(url: str, out_path: Path) -> None:
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "-f", "bv*[height<=1080]+ba/b",
        "--merge-output-format", "mp4",
        "-o", str(out_path),
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp download failed: {stderr.decode()[:500]}")


async def download_source(
    url: str,
    user_id: str,
    job_id: str,
    tmp_dir: Path,
) -> Path:
    """Download YouTube video and upload to Supabase. Returns local file path."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    local_path = tmp_dir / "source.mp4"
    await _run_ytdlp_download(url, local_path)
    await upload_file(local_path, source_key(user_id, job_id), "video/mp4")
    logger.info("Downloaded source for job %s, size=%d", job_id, local_path.stat().st_size)
    return local_path
