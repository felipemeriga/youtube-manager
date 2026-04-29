import asyncio
import logging
import re
from pathlib import Path

from config import settings

from .models import TranscriptCue

logger = logging.getLogger(__name__)

VTT_TIMESTAMP_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2})\.(\d{3})"
)


def _ts_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_vtt(content: str) -> list[TranscriptCue]:
    cues: list[TranscriptCue] = []
    blocks = re.split(r"\n\n+", content.strip())
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln and ln != "WEBVTT"]
        if not lines:
            continue
        ts_line = next((ln for ln in lines if "-->" in ln), None)
        if not ts_line:
            continue
        m = VTT_TIMESTAMP_RE.search(ts_line)
        if not m:
            continue
        start = _ts_to_seconds(*m.groups()[:4])
        end = _ts_to_seconds(*m.groups()[4:])
        text = " ".join(ln for ln in lines if ln is not ts_line and "-->" not in ln).strip()
        if text:
            cues.append(TranscriptCue(start=start, end=end, text=text))
    return cues


def is_broken_captions(cues: list) -> bool:
    if len(cues) < 5:
        return True
    music_tag_re = re.compile(r"\[(music|applause|laughter|silence)\]", re.IGNORECASE)
    music_count = sum(1 for c in cues if music_tag_re.fullmatch(c.text.strip()))
    if music_count / len(cues) > 0.5:
        return True
    return False


async def _download_yt_captions(url: str, out_dir: Path) -> Path | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "--write-auto-subs", "--sub-langs", "en",
        "--sub-format", "vtt",
        "--skip-download",
        "--convert-subs", "vtt",
        "-o", str(out_dir / "captions.%(ext)s"),
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    candidates = list(out_dir.glob("captions*.vtt"))
    return candidates[0] if candidates else None


async def _whisper_transcribe(audio_path: Path) -> list[TranscriptCue]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    with audio_path.open("rb") as f:
        result = await client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    cues: list[TranscriptCue] = []
    # Group words into ~5s cues for downstream sentence-aware segmentation
    current_words: list[str] = []
    current_start: float | None = None
    last_end: float = 0.0
    for w in getattr(result, "words", []) or []:
        if current_start is None:
            current_start = w.start
        current_words.append(w.word)
        last_end = w.end
        if last_end - current_start >= 5.0 or w.word.endswith((".", "?", "!")):
            cues.append(TranscriptCue(
                start=current_start, end=last_end, text=" ".join(current_words).strip(),
            ))
            current_words = []
            current_start = None
    if current_words and current_start is not None:
        cues.append(TranscriptCue(
            start=current_start, end=last_end, text=" ".join(current_words).strip(),
        ))
    return cues


async def fetch_transcript(
    url: str,
    audio_path: Path,
    tmp_dir: Path,
) -> list[TranscriptCue]:
    """Try YouTube auto-captions first; fall back to Whisper if missing/broken.

    Retries Whisper once on failure before raising.
    """
    vtt_path = await _download_yt_captions(url, tmp_dir)
    if vtt_path and vtt_path.exists():
        cues = parse_vtt(vtt_path.read_text())
        if not is_broken_captions(cues):
            logger.info("Using YT captions: %d cues", len(cues))
            return cues
        logger.info("YT captions broken (%d cues) — falling back to Whisper", len(cues))
    else:
        logger.info("YT captions missing — falling back to Whisper")

    last_err: Exception | None = None
    for attempt in range(2):
        try:
            return await _whisper_transcribe(audio_path)
        except Exception as e:
            last_err = e
            logger.warning("Whisper attempt %d failed: %s", attempt + 1, e)
    raise RuntimeError(f"Transcription failed: {last_err}")
