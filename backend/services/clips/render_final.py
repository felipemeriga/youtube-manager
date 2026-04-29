import asyncio
import logging
from pathlib import Path

from .face_detection import detect_face_track
from .models import CandidateClip, TranscriptCue
from .render_preview import _video_dims, build_crop_filter
from .storage import final_key, upload_file

logger = logging.getLogger(__name__)


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H00000000,&H80000000,1,1,3,1,2,40,40,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _seconds_to_ass_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass_file(
    cues: list[TranscriptCue],
    clip_start: float,
    clip_end: float,
    out_path: Path,
) -> None:
    """Write a .ass file containing only the cues that overlap [clip_start, clip_end].

    Times are normalized so the clip's first cue starts near 0:00:00.
    """
    lines: list[str] = [ASS_HEADER]
    for cue in cues:
        if cue.end <= clip_start or cue.start >= clip_end:
            continue
        local_start = max(0.0, cue.start - clip_start)
        local_end = min(clip_end - clip_start, cue.end - clip_start)
        text = cue.text.replace("\n", " ").replace(",", "\\,")
        lines.append(
            f"Dialogue: 0,{_seconds_to_ass_ts(local_start)},"
            f"{_seconds_to_ass_ts(local_end)},Default,,0,0,0,,{text}"
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")


async def _ffmpeg_render_with_subs(
    source: Path, start: float, end: float, vf_with_subs: str, out: Path,
) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-ss", str(start),
        "-to", str(end),
        "-i", str(source),
        "-vf", vf_with_subs,
        "-c:v", "libx264", "-crf", "18", "-preset", "slow",
        "-c:a", "aac", "-b:a", "192k",
        str(out),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg final render failed: {stderr.decode()[:500]}")


async def render_one_final(
    candidate: CandidateClip,
    candidate_id: str,
    source: Path,
    cues: list[TranscriptCue],
    user_id: str,
    job_id: str,
    tmp_dir: Path,
) -> str:
    """Render full-quality vertical clip with burned-in captions. Returns storage key."""
    ass_path = tmp_dir / f"{candidate_id}.ass"
    out_path = tmp_dir / f"{candidate_id}_final.mp4"

    build_ass_file(cues, candidate.start_seconds, candidate.end_seconds, ass_path)
    width, height = _video_dims(source)
    track = detect_face_track(source, candidate.duration_seconds)
    crop_scale = build_crop_filter(track=track, video_height=height, video_width=width)
    # ffmpeg subtitles filter takes the .ass path; escape special chars for filter args
    ass_escaped = str(ass_path).replace(":", "\\:").replace("'", "\\'")
    vf = f"{crop_scale},subtitles='{ass_escaped}'"

    await _ffmpeg_render_with_subs(
        source, candidate.start_seconds, candidate.end_seconds, vf, out_path
    )
    key = final_key(user_id, job_id, candidate_id)
    await upload_file(out_path, key, "video/mp4")
    return key
