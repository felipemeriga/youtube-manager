from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.clips.job_runner import (
    run_pipeline, register_task, get_task, cancel_task, recover_orphans,
)
from services.clips.models import CandidateClip, TranscriptCue, VideoMetadata


@pytest.mark.asyncio
async def test_register_get_cancel():
    import asyncio
    async def long_running():
        await asyncio.sleep(10)
    task = asyncio.create_task(long_running())
    register_task("j1", task)
    assert get_task("j1") is task
    assert cancel_task("j1") is True
    assert get_task("j1") is None
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_run_pipeline_happy_path(tmp_path):
    job_id = "job-x"
    user_id = "user-x"
    url = "https://youtu.be/x"

    metadata = VideoMetadata(youtube_video_id="x", title="t", duration_seconds=120)
    cues = [TranscriptCue(start=0, end=2, text="hi")]
    candidates = [
        CandidateClip(start_seconds=0, end_seconds=30, hype_score=9,
                      hype_reasoning="r", transcript_excerpt="e"),
    ]

    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute = AsyncMock()
    sb.table.return_value.insert.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[{"id": "cand-1"}])
    )
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[{"id": "cand-1"}])
    )

    # Mock the audio-extraction subprocess so ffmpeg is not actually invoked.
    proc_mock = MagicMock()
    proc_mock.wait = AsyncMock(return_value=0)

    br_mock = MagicMock()
    br_mock.publish = AsyncMock()

    with patch("services.clips.job_runner.get_async_client", new=AsyncMock(return_value=sb)), \
         patch("services.clips.job_runner.fetch_metadata", new=AsyncMock(return_value=metadata)), \
         patch("services.clips.job_runner.download_source",
               new=AsyncMock(return_value=tmp_path / "source.mp4")), \
         patch("services.clips.job_runner.fetch_transcript", new=AsyncMock(return_value=cues)), \
         patch("services.clips.job_runner.segment_and_score", new=AsyncMock(return_value=candidates)), \
         patch("services.clips.job_runner.render_all_previews",
               new=AsyncMock(return_value=[
                   {"candidate_id": "cand-1",
                    "preview_storage_key": "k1", "preview_poster_key": "k1.jpg",
                    "render_failed": False},
               ])), \
         patch("services.clips.job_runner.asyncio.create_subprocess_exec",
               new=AsyncMock(return_value=proc_mock)), \
         patch("services.clips.job_runner.broker", new=br_mock) as br:
        await run_pipeline(job_id=job_id, user_id=user_id, url=url, tmp_dir=tmp_path)

    # Should have published progress + ready events
    assert br.publish.await_count >= 2


@pytest.mark.asyncio
async def test_recover_orphans_marks_processing_as_failed():
    sb = MagicMock()
    sb.table.return_value.update.return_value.in_.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[{"id": "j1"}, {"id": "j2"}])
    )
    with patch("services.clips.job_runner.get_async_client", new=AsyncMock(return_value=sb)):
        n = await recover_orphans()
    assert n == 2
