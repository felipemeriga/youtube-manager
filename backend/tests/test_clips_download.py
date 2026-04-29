from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from services.clips.download import download_source


@pytest.mark.asyncio
async def test_download_source_invokes_ytdlp_and_uploads(tmp_path):
    captured = {}

    async def fake_run(url, out_path):
        Path(out_path).write_bytes(b"fake mp4")
        captured["url"] = url
        captured["out"] = out_path

    async def fake_upload(local, key, content_type):
        captured["upload_local"] = str(local)
        captured["upload_key"] = key

    with patch("services.clips.download._run_ytdlp_download", new=fake_run), \
         patch("services.clips.download.upload_file", new=fake_upload):
        local_path = await download_source(
            url="https://youtu.be/abc",
            user_id="u1",
            job_id="j1",
            tmp_dir=tmp_path,
        )
    assert local_path.exists()
    assert captured["url"] == "https://youtu.be/abc"
    assert captured["upload_key"] == "u1/j1/source.mp4"


@pytest.mark.asyncio
async def test_download_source_propagates_failure(tmp_path):
    with patch("services.clips.download._run_ytdlp_download",
               new=AsyncMock(side_effect=RuntimeError("yt-dlp fail"))):
        with pytest.raises(RuntimeError):
            await download_source(
                url="https://youtu.be/x", user_id="u", job_id="j", tmp_dir=tmp_path,
            )
