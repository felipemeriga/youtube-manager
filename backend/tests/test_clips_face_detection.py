from unittest.mock import AsyncMock, patch

import pytest

from services.clips.face_detection import smooth_x_track, fallback_center


def test_smooth_x_track_simple_average():
    raw = [(0.0, 100), (1.0, 110), (2.0, 105)]
    smoothed = smooth_x_track(raw, window=3)
    assert len(smoothed) == 3
    assert smoothed[1][1] == round((100 + 110 + 105) / 3)


def test_smooth_x_track_handles_empty():
    assert smooth_x_track([], window=3) == []


def test_fallback_center():
    assert fallback_center(video_width=1920, sample_times=[0.0, 1.0, 2.0]) == [
        (0.0, 960),
        (1.0, 960),
        (2.0, 960),
    ]


@pytest.mark.asyncio
async def test_video_dimensions_uses_async_subprocess():
    """ffprobe must run via asyncio.create_subprocess_exec, not blocking subprocess."""
    from pathlib import Path

    from services.clips import face_detection

    fake_proc = AsyncMock()
    fake_proc.communicate = AsyncMock(return_value=(b"1920x1080\n", b""))
    fake_proc.returncode = 0

    with patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_proc)
    ) as spawn:
        result = await face_detection._video_dimensions(Path("/tmp/fake.mp4"))

    assert spawn.called, "should dispatch via asyncio.create_subprocess_exec"
    assert result == (1920, 1080)
