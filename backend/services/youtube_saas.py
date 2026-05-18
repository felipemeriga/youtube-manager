"""YouTube data client — RapidAPI ``youtube-media-downloader``.

Replaces the previous yt-dlp integration after YouTube began bot-blocking
unauthenticated requests from datacenter IPs. The SaaS provider handles the
IP-reputation problem on their side; we just make HTTP calls.

A single ``GET /v2/video/details`` request returns metadata, adaptive video
formats, audio formats, and auto-caption URLs in one payload. All URLs in
the response are short-lived (signed, expire in a few hours) — callers must
download immediately and not cache them.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from config import settings

logger = logging.getLogger(__name__)

_API_HOST = "youtube-media-downloader.p.rapidapi.com"
_API_BASE = f"https://{_API_HOST}"
_HTTP_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
_DOWNLOAD_TIMEOUT = httpx.Timeout(300.0, connect=10.0)

# Standard YouTube URL forms that embed an 11-char video id.
_YT_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)
_BARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(url_or_id: str) -> str:
    """Return the 11-char YouTube video id from a URL or pass through a bare id."""
    if _BARE_ID_RE.match(url_or_id):
        return url_or_id
    m = _YT_ID_RE.search(url_or_id)
    if not m:
        raise ValueError(f"Could not parse YouTube video id from {url_or_id!r}")
    return m.group(1)


@dataclass
class VideoInfo:
    video_id: str
    title: str
    duration_seconds: int
    video_url: str  # adaptive video stream (no audio) — prefer 1080p mp4
    audio_url: str  # adaptive audio stream — prefer m4a/AAC
    caption_url: str | None  # auto-caption timedtext URL, or None
    caption_lang: str | None


def _headers() -> dict[str, str]:
    key = (settings.rapidapi_key or "").strip()
    if not key:
        raise RuntimeError("RAPIDAPI_KEY is not configured")
    return {"x-rapidapi-host": _API_HOST, "x-rapidapi-key": key}


def _quality_rank(quality: str | None) -> int:
    if not quality:
        return 0
    m = re.match(r"(\d+)", quality)
    return int(m.group(1)) if m else 0


def _pick_best_video(items: list[dict]) -> dict:
    """Prefer adaptive 1080p mp4 (h264) for clean ffmpeg `-c copy` muxing.

    Fallback chain: 1080p+ mp4 → best mp4 we have → any item. We avoid webm
    because muxing webm video with aac audio into mp4 requires re-encoding.
    """
    mp4_items = [v for v in items if v.get("extension") == "mp4"]
    mp4_items.sort(key=lambda v: _quality_rank(v.get("quality")), reverse=True)
    for v in mp4_items:
        if _quality_rank(v.get("quality")) >= 1080:
            return v
    if mp4_items:
        return mp4_items[0]
    return items[0]


def _pick_best_audio(items: list[dict]) -> dict:
    """Prefer audio/mp4 (AAC) for clean mp4 muxing; pick highest bitrate variant."""
    m4a = [a for a in items if "mp4" in (a.get("mimeType") or "")]
    if m4a:
        m4a.sort(key=lambda a: a.get("size") or 0, reverse=True)
        return m4a[0]
    return items[0]


def _pick_caption(items: list[dict]) -> dict | None:
    """Prefer English when available, otherwise return the first auto-caption."""
    if not items:
        return None
    for code in ("en", "en-US", "en-GB"):
        for s in items:
            if s.get("code") == code:
                return s
    return items[0]


async def fetch_video_info(url_or_id: str) -> VideoInfo:
    """Fetch metadata + adaptive download URLs + auto-caption URL in one call.

    All returned URLs are signed and expire within hours — download
    immediately, don't cache. Raises RuntimeError on API failure or when
    no downloadable formats are returned.
    """
    video_id = extract_video_id(url_or_id)
    params = {
        "videoId": video_id,
        "urlAccess": "normal",
        "videos": "auto",
        "audios": "auto",
        "subtitles": "true",
    }
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        r = await client.get(
            f"{_API_BASE}/v2/video/details", headers=_headers(), params=params
        )
    if r.status_code != 200:
        raise RuntimeError(
            f"youtube_saas fetch_video_info failed: HTTP {r.status_code} — "
            f"{r.text[:300]}"
        )
    d = r.json()
    err = d.get("errorId")
    if err and err != "Success":
        raise RuntimeError(f"youtube_saas fetch_video_info error: {err}")
    videos = (d.get("videos") or {}).get("items") or []
    audios = (d.get("audios") or {}).get("items") or []
    subtitles = (d.get("subtitles") or {}).get("items") or []
    if not videos or not audios:
        raise RuntimeError(f"youtube_saas: no downloadable formats for {video_id}")

    v = _pick_best_video(videos)
    a = _pick_best_audio(audios)
    cap = _pick_caption(subtitles)

    return VideoInfo(
        video_id=video_id,
        title=d.get("title") or "",
        duration_seconds=int(d.get("lengthSeconds") or 0),
        video_url=v["url"],
        audio_url=a["url"],
        caption_url=(cap or {}).get("url"),
        caption_lang=(cap or {}).get("code"),
    )


async def _stream_to_file(url: str, dest: Path) -> None:
    """Stream-download a URL to a local file without buffering it in memory.

    ``follow_redirects=True`` is required because YouTube's googlevideo CDN
    returns 302s to redistribute load across edge servers.
    """
    async with httpx.AsyncClient(
        timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True
    ) as client:
        async with client.stream("GET", url) as r:
            r.raise_for_status()
            with dest.open("wb") as f:
                async for chunk in r.aiter_bytes(chunk_size=1 << 16):
                    f.write(chunk)


async def download_video_and_audio(info: VideoInfo, dest_mp4: Path) -> None:
    """Download the adaptive video + audio streams and mux them into one MP4.

    Uses ``ffmpeg -c copy`` so no re-encoding happens — fast and lossless.
    The temporary stream files are removed even when muxing fails.
    """
    tmp_v = dest_mp4.parent / f".{dest_mp4.stem}.v.mp4"
    tmp_a = dest_mp4.parent / f".{dest_mp4.stem}.a.m4a"
    try:
        await _stream_to_file(info.video_url, tmp_v)
        await _stream_to_file(info.audio_url, tmp_a)
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-i",
            str(tmp_v),
            "-i",
            str(tmp_a),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(dest_mp4),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg mux failed: {stderr.decode(errors='replace')[-500:]}"
            )
    finally:
        for p in (tmp_v, tmp_a):
            try:
                p.unlink()
            except FileNotFoundError:
                pass


async def fetch_captions_json3(info: VideoInfo) -> dict | None:
    """Fetch auto-captions in YouTube's JSON3 format. Returns None if unavailable.

    JSON3 has clean per-event word lists without the rolling-overlap pattern
    that the VTT format would force us to dedupe. The parsing into cues lives
    in the transcript service so we can keep ``parse_vtt`` free of YouTube
    specifics.
    """
    if not info.caption_url:
        return None
    url = info.caption_url
    sep = "&" if "?" in url else "?"
    if "fmt=" not in url:
        url = f"{url}{sep}fmt=json3"
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        r = await client.get(url)
    if r.status_code != 200 or not r.text.strip():
        logger.warning(
            "youtube_saas: caption fetch returned HTTP %s for %s",
            r.status_code,
            info.video_id,
        )
        return None
    try:
        return r.json()
    except Exception:
        logger.warning("youtube_saas: caption response was not valid JSON")
        return None
