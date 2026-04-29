from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from services.clips.transcript import (
    fetch_transcript, parse_vtt, is_broken_captions,
)


SAMPLE_VTT = """WEBVTT

00:00:00.000 --> 00:00:02.500
Welcome to my channel.

00:00:02.500 --> 00:00:05.000
Today we're talking about Python.
"""


def test_parse_vtt_returns_cues():
    cues = parse_vtt(SAMPLE_VTT)
    assert len(cues) == 2
    assert cues[0].start == 0.0
    assert cues[0].end == 2.5
    assert cues[0].text == "Welcome to my channel."


def test_is_broken_captions_empty():
    assert is_broken_captions([]) is True


def test_is_broken_captions_too_few():
    cues = [type("C", (), {"text": f"line {i}"})() for i in range(3)]
    assert is_broken_captions(cues) is True


def test_is_broken_captions_mostly_music_tags():
    cues = [type("C", (), {"text": t})() for t in
            ["[Music]", "[Music]", "[Applause]", "[Music]", "[Music]", "[Music]"]]
    assert is_broken_captions(cues) is True


def test_is_broken_captions_normal_passes():
    cues = [type("C", (), {"text": "Hello world this is content"})() for _ in range(10)]
    assert is_broken_captions(cues) is False


@pytest.mark.asyncio
async def test_fetch_transcript_uses_yt_captions_when_good(tmp_path):
    vtt_path = tmp_path / "captions.en.vtt"
    vtt_path.write_text(SAMPLE_VTT * 5)  # 10 cues

    async def fake_dl(url, out_dir):
        return vtt_path

    with patch("services.clips.transcript._download_yt_captions", new=fake_dl):
        cues = await fetch_transcript("https://youtu.be/x", tmp_path / "audio.mp3", tmp_path)
    assert len(cues) >= 5


@pytest.mark.asyncio
async def test_fetch_transcript_falls_back_to_whisper(tmp_path):
    # YT captions return None → fallback
    async def fake_dl(url, out_dir):
        return None

    fake_whisper_cues = [
        type("C", (), {"start": 0.0, "end": 1.0, "text": "hi"})(),
        type("C", (), {"start": 1.0, "end": 2.0, "text": "there"})(),
    ]

    async def fake_whisper(audio_path):
        return fake_whisper_cues

    with patch("services.clips.transcript._download_yt_captions", new=fake_dl), \
         patch("services.clips.transcript._whisper_transcribe", new=fake_whisper):
        cues = await fetch_transcript("https://youtu.be/x", tmp_path / "audio.mp3", tmp_path)
    assert len(cues) == 2
