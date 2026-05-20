from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.clips.job_runner import (
    run_pipeline,
    run_finals_pipeline,
    register_task,
    get_task,
    cancel_task,
    recover_orphans,
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
        CandidateClip(
            start_seconds=0,
            end_seconds=30,
            hype_score=9,
            hype_reasoning="r",
            transcript_excerpt="e",
        ),
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
    published: list[dict] = []

    async def _publish(_job_id, event):
        published.append(event)

    br_mock.publish = AsyncMock(side_effect=_publish)

    with (
        patch(
            "services.clips.job_runner.get_async_client", new=AsyncMock(return_value=sb)
        ),
        patch(
            "services.clips.job_runner.fetch_metadata",
            new=AsyncMock(return_value=metadata),
        ),
        patch(
            "services.clips.job_runner.download_source",
            new=AsyncMock(return_value=tmp_path / "source.mp4"),
        ),
        patch(
            "services.clips.job_runner.fetch_transcript",
            new=AsyncMock(return_value=cues),
        ),
        patch(
            "services.clips.job_runner.segment_and_score",
            new=AsyncMock(return_value=candidates),
        ),
        patch(
            "services.clips.job_runner.render_all_previews",
            new=AsyncMock(
                return_value=[
                    {
                        "candidate_id": "cand-1",
                        "preview_storage_key": "k1",
                        "preview_poster_key": "k1.jpg",
                        "render_failed": False,
                    },
                ]
            ),
        ),
        patch(
            "services.clips.job_runner.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc_mock),
        ),
        patch("services.clips.job_runner.broker", new=br_mock),
    ):
        await run_pipeline(job_id=job_id, user_id=user_id, url=url, tmp_dir=tmp_path)

    # Stages must appear in the order JobProgressPanel's STAGE_ORDER expects.
    progress_stages = [e["stage"] for e in published if e.get("type") == "progress"]
    expected = ["metadata", "download", "transcribe", "segment", "preview_render"]
    seen_idx = -1
    for stage in expected:
        try:
            seen_idx = progress_stages.index(stage, seen_idx + 1)
        except ValueError:
            pytest.fail(
                f"Expected stage {stage!r} not found in order. Got: {progress_stages}"
            )

    # Must end with a 'ready' event so the UI knows candidates are available.
    assert any(e.get("type") == "ready" for e in published)


@pytest.mark.asyncio
async def test_run_finals_pipeline_publishes_stages_in_order(tmp_path):
    """Verifies the finals pipeline emits the four stages the UI breadcrumb
    expects (download_source → extract_audio → transcribe → render_finals →
    done) plus per-candidate render_progress/render_complete events. The
    FinalRenderPanel UI relies on this exact ordering."""
    job_id = "job-r"
    user_id = "user-r"
    candidate_ids = ["cand-1", "cand-2"]
    cues = [TranscriptCue(start=0, end=2, text="hi")]

    sb = MagicMock()
    # job_res select
    sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
        return_value=MagicMock(
            data={
                "id": job_id,
                "user_id": user_id,
                "youtube_url": "https://youtu.be/x",
                "source_storage_key": f"{user_id}/{job_id}/source.mp4",
            }
        )
    )
    # candidates select
    sb.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
        return_value=MagicMock(
            data=[
                {
                    "id": "cand-1",
                    "start_seconds": 0,
                    "end_seconds": 30,
                    "hype_score": 9,
                    "hype_reasoning": "r",
                    "transcript_excerpt": "e",
                },
                {
                    "id": "cand-2",
                    "start_seconds": 30,
                    "end_seconds": 60,
                    "hype_score": 8,
                    "hype_reasoning": "r",
                    "transcript_excerpt": "e",
                },
            ]
        )
    )
    sb.table.return_value.update.return_value.eq.return_value.execute = AsyncMock()

    proc_mock = MagicMock()
    proc_mock.wait = AsyncMock(return_value=0)

    br_mock = MagicMock()
    published: list[dict] = []

    async def _publish(_job_id, event):
        published.append(event)

    br_mock.publish = AsyncMock(side_effect=_publish)

    async def _render_one_final(*args, on_progress=None, **kwargs):
        # Simulate a render emitting a couple of intra-encode progress events.
        if on_progress:
            await on_progress(50)
            await on_progress(99)
        return f"finals/{kwargs.get('candidate_id', 'x')}.mp4"

    with (
        patch(
            "services.clips.job_runner.get_async_client", new=AsyncMock(return_value=sb)
        ),
        patch("services.clips.job_runner.download_file", new=AsyncMock()),
        patch(
            "services.clips.job_runner.fetch_transcript",
            new=AsyncMock(return_value=cues),
        ),
        patch(
            "services.clips.job_runner.signed_url_helper",
            new=AsyncMock(return_value="https://signed.example/abc"),
        ),
        patch(
            "services.clips.job_runner.render_one_final",
            new=AsyncMock(side_effect=_render_one_final),
        ),
        patch(
            "services.clips.job_runner.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc_mock),
        ),
        patch("services.clips.job_runner.broker", new=br_mock),
    ):
        await run_finals_pipeline(
            job_id=job_id,
            user_id=user_id,
            candidate_ids=candidate_ids,
            tmp_dir=tmp_path,
            caption_style="tiktok",
        )

    # Extract the progress stages in order — these drive the FinalRenderPanel
    # breadcrumb. Other event types are interleaved, so filter to just
    # progress events for the order check.
    progress_stages = [e["stage"] for e in published if e.get("type") == "progress"]
    # Each stage must appear at least once, in this exact relative order.
    expected = [
        "download_source",
        "extract_audio",
        "transcribe",
        "render_finals",
        "done",
    ]
    seen_idx = -1
    for stage in expected:
        try:
            seen_idx = progress_stages.index(stage, seen_idx + 1)
        except ValueError:
            pytest.fail(
                f"Expected stage {stage!r} not found in order. Got: {progress_stages}"
            )

    # Per-candidate render_progress events should fire (intra + final 100).
    rp = [e for e in published if e.get("type") == "render_progress"]
    rp_by_cand = {
        cid: [e["pct"] for e in rp if e["candidate_id"] == cid] for cid in candidate_ids
    }
    for cid in candidate_ids:
        assert rp_by_cand[cid], f"no render_progress for {cid}"
        assert rp_by_cand[cid][-1] == 100, (
            f"final render_progress for {cid} must be 100, got {rp_by_cand[cid]}"
        )

    # Each candidate must get a render_complete event with a signed URL.
    rc = [e for e in published if e.get("type") == "render_complete"]
    assert {e["candidate_id"] for e in rc} == set(candidate_ids)
    assert all(e["signed_url"].startswith("https://") for e in rc)

    # Final terminator: render_complete_all must be the last event published.
    assert published[-1].get("type") == "render_complete_all"


@pytest.mark.asyncio
async def test_recover_orphans_marks_processing_as_failed():
    sb = MagicMock()
    sb.table.return_value.update.return_value.in_.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[{"id": "j1"}, {"id": "j2"}])
    )
    with patch(
        "services.clips.job_runner.get_async_client", new=AsyncMock(return_value=sb)
    ):
        n = await recover_orphans()
    assert n == 2
