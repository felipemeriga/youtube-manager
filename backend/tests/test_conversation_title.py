"""Tests for the conversation title helper."""

from services.conversation_title import derive_title


def test_short_message_returned_as_is():
    assert derive_title("Make a thumbnail") == "Make a thumbnail"


def test_collapses_internal_whitespace():
    assert derive_title("Hello\n\nworld\t  again") == "Hello world again"


def test_strips_outer_whitespace():
    assert derive_title("   spaced  ") == "spaced"


def test_long_message_truncated_at_word_boundary():
    msg = (
        "Create a thumbnail for my new video about the latest AI models and what they "
        "mean for content creators in 2026"
    )
    title = derive_title(msg, max_len=60)
    # Must fit within max length
    assert len(title) <= 60
    # Must end with the single-char ellipsis (not three dots) and break on word
    assert title.endswith("\u2026")
    assert " " in title
    # Last char before ellipsis is not whitespace
    assert title[-2] != " "


def test_long_message_with_no_whitespace_falls_back_to_hard_truncate():
    msg = "x" * 200
    title = derive_title(msg, max_len=20)
    assert len(title) == 20
    assert title.endswith("\u2026")


def test_empty_message_returns_fallback():
    assert derive_title("") == "Nova conversa"
    assert derive_title("   \n\t ") == "Nova conversa"


def test_exactly_max_length_unchanged():
    msg = "a" * 60
    assert derive_title(msg, max_len=60) == msg
