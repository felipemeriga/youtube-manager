"""Derive a short human-friendly conversation title from a user message."""

from __future__ import annotations

MAX_TITLE_LEN = 60


def derive_title(message: str, max_len: int = MAX_TITLE_LEN) -> str:
    """Return a tidy title for a conversation, derived from its first message.

    Rules:
    - Collapse internal whitespace (newlines, tabs, multiple spaces) to a single
      space.
    - Strip leading/trailing whitespace.
    - If the result fits in ``max_len``, return it as-is.
    - Otherwise, truncate at the last word boundary that fits within
      ``max_len - 1`` chars and append a single ellipsis character. If no
      whitespace exists in the prefix, hard-truncate.
    - If the input is empty or whitespace-only, fall back to ``"Nova conversa"``.
    """
    cleaned = " ".join(message.split()).strip()
    if not cleaned:
        return "Nova conversa"
    if len(cleaned) <= max_len:
        return cleaned

    # Reserve one character for the ellipsis.
    budget = max_len - 1
    prefix = cleaned[:budget]
    cut = prefix.rfind(" ")
    if cut > 0:
        prefix = prefix[:cut].rstrip()
    return f"{prefix}\u2026"
