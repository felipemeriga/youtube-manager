"""Shared yt-dlp argument builder.

YouTube has started bot-blocking server IPs with the error
``Sign in to confirm you're not a bot``. The fix is to pass either a cookies
file or a browser-cookie source to every yt-dlp invocation. This helper
centralises that so the three call sites (metadata, download, transcript)
stay in sync.
"""

from __future__ import annotations

from config import settings


def ytdlp_auth_args() -> list[str]:
    """Return the auth flags to splice into a yt-dlp argv.

    Priority: explicit cookies file > browser source > no auth (legacy path).
    """
    cookies_file = (settings.youtube_cookies_file or "").strip()
    if cookies_file:
        return ["--cookies", cookies_file]
    browser = (settings.youtube_cookies_from_browser or "").strip()
    if browser:
        return ["--cookies-from-browser", browser]
    return []
