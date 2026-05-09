"""Verify the URL-fetch path in openai_image uses an explicit httpx timeout."""
from unittest.mock import MagicMock, patch

import httpx


def test_url_path_uses_explicit_timeout():
    """When OpenAI returns a URL instead of b64, httpx.get must include a Timeout."""
    from services import openai_image

    captured: dict = {}

    def fake_get(url, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        m = MagicMock()
        m.content = b"image-bytes"
        m.raise_for_status = lambda: None
        return m

    item = MagicMock()
    item.b64_json = None
    item.url = "https://oai-cdn/x.png"

    with patch("httpx.get", side_effect=fake_get):
        result = openai_image._decode_response(MagicMock(data=[item]))

    assert result == b"image-bytes"
    timeout = captured.get("timeout")
    assert timeout is not None, "httpx.get must be called with explicit timeout"
    assert isinstance(timeout, httpx.Timeout), "timeout must be an httpx.Timeout instance"
