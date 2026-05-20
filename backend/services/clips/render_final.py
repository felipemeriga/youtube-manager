import asyncio
import logging
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Awaitable, Callable

from .face_detection import detect_face_track
from .models import CandidateClip, TranscriptCue
from .render_preview import FINAL_OUTPUT_SIZE, _video_dims, build_crop_filter
from .storage import final_key, upload_file

ProgressCallback = Callable[[int], Awaitable[None]]

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _subtitles_filter_available() -> bool:
    """Return True if this ffmpeg build includes the `subtitles` filter (libass).

    Some minimal ffmpeg builds (e.g. recent Homebrew bottles for arm64) ship
    without libass / libfreetype, which means captions can't be burned in. We
    detect that once and let the caller skip the filter so the render still
    succeeds without captions.
    """
    try:
        out = subprocess.check_output(
            ["ffmpeg", "-hide_banner", "-filters"], stderr=subprocess.DEVNULL
        ).decode()
    except Exception:
        return False
    for line in out.splitlines():
        # Filter list rows are formatted: "<flags> <name> <io>  <description>"
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "subtitles":
            return True
    return False


# Caption style presets. Each value is a single ASS "Style: Default,..." line.
# Format fields (must match the Format: row in the [V4+ Styles] section below):
#   Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold,
#   BorderStyle (1=outline, 3=opaque box), Outline, Shadow, Alignment (numpad),
#   MarginL, MarginR, MarginV, Encoding
CAPTION_PRESETS: dict[str, str] = {
    # White text, thick black outline. Bottom-center. Universal default.
    "classic": "Style: Default,Arial,48,&H00FFFFFF,&H00000000,&H80000000,1,1,3,1,2,40,40,80,1",
    # Big white text, heavy outline, bottom-center. Inspired by social-clip overlays.
    "tiktok": "Style: Default,Impact,56,&H00FFFFFF,&H00000000,&H80000000,1,1,4,2,2,40,40,90,1",
    # Bright yellow w/ thick black outline. Bottom-center.
    "bold_yellow": "Style: Default,Arial,52,&H0000FFFF,&H00000000,&H80000000,1,1,4,1,2,40,40,80,1",
    # White text on opaque black rounded box. Bottom-center.
    "minimal_box": "Style: Default,Arial,42,&H00FFFFFF,&H00000000,&HC0000000,0,3,2,0,2,40,40,80,1",
    # Same as classic but anchored to top-center (alignment 8).
    "top_centered": "Style: Default,Arial,48,&H00FFFFFF,&H00000000,&H80000000,1,1,3,1,8,40,40,80,1",
}

DEFAULT_CAPTION_STYLE = "classic"


def _build_ass_header(caption_style: str) -> str:
    style_line = CAPTION_PRESETS.get(caption_style)
    if style_line is None:
        logger.warning(
            "Unknown caption_style %r — falling back to %r",
            caption_style,
            DEFAULT_CAPTION_STYLE,
        )
        style_line = CAPTION_PRESETS[DEFAULT_CAPTION_STYLE]
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 720\n"
        "PlayResY: 1280\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, "
        "Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"{style_line}\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def _seconds_to_ass_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


CUE_GAP_SECONDS = 0.12  # short blank between back-to-back cues so consecutive
# phrases don't visually glue into one paragraph


def build_ass_file(
    cues: list[TranscriptCue],
    clip_start: float,
    clip_end: float,
    out_path: Path,
    caption_style: str = DEFAULT_CAPTION_STYLE,
) -> None:
    """Write a .ass file containing only the cues that overlap [clip_start, clip_end].

    Times are normalized so the clip's first cue starts near 0:00:00. When two
    cues are temporally adjacent (no natural pause between them), the earlier
    one's display end is shortened by CUE_GAP_SECONDS so libass renders a brief
    blank — otherwise the text swap is instantaneous and reads as one paragraph.
    """
    visible = [c for c in cues if c.end > clip_start and c.start < clip_end]
    lines: list[str] = [_build_ass_header(caption_style)]
    for i, cue in enumerate(visible):
        local_start = max(0.0, cue.start - clip_start)
        local_end = min(clip_end - clip_start, cue.end - clip_start)
        next_cue = visible[i + 1] if i + 1 < len(visible) else None
        if next_cue is not None:
            next_local_start = max(0.0, next_cue.start - clip_start)
            # If the next cue starts within CUE_GAP_SECONDS of this cue's end,
            # pull this cue's end back so there's a visible gap. Never let the
            # cue collapse to zero/negative duration.
            if next_local_start - local_end < CUE_GAP_SECONDS:
                local_end = max(local_start + 0.05, next_local_start - CUE_GAP_SECONDS)
        # ASS Dialogue: Text is the LAST field — commas inside it are part of
        # the text, not field separators, so they must NOT be backslash-escaped
        # (libass renders `\,` literally or drops it).
        text = cue.text.replace("\n", " ")
        lines.append(
            f"Dialogue: 0,{_seconds_to_ass_ts(local_start)},"
            f"{_seconds_to_ass_ts(local_end)},Default,,0,0,0,,{text}"
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")


async def _ffmpeg_render_with_subs(
    source: Path,
    start: float,
    end: float,
    vf_with_subs: str,
    out: Path,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Encode a single clip. If `on_progress` is provided, ffmpeg emits structured
    key=value progress lines on stdout (`-progress pipe:1`) which we parse and
    forward as integer pct in [0, 99]. The final 100 should be emitted by the
    caller after upload, not here."""
    duration = max(0.001, end - start)
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-ss",
        str(start),
        "-to",
        str(end),
        "-i",
        str(source),
        "-vf",
        vf_with_subs,
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "slow",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-progress",
        "pipe:1",
        "-nostats",
        str(out),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def _read_progress() -> None:
        if on_progress is None or proc.stdout is None:
            return
        last_pct = -1
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            line = raw.decode(errors="replace").strip()
            if not line.startswith("out_time_us=") and not line.startswith(
                "out_time_ms="
            ):
                continue
            try:
                us = int(line.split("=", 1)[1])
            except ValueError:
                continue
            if us < 0:
                continue
            pct = min(99, int(us / 1_000_000 / duration * 100))
            if pct > last_pct:
                last_pct = pct
                try:
                    await on_progress(pct)
                except Exception:
                    pass  # never let progress reporting break the render

    async def _drain_stderr() -> bytes:
        if proc.stderr is None:
            return b""
        return await proc.stderr.read()

    progress_task = asyncio.create_task(_read_progress())
    stderr_task = asyncio.create_task(_drain_stderr())
    await proc.wait()
    # Make sure the readers see EOF and finish.
    await progress_task
    stderr_bytes = await stderr_task

    if proc.returncode != 0:
        # Keep the tail of stderr — the actionable error is almost always near
        # the end (the leading lines are version + input metadata banners).
        err = stderr_bytes.decode(errors="replace")
        raise RuntimeError(f"ffmpeg final render failed: …{err[-1500:]}")


async def render_one_final(
    candidate: CandidateClip,
    candidate_id: str,
    source: Path,
    cues: list[TranscriptCue],
    user_id: str,
    job_id: str,
    tmp_dir: Path,
    on_progress: ProgressCallback | None = None,
    caption_style: str = DEFAULT_CAPTION_STYLE,
) -> str:
    """Render full-quality vertical clip with burned-in captions. Returns storage key."""
    ass_path = tmp_dir / f"{candidate_id}.ass"
    out_path = tmp_dir / f"{candidate_id}_final.mp4"

    build_ass_file(
        cues,
        candidate.start_seconds,
        candidate.end_seconds,
        ass_path,
        caption_style=caption_style,
    )
    width, height = _video_dims(source)
    track = await detect_face_track(source, candidate.duration_seconds)
    crop_scale = build_crop_filter(
        track=track,
        video_height=height,
        video_width=width,
        output_size=FINAL_OUTPUT_SIZE,
    )

    if _subtitles_filter_available():
        # ffmpeg subtitles filter: escape `:` and `\` in the path; use the
        # canonical `filename=` syntax to avoid quote-parsing issues that broke
        # the legacy `subtitles='...'` form on ffmpeg 8+.
        ass_escaped = str(ass_path).replace("\\", "\\\\").replace(":", "\\:")
        vf = f"{crop_scale},subtitles=filename={ass_escaped}"
    else:
        logger.warning(
            "ffmpeg `subtitles` filter unavailable (libass not built in); "
            "rendering final clip without burned-in captions"
        )
        vf = crop_scale

    await _ffmpeg_render_with_subs(
        source,
        candidate.start_seconds,
        candidate.end_seconds,
        vf,
        out_path,
        on_progress=on_progress,
    )
    key = final_key(user_id, job_id, candidate_id)
    await upload_file(out_path, key, "video/mp4")
    return key
