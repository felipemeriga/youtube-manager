import asyncio
import json
import logging

from .models import VideoMetadata

logger = logging.getLogger(__name__)

MAX_DURATION_SECONDS = 3600


async def _run_ytdlp_dump(url: str) -> str:
    """Run `yt-dlp --dump-json --no-download <url>` and return stdout."""
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp", "--dump-json", "--no-download", url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {stderr.decode()[:500]}")
    return stdout.decode()


async def fetch_metadata(url: str) -> VideoMetadata:
    raw = await _run_ytdlp_dump(url)
    data = json.loads(raw)
    duration = int(data.get("duration") or 0)
    if duration > MAX_DURATION_SECONDS:
        raise ValueError(f"Video duration {duration}s exceeds 60 min limit")
    return VideoMetadata(
        youtube_video_id=data["id"],
        title=data.get("title", ""),
        duration_seconds=duration,
    )
