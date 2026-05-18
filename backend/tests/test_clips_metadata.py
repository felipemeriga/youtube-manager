from unittest.mock import AsyncMock, patch

import pytest

from services.clips.metadata import MAX_DURATION_SECONDS, fetch_metadata
from services.youtube_saas import VideoInfo


def _info(duration: int = 300) -> VideoInfo:
    return VideoInfo(
        video_id="abc123",
        title="Test",
        duration_seconds=duration,
        video_url="https://example.test/v.mp4",
        audio_url="https://example.test/a.m4a",
        caption_url=None,
        caption_lang=None,
    )


@pytest.mark.asyncio
async def test_fetch_metadata_returns_saas_info():
    with patch(
        "services.clips.metadata.fetch_video_info",
        new=AsyncMock(return_value=_info(duration=300)),
    ):
        m = await fetch_metadata("https://youtu.be/abc123")
    assert m.youtube_video_id == "abc123"
    assert m.title == "Test"
    assert m.duration_seconds == 300


@pytest.mark.asyncio
async def test_fetch_metadata_rejects_over_60_min():
    with patch(
        "services.clips.metadata.fetch_video_info",
        new=AsyncMock(return_value=_info(duration=3601)),
    ):
        with pytest.raises(ValueError, match="exceeds 60 min"):
            await fetch_metadata("https://youtu.be/abc")


@pytest.mark.asyncio
async def test_fetch_metadata_invalid_url_propagates():
    with patch(
        "services.clips.metadata.fetch_video_info",
        new=AsyncMock(side_effect=RuntimeError("api down")),
    ):
        with pytest.raises(RuntimeError):
            await fetch_metadata("https://bad")


def test_max_duration_constant():
    assert MAX_DURATION_SECONDS == 3600
