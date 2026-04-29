from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from services.clips.models import CandidateClip, TranscriptCue
from services.clips.render_final import build_ass_file, render_one_final


def test_build_ass_file_writes_overlapping_cues(tmp_path):
    cues = [
        TranscriptCue(start=0, end=2, text="before clip"),
        TranscriptCue(start=10, end=12, text="hello"),
        TranscriptCue(start=12, end=14, text="world"),
        TranscriptCue(start=50, end=52, text="after clip"),
    ]
    out = tmp_path / "clip.ass"
    build_ass_file(cues, clip_start=10, clip_end=20, out_path=out)
    body = out.read_text()
    assert "hello" in body
    assert "world" in body
    assert "before clip" not in body
    assert "after clip" not in body
    # Times should be normalized to clip start (subtract 10s)
    assert "0:00:00.00" in body  # "hello" starts at 0 in clip-local time


@pytest.mark.asyncio
async def test_render_one_final_orchestrates(tmp_path):
    candidate = CandidateClip(
        start_seconds=10, end_seconds=40, hype_score=8,
        hype_reasoning="x", transcript_excerpt="y",
    )
    cues = [TranscriptCue(start=10, end=12, text="hi")]
    source = tmp_path / "source.mp4"
    source.write_bytes(b"")

    with patch("services.clips.render_final._ffmpeg_render_with_subs", new=AsyncMock()) as render, \
         patch("services.clips.render_final.detect_face_track", return_value=[(0.0, 960)]), \
         patch("services.clips.render_final._video_dims", return_value=(1920, 1080)), \
         patch("services.clips.render_final.upload_file", new=AsyncMock()) as upload:
        key = await render_one_final(
            candidate=candidate, candidate_id="c1", source=source,
            cues=cues, user_id="u1", job_id="j1", tmp_dir=tmp_path,
        )
    assert render.await_count == 1
    assert upload.await_count == 1
    assert key == "u1/j1/finals/c1.mp4"
