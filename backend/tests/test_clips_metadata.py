import json
from unittest.mock import AsyncMock, patch

import pytest

from services.clips.metadata import fetch_metadata, MAX_DURATION_SECONDS


@pytest.mark.asyncio
async def test_fetch_metadata_parses_ytdlp_json():
    fake_json = json.dumps({"id": "abc123", "title": "Test", "duration": 300})
    with patch("services.clips.metadata._run_ytdlp_dump", new=AsyncMock(return_value=fake_json)):
        m = await fetch_metadata("https://youtu.be/abc123")
    assert m.youtube_video_id == "abc123"
    assert m.title == "Test"
    assert m.duration_seconds == 300


@pytest.mark.asyncio
async def test_fetch_metadata_rejects_over_60_min():
    fake_json = json.dumps({"id": "abc", "title": "Long", "duration": 3601})
    with patch("services.clips.metadata._run_ytdlp_dump", new=AsyncMock(return_value=fake_json)):
        with pytest.raises(ValueError, match="exceeds 60 min"):
            await fetch_metadata("https://youtu.be/abc")


@pytest.mark.asyncio
async def test_fetch_metadata_invalid_url_propagates():
    with patch("services.clips.metadata._run_ytdlp_dump", new=AsyncMock(side_effect=RuntimeError("yt-dlp failed"))):
        with pytest.raises(RuntimeError):
            await fetch_metadata("https://bad")


def test_max_duration_constant():
    assert MAX_DURATION_SECONDS == 3600
