import logging

from services.youtube_saas import fetch_video_info

from .models import VideoMetadata

logger = logging.getLogger(__name__)

MAX_DURATION_SECONDS = 3600


async def fetch_metadata(url: str) -> VideoMetadata:
    info = await fetch_video_info(url)
    if info.duration_seconds > MAX_DURATION_SECONDS:
        raise ValueError(
            f"Video duration {info.duration_seconds}s exceeds 60 min limit"
        )
    return VideoMetadata(
        youtube_video_id=info.video_id,
        title=info.title,
        duration_seconds=info.duration_seconds,
    )
