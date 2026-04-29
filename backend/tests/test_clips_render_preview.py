from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from services.clips.models import CandidateClip
from services.clips.render_preview import (
    build_crop_filter, render_one_preview,
)


def test_build_crop_filter_centered():
    track = [(0.0, 960), (1.0, 960), (2.0, 960)]
    f = build_crop_filter(track=track, video_height=1080, video_width=1920)
    # 9:16 of height 1080 → width 607.5 → 608. center x = 960 - 304 = 656
    assert "crop=608:1080:656:0" in f
    assert "scale=720:1280" in f


def test_build_crop_filter_clamps_left():
    track = [(0.0, 50)]
    f = build_crop_filter(track=track, video_height=1080, video_width=1920)
    assert "crop=608:1080:0:0" in f


def test_build_crop_filter_clamps_right():
    track = [(0.0, 1900)]
    f = build_crop_filter(track=track, video_height=1080, video_width=1920)
    # max x_offset = 1920 - 608 = 1312
    assert "crop=608:1080:1312:0" in f


@pytest.mark.asyncio
async def test_render_one_preview_orchestrates(tmp_path):
    candidate = CandidateClip(
        start_seconds=10, end_seconds=40, hype_score=8,
        hype_reasoning="x", transcript_excerpt="y",
    )
    source = tmp_path / "source.mp4"
    source.write_bytes(b"")

    with patch("services.clips.render_preview._ffmpeg_cut", new=AsyncMock()) as cut, \
         patch("services.clips.render_preview.detect_face_track", return_value=[(0.0, 960)]) as det, \
         patch("services.clips.render_preview._video_dims", return_value=(1920, 1080)), \
         patch("services.clips.render_preview._ffmpeg_reframe", new=AsyncMock()) as reframe, \
         patch("services.clips.render_preview._ffmpeg_poster", new=AsyncMock()) as poster, \
         patch("services.clips.render_preview.upload_file", new=AsyncMock()) as upload:
        result = await render_one_preview(
            candidate=candidate, candidate_id="c1", source=source,
            user_id="u1", job_id="j1", tmp_dir=tmp_path,
        )

    assert cut.await_count == 1
    assert reframe.await_count == 1
    assert poster.await_count == 1
    assert upload.await_count == 2  # mp4 + jpg
    assert result["preview_storage_key"] == "u1/j1/previews/c1.mp4"
    assert result["preview_poster_key"] == "u1/j1/previews/c1.jpg"
