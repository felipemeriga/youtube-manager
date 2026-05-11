import asyncio
import logging
import re
from pathlib import Path

from config import settings

from .models import TranscriptCue

logger = logging.getLogger(__name__)

# Maximum words shown per subtitle frame.  Longer cues are split into
# proportionally-timed sub-cues so viewers can read comfortably.
MAX_WORDS_PER_CUE = 8
# Once a chunk has at least this many words, a `.`, `?`, or `!` is enough to
# end it — landing on a sentence boundary even if a few words short.
_SOFT_BREAK_AFTER = max(4, MAX_WORDS_PER_CUE - 4)

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
        text = " ".join(
            ln for ln in lines if ln is not ts_line and "-->" not in ln
        ).strip()
        if text:
            cues.append(TranscriptCue(start=start, end=end, text=text))
    return cues


def _smart_chunk(words: list[str]) -> list[list[str]]:
    """Group a flat word list into subtitle-sized chunks, preferring breaks
    after sentence-ending punctuation (``.?!``) and falling back to clause
    punctuation (``,;:``) once the chunk is close to the hard limit.

    A chunk never exceeds ``MAX_WORDS_PER_CUE`` words; a sentence boundary
    landing a few words short is allowed so the next subtitle can start on
    a new sentence instead of mid-clause.
    """
    chunks: list[list[str]] = []
    current: list[str] = []
    for w in words:
        current.append(w)
        last = w[-1:] if w else ""
        is_sentence_end = last in ".?!"
        is_clause_end = last in ",;:"
        # Strong preference: end the chunk after a full sentence once we
        # have a readable minimum number of words.
        if is_sentence_end and len(current) >= _SOFT_BREAK_AFTER:
            chunks.append(current)
            current = []
            continue
        # Mild preference: a comma is a fine break when we're already near
        # the hard cap and another word would overflow.
        if is_clause_end and len(current) >= MAX_WORDS_PER_CUE - 1:
            chunks.append(current)
            current = []
            continue
        # Hard cap.
        if len(current) >= MAX_WORDS_PER_CUE:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def _split_long_cues(cues: list[TranscriptCue]) -> list[TranscriptCue]:
    """Split cues into subtitle-sized sub-cues, preferring breaks at
    sentence/clause punctuation. Cues already short enough pass through.

    Time is distributed proportionally across sub-cues so each chunk appears
    on screen for a duration that matches its share of the original text.
    """
    out: list[TranscriptCue] = []
    for cue in cues:
        words = cue.text.split()
        if len(words) <= MAX_WORDS_PER_CUE:
            out.append(cue)
            continue
        chunks = _smart_chunk(words)
        total_words = sum(len(c) for c in chunks)
        duration = cue.end - cue.start
        offset = cue.start
        for chunk in chunks:
            chunk_duration = duration * (len(chunk) / total_words)
            out.append(
                TranscriptCue(
                    start=offset,
                    end=offset + chunk_duration,
                    text=" ".join(chunk),
                )
            )
            offset += chunk_duration
    return out


_PUNCTUATE_SYSTEM = (
    "You are a punctuation corrector for video subtitles. "
    "Detect the language of the input text and add punctuation that is "
    "natural for that language — commas, periods, question marks, "
    "exclamation marks, semicolons, colons, and quotation marks where "
    "appropriate. Fix capitalization at sentence starts and on proper nouns. "
    "Do NOT change, add, remove, or reorder any words — only insert "
    "punctuation and fix letter case. Preserve hyphens inside hyphenated "
    "words (e.g. 'well-known'). Return ONLY the corrected text, nothing else."
)

_PUNCTUATE_MODEL = "claude-haiku-4-5-20251001"


async def add_punctuation(cues: list[TranscriptCue]) -> list[TranscriptCue]:
    """Run cue texts through a fast LLM to add missing punctuation.

    Joins all cue texts, sends to Haiku, then maps the punctuated words
    back onto the original cues preserving their timestamps.  Falls back
    to the original cues if the LLM changes the word count.
    """
    from services.llm import ask_llm

    if not cues:
        return cues

    # Build flat text with word count per cue for redistribution
    word_counts = [len(c.text.split()) for c in cues]
    flat_text = " ".join(c.text for c in cues)

    try:
        punctuated = await ask_llm(
            system=_PUNCTUATE_SYSTEM,
            messages=[{"role": "user", "content": flat_text}],
            model=_PUNCTUATE_MODEL,
        )
    except Exception:
        logger.warning("Punctuation LLM call failed — using raw transcript")
        return cues

    # Strip any wrapping quotes or whitespace the model might add
    punctuated = punctuated.strip().strip('"').strip("'").strip()
    punct_words = punctuated.split()

    # Validate: word count must match (LLM was told not to add/remove words)
    total_original = sum(word_counts)
    if len(punct_words) != total_original:
        logger.warning(
            "Punctuation word count mismatch: original=%d, punctuated=%d — skipping",
            total_original,
            len(punct_words),
        )
        return cues

    # Redistribute punctuated words back onto cues
    out: list[TranscriptCue] = []
    offset = 0
    for cue, wc in zip(cues, word_counts):
        new_text = " ".join(punct_words[offset : offset + wc])
        out.append(TranscriptCue(start=cue.start, end=cue.end, text=new_text))
        offset += wc
    return out


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
        "--write-auto-subs",
        "--sub-langs",
        "en",
        "--sub-format",
        "vtt",
        "--skip-download",
        "--convert-subs",
        "vtt",
        "-o",
        str(out_dir / "captions.%(ext)s"),
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
    # Group words into ~2.5s cues so each subtitle frame stays short and
    # readable.  Also break on sentence-ending punctuation.
    current_words: list[str] = []
    current_start: float | None = None
    last_end: float = 0.0
    for w in getattr(result, "words", []) or []:
        if current_start is None:
            current_start = w.start
        current_words.append(w.word)
        last_end = w.end
        if last_end - current_start >= 2.5 or w.word.endswith((".", "?", "!")):
            cues.append(
                TranscriptCue(
                    start=current_start,
                    end=last_end,
                    text=" ".join(current_words).strip(),
                )
            )
            current_words = []
            current_start = None
    if current_words and current_start is not None:
        cues.append(
            TranscriptCue(
                start=current_start,
                end=last_end,
                text=" ".join(current_words).strip(),
            )
        )
    return cues


async def fetch_transcript(
    url: str,
    audio_path: Path,
    tmp_dir: Path,
) -> list[TranscriptCue]:
    """Try YouTube auto-captions first; fall back to Whisper if missing/broken.

    Retries Whisper once on failure before raising.
    """
    # Return raw cues without splitting — the caller (`job_runner`) runs
    # `add_punctuation` first, then `_split_long_cues`, so subtitle breaks
    # can land on sentence boundaries instead of mid-clause.
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
