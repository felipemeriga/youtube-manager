from unittest.mock import AsyncMock, patch

import pytest

from services.clips.transcript import (
    add_punctuation,
    fetch_transcript,
    parse_vtt,
    is_broken_captions,
    _split_long_cues,
)
from services.clips.models import TranscriptCue


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
    cues = [
        type("C", (), {"text": t})()
        for t in ["[Music]", "[Music]", "[Applause]", "[Music]", "[Music]", "[Music]"]
    ]
    assert is_broken_captions(cues) is True


def test_is_broken_captions_normal_passes():
    cues = [type("C", (), {"text": "Hello world this is content"})() for _ in range(10)]
    assert is_broken_captions(cues) is False


def test_split_long_cues_short_cue_unchanged():
    cues = [TranscriptCue(start=0.0, end=2.0, text="Short phrase here")]
    result = _split_long_cues(cues)
    assert len(result) == 1
    assert result[0].text == "Short phrase here"


def test_split_long_cues_splits_long_cue():
    text = "one two three four five six seven eight nine ten eleven twelve"
    cues = [TranscriptCue(start=0.0, end=12.0, text=text)]
    result = _split_long_cues(cues)
    assert len(result) == 2
    assert result[0].text == "one two three four five six seven eight"
    assert result[1].text == "nine ten eleven twelve"
    # Time is proportionally distributed
    assert result[0].start == 0.0
    assert abs(result[0].end - 8.0) < 0.01  # 8/12 words * 12s
    assert abs(result[1].start - 8.0) < 0.01
    assert abs(result[1].end - 12.0) < 0.01


def test_split_long_cues_breaks_at_sentence_end():
    """When a sentence ends within the soft-break window, the chunk ends there
    even if a few words short of the hard cap."""
    text = "Hi there. This second sentence runs a little longer overall."
    # 11 words; hard cap is 8.  After "there." (2 words) we're below the
    # soft-break floor of 4, so first chunk should continue until "longer"
    # (10th word) — i.e. once we have >=4 words AND see a '.' or '!'/'?'.
    # The natural split lands at "longer." (end of sentence) once length>=4.
    cues = [TranscriptCue(start=0.0, end=11.0, text=text)]
    result = _split_long_cues(cues)
    # Last chunk should end with a sentence-ending mark, not be cut mid-clause
    assert result[-1].text.rstrip().endswith((".", "?", "!"))


def test_split_long_cues_prefers_comma_near_limit():
    """A comma at word 7 should be a better break than continuing to word 8."""
    text = "alpha bravo charlie delta echo foxtrot golf, hotel india juliet"
    cues = [TranscriptCue(start=0.0, end=10.0, text=text)]
    result = _split_long_cues(cues)
    # First chunk should end with the comma word, not be cut after "hotel"
    assert result[0].text.endswith("golf,")


def test_split_long_cues_preserves_time_bounds():
    cues = [
        TranscriptCue(start=5.0, end=10.0, text=" ".join(f"w{i}" for i in range(20)))
    ]
    result = _split_long_cues(cues)
    assert result[0].start == 5.0
    assert abs(result[-1].end - 10.0) < 0.01
    for cue in result:
        assert len(cue.text.split()) <= 8


@pytest.mark.asyncio
async def test_fetch_transcript_uses_yt_captions_when_good(tmp_path):
    vtt_path = tmp_path / "captions.en.vtt"
    vtt_path.write_text(SAMPLE_VTT * 5)  # 10 cues

    async def fake_dl(url, out_dir):
        return vtt_path

    with patch("services.clips.transcript._download_yt_captions", new=fake_dl):
        cues = await fetch_transcript(
            "https://youtu.be/x", tmp_path / "audio.mp3", tmp_path
        )
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

    with (
        patch("services.clips.transcript._download_yt_captions", new=fake_dl),
        patch("services.clips.transcript._whisper_transcribe", new=fake_whisper),
    ):
        cues = await fetch_transcript(
            "https://youtu.be/x", tmp_path / "audio.mp3", tmp_path
        )
    assert len(cues) == 2


@pytest.mark.asyncio
async def test_add_punctuation_maps_words_back():
    cues = [
        TranscriptCue(start=0.0, end=2.0, text="hello world"),
        TranscriptCue(start=2.0, end=4.0, text="how are you"),
    ]
    with patch(
        "services.llm.ask_llm",
        new_callable=AsyncMock,
        return_value="Hello world, how are you?",
    ):
        result = await add_punctuation(cues)
    assert result[0].text == "Hello world,"
    assert result[1].text == "how are you?"
    # Timestamps preserved
    assert result[0].start == 0.0
    assert result[1].end == 4.0


@pytest.mark.asyncio
async def test_add_punctuation_falls_back_on_word_count_mismatch():
    cues = [TranscriptCue(start=0.0, end=2.0, text="hello world")]
    # LLM adds an extra word — should fall back to original
    with patch(
        "services.llm.ask_llm",
        new_callable=AsyncMock,
        return_value="Hello, beautiful world!",
    ):
        result = await add_punctuation(cues)
    assert result[0].text == "hello world"


@pytest.mark.asyncio
async def test_add_punctuation_falls_back_on_llm_failure():
    cues = [TranscriptCue(start=0.0, end=2.0, text="hello world")]
    with patch(
        "services.llm.ask_llm",
        new_callable=AsyncMock,
        side_effect=RuntimeError("API down"),
    ):
        result = await add_punctuation(cues)
    assert result[0].text == "hello world"
