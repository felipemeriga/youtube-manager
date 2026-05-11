"""Shared yt-dlp argument builder.

YouTube has started bot-blocking server IPs with the error
``Sign in to confirm you're not a bot``. The fix is to pass either a cookies
file or a browser-cookie source to every yt-dlp invocation. This helper
centralises that so the three call sites (metadata, download, transcript)
stay in sync.

Resolves relative cookie-file paths to absolute paths anchored at the backend
package root, so ``YOUTUBE_COOKIES_FILE=cookies.txt`` works regardless of the
process CWD. Logs the auth mode on first use so configuration mistakes are
visible in startup logs rather than masked as "still bot-blocked".
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


def ytdlp_auth_args() -> list[str]:
    """Return the auth flags to splice into a yt-dlp argv.

    Priority: explicit cookies file (if it exists) > browser source > no auth.
    A missing/empty cookies file does NOT block fallback to the browser
    source, so an env with both set still works when the file is wrong.
    """
    cookies_file_raw = (settings.youtube_cookies_file or "").strip()
    if cookies_file_raw:
        resolved = _resolve_cookies_file(cookies_file_raw)
        if resolved:
            _log_once(f"yt-dlp auth: using cookies file {resolved}")
            return ["--cookies", resolved]
    browser = (settings.youtube_cookies_from_browser or "").strip()
    if browser:
        _log_once(f"yt-dlp auth: using cookies from browser {browser!r}")
        return ["--cookies-from-browser", browser]
    _log_once(
        "yt-dlp auth: NONE configured (set YOUTUBE_COOKIES_FILE or "
        "YOUTUBE_COOKIES_FROM_BROWSER to bypass YouTube bot challenge)"
    )
    return []
