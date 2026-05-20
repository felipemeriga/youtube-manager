from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from services.clips.download import download_source
from services.youtube_saas import VideoInfo


def _info() -> VideoInfo:
    return VideoInfo(
        video_id="abc",
        title="t",
        duration_seconds=120,
        video_url="https://example.test/v.mp4",
        audio_url="https://example.test/a.m4a",
        caption_url=None,
        caption_lang=None,
    )


@pytest.mark.asyncio
async def test_download_source_fetches_and_muxes_then_uploads(tmp_path):
    captured: dict = {}

    async def fake_dl(info, dest_mp4):
        Path(dest_mp4).write_bytes(b"fake mp4")
        captured["dest"] = dest_mp4
        captured["video_url"] = info.video_url

    async def fake_upload(local, key, content_type):
        captured["upload_local"] = str(local)
        captured["upload_key"] = key

    with (
        patch(
            "services.clips.download.fetch_video_info",
            new=AsyncMock(return_value=_info()),
        ),
        patch("services.clips.download.download_video_and_audio", new=fake_dl),
        patch("services.clips.download.upload_file", new=fake_upload),
    ):
        local_path = await download_source(
            url="https://youtu.be/abc",
            user_id="u1",
            job_id="j1",
            tmp_dir=tmp_path,
        )
    assert local_path.exists()
    assert captured["video_url"] == "https://example.test/v.mp4"
    assert captured["upload_key"] == "u1/j1/source.mp4"


@pytest.mark.asyncio
async def test_download_source_propagates_failure(tmp_path):
    with (
        patch(
            "services.clips.download.fetch_video_info",
            new=AsyncMock(return_value=_info()),
        ),
        patch(
            "services.clips.download.download_video_and_audio",
            new=AsyncMock(side_effect=RuntimeError("mux fail")),
        ),
    ):
        with pytest.raises(RuntimeError):
            await download_source(
                url="https://youtu.be/x",
                user_id="u",
                job_id="j",
                tmp_dir=tmp_path,
            )
