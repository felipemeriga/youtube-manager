"""Shared yt-dlp argument builder.

YouTube bot-blocks server IPs with ``Sign in to confirm you're not a bot``.
We bypass this with client spoofing and optional residential proxy rotation.
Cookie/browser auth is available as a local dev fallback only.

Auth modes (configured via YOUTUBE_AUTH_MODE):
- ""        (default): no auth — relies on client spoofing + optional proxy
- "cookies": Netscape-format cookies file (local dev only, expires quickly)
- "browser": pull cookies from a local browser (only works on desktop)
"""

from __future__ import annotations

import logging
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

# Anchor relative paths at the backend/ directory (parent of services/).
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent

_logged_once = False


def _log_once(msg: str) -> None:
    global _logged_once
    if _logged_once:
        return
    _logged_once = True
    logger.info(msg)


def _resolve_cookies_file(raw: str) -> str | None:
    """Resolve a cookies-file setting to an absolute path. Returns None if the
    file does not exist (logged at WARNING level so misconfig is visible)."""
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = _BACKEND_ROOT / p
    if not p.is_file():
        logger.warning(
            "youtube_cookies_file=%r resolved to %s which does not exist — "
            "yt-dlp will fall through to other auth or fail with bot challenge",
            raw,
            p,
        )
        return None
    return str(p)


_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def ytdlp_auth_args() -> list[str]:
    """Return the auth and runtime flags to splice into a yt-dlp argv."""
    args: list[str] = [
        # Allow yt-dlp to download remote JS challenge solver components.
        "--remote-components", "ejs:github",
        # Do NOT override player_client. As of yt-dlp 2026.03+, the default
        # client mix (android_vr + web_safari) returns full-quality streams
        # anonymously for server IPs. Forcing `tv` triggers a broken OAuth
        # path; forcing `web,mweb` throttles to low-res single-file streams.
        "--user-agent", _CHROME_UA,
    ]

    # Optional residential proxy for bot bypass.
    proxy_url = (settings.youtube_proxy_url or "").strip()
    if proxy_url:
        args += ["--proxy", proxy_url]
        _log_once(f"yt-dlp: using proxy {proxy_url[:30]}…")

    mode = (settings.youtube_auth_mode or "").strip().lower()

    if mode == "cookies":
        cookies_file_raw = (settings.youtube_cookies_file or "").strip()
        if cookies_file_raw:
            resolved = _resolve_cookies_file(cookies_file_raw)
            if resolved:
                _log_once(f"yt-dlp auth: using cookies file {resolved}")
                return args + ["--cookies", resolved]

    if mode == "browser":
        browser = (settings.youtube_cookies_from_browser or "").strip()
        if browser:
            _log_once(f"yt-dlp auth: using cookies from browser {browser!r}")
            return args + ["--cookies-from-browser", browser]

    _log_once("yt-dlp auth: none (client spoofing + proxy only)")
    return args
