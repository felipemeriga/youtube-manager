import json
from unittest.mock import AsyncMock, patch

import pytest

from services.clips.models import TranscriptCue
from services.clips.segment import segment_and_score, candidate_cap


def test_candidate_cap_short_video():
    # 5 minutes → ceil(5/2) = 3 candidates
    assert candidate_cap(300) == 3


def test_candidate_cap_long_video():
    # 60 minutes → ceil(60/2) = 30 → capped at 20
    assert candidate_cap(3600) == 20


def test_candidate_cap_one_minute_min_one():
    assert candidate_cap(60) == 1


@pytest.mark.asyncio
async def test_segment_and_score_parses_llm_json():
    cues = [TranscriptCue(start=i, end=i + 2, text=f"line {i}") for i in range(0, 60, 2)]
    fake_response = json.dumps([
        {"start_time": 0, "end_time": 30, "hype_score": 9.0,
         "reasoning": "strong hook", "transcript_excerpt": "line 0..."},
        {"start_time": 30, "end_time": 50, "hype_score": 7.0,
         "reasoning": "good payoff", "transcript_excerpt": "line 30..."},
    ])
    with patch("services.clips.segment._ask_llm_for_segments", new=AsyncMock(return_value=fake_response)):
        result = await segment_and_score(cues, duration_seconds=240)
    assert len(result) == 2
    assert result[0].hype_score == 9.0
    assert result[0].duration_seconds == 30


@pytest.mark.asyncio
async def test_segment_caps_to_max():
    cues = [TranscriptCue(start=i, end=i + 1, text=f"l{i}") for i in range(120)]
    items = [
        {"start_time": i * 2, "end_time": i * 2 + 30, "hype_score": 10 - (i * 0.1),
         "reasoning": "x", "transcript_excerpt": "x"}
        for i in range(50)
    ]
    fake_response = json.dumps(items)
    with patch("services.clips.segment._ask_llm_for_segments", new=AsyncMock(return_value=fake_response)):
        # 120 sec / 2 = 1, capped — actually duration=120 → ceil(2)=1, cap=min(20, 1)=1
        result = await segment_and_score(cues, duration_seconds=1200)
    assert len(result) == 10  # 1200s = 20min → cap at min(20, 10) = 10


@pytest.mark.asyncio
async def test_segment_retries_on_invalid_json():
    cues = [TranscriptCue(start=0, end=5, text="hi")]
    valid_response = json.dumps([
        {"start_time": 0, "end_time": 5, "hype_score": 5.0,
         "reasoning": "ok", "transcript_excerpt": "hi"},
    ])
    mock = AsyncMock(side_effect=["not json", "still bad", valid_response])
    with patch("services.clips.segment._ask_llm_for_segments", new=mock):
        result = await segment_and_score(cues, duration_seconds=60)
    assert len(result) == 1
