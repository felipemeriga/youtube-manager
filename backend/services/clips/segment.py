import json
import logging
import math

from services.llm import ask_llm

from .models import CandidateClip, TranscriptCue

logger = logging.getLogger(__name__)


SEGMENT_SYSTEM_PROMPT = """You analyze video transcripts to find the most viral, clip-worthy moments
suitable for vertical Shorts/Reels. You return a JSON array of clip candidates.

Rules:
- Each clip must be between 15 and 60 seconds
- Prefer 20-45 seconds
- Start and end must align with sentence boundaries from the transcript
- hype_score is 0-10 (higher = more viral potential)
- reasoning is one short sentence

Return JSON only, no prose."""


SEGMENT_USER_PROMPT_TEMPLATE = """Transcript with timestamps:
{transcript}

Return a JSON array. Each item: {{
  "start_time": number (seconds),
  "end_time": number (seconds),
  "hype_score": number 0-10,
  "reasoning": string (one sentence),
  "transcript_excerpt": string (the dialogue inside the clip window)
}}"""


def candidate_cap(duration_seconds: int) -> int:
    return min(20, max(1, math.ceil(duration_seconds / 60 / 2)))


def _format_transcript(cues: list[TranscriptCue]) -> str:
    return "\n".join(f"[{c.start:.1f}s] {c.text}" for c in cues)


async def _ask_llm_for_segments(prompt: str) -> str:
    return await ask_llm(
        system=SEGMENT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )


async def segment_and_score(
    cues: list[TranscriptCue],
    duration_seconds: int,
) -> list[CandidateClip]:
    prompt = SEGMENT_USER_PROMPT_TEMPLATE.format(transcript=_format_transcript(cues))
    last_err: Exception | None = None
    for attempt in range(3):
        raw = await _ask_llm_for_segments(prompt)
        try:
            stripped = raw.strip()
            if stripped.startswith("```"):
                stripped = stripped.split("```", 2)[1]
                if stripped.startswith("json"):
                    stripped = stripped[4:]
            data = json.loads(stripped)
            candidates = [
                CandidateClip(
                    start_seconds=float(item["start_time"]),
                    end_seconds=float(item["end_time"]),
                    hype_score=float(item["hype_score"]),
                    hype_reasoning=item.get("reasoning", ""),
                    transcript_excerpt=item.get("transcript_excerpt", ""),
                )
                for item in data
            ]
            candidates.sort(key=lambda c: c.hype_score, reverse=True)
            cap = candidate_cap(duration_seconds)
            return candidates[:cap]
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            last_err = e
            logger.warning("Segment LLM parse attempt %d failed: %s", attempt + 1, e)
    raise RuntimeError(f"LLM segment parsing failed after 3 attempts: {last_err}")
