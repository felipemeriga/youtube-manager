import asyncio
import logging
import subprocess
from pathlib import Path

from .face_detection import detect_face_track
from .models import CandidateClip
from .storage import preview_key, preview_poster_key, upload_file

logger = logging.getLogger(__name__)


def _video_dims(path: Path) -> tuple[int, int]:
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x",
            str(path),
        ]
    ).decode().strip()
    w, h = out.split("x")
    return int(w), int(h)


def build_crop_filter(
    track: list[tuple[float, int]],
    video_height: int,
    video_width: int,
) -> str:
    """Return the ffmpeg -vf string for a 9:16 vertical crop.

    Uses the median X from the smoothed track (avoids whipping). Clamps so the
    crop window stays inside the source frame.
    """
    crop_w = round(video_height * 9 / 16)
    if crop_w % 2:
        crop_w += 1
    if track:
        xs = sorted(int(p[1]) for p in track)
        cx = xs[len(xs) // 2]
    else:
        cx = video_width // 2
    x_offset = max(0, min(cx - crop_w // 2, video_width - crop_w))
    return f"crop={crop_w}:{video_height}:{x_offset}:0,scale=720:1280"


async def _ffmpeg_cut(source: Path, start: float, end: float, out: Path) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-ss", str(start),
        "-to", str(end),
        "-i", str(source),
        "-c", "copy",
        str(out),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg cut failed: {stderr.decode()[:500]}")


async def _ffmpeg_reframe(clip: Path, vf: str, out: Path) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-i", str(clip),
        "-vf", vf,
        "-c:v", "libx264", "-crf", "30", "-preset", "fast",
        "-c:a", "aac", "-b:a", "96k",
        str(out),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg reframe failed: {stderr.decode()[:500]}")


async def _ffmpeg_poster(clip: Path, out: Path) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-i", str(clip),
        "-ss", "0.5",
        "-vframes", "1",
        "-q:v", "3",
        str(out),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg poster failed: {stderr.decode()[:500]}")


async def render_one_preview(
    candidate: CandidateClip,
    candidate_id: str,
    source: Path,
    user_id: str,
    job_id: str,
    tmp_dir: Path,
) -> dict[str, str]:
    """Cut → reframe → poster → upload. Returns storage keys."""
    cut_path = tmp_dir / f"{candidate_id}_cut.mp4"
    preview_path = tmp_dir / f"{candidate_id}_preview.mp4"
    poster_path = tmp_dir / f"{candidate_id}.jpg"

    await _ffmpeg_cut(source, candidate.start_seconds, candidate.end_seconds, cut_path)
    width, height = _video_dims(cut_path)
    track = detect_face_track(cut_path, candidate.duration_seconds)
    vf = build_crop_filter(track=track, video_height=height, video_width=width)

    await _ffmpeg_reframe(cut_path, vf, preview_path)
    await _ffmpeg_poster(preview_path, poster_path)

    p_key = preview_key(user_id, job_id, candidate_id)
    pp_key = preview_poster_key(user_id, job_id, candidate_id)
    await upload_file(preview_path, p_key, "video/mp4")
    await upload_file(poster_path, pp_key, "image/jpeg")

    cut_path.unlink(missing_ok=True)
    return {"preview_storage_key": p_key, "preview_poster_key": pp_key}


async def render_all_previews(
    candidates: list[tuple[str, CandidateClip]],
    source: Path,
    user_id: str,
    job_id: str,
    tmp_dir: Path,
    max_concurrent: int = 3,
    on_progress=None,
) -> list[dict]:
    """Render previews concurrently. on_progress is called with (done, total)."""
    sem = asyncio.Semaphore(max_concurrent)
    total = len(candidates)
    done = 0
    results: list[dict] = []

    async def one(cid: str, cand: CandidateClip):
        nonlocal done
        async with sem:
            try:
                keys = await render_one_preview(
                    cand, cid, source, user_id, job_id, tmp_dir
                )
                results.append({"candidate_id": cid, **keys, "render_failed": False})
            except Exception as e:
                logger.exception("Preview render failed for candidate %s: %s", cid, e)
                results.append({"candidate_id": cid, "render_failed": True})
            finally:
                done += 1
                if on_progress:
                    on_progress(done, total)

    await asyncio.gather(*(one(cid, c) for cid, c in candidates))
    return results
