"""Unit tests for services/reference_analyzer.py.

Tests cover analyze_references using mocked Anthropic client — no real API calls.
"""

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.reference_analyzer import ANALYSIS_SYSTEM, analyze_references

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

JPEG_MAGIC = b"\xff\xd8\xff" + b"\x00" * 10
PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 10
WEBP_MAGIC = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 10


def _make_mock_response(text: str) -> MagicMock:
    """Build a mock Anthropic messages.create response with a single text block."""
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


def _valid_style_json() -> dict:
    return {
        "person_position": "right",
        "person_size_pct": 70,
        "person_vertical": "bottom-aligned",
        "text_position": "left",
        "text_vertical": "top",
        "text_color": "#FFFFFF",
        "text_stroke": True,
        "text_stroke_color": "#000000",
        "text_stroke_width": 2,
        "text_shadow": False,
        "text_size_ratio": 0.1,
        "text_max_width_ratio": 0.5,
        "logo_position": "top-left",
        "logo_size_ratio": 0.08,
    }


# ---------------------------------------------------------------------------
# Tests: early-exit conditions
# ---------------------------------------------------------------------------


class TestAnalyzeReferencesEarlyExit:
    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_api_key(self):
        """analyze_references must return {} when anthropic_api_key is falsy."""
        with patch("services.reference_analyzer.settings") as mock_settings:
            mock_settings.anthropic_api_key = ""
            result = await analyze_references([JPEG_MAGIC])
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_api_key_is_none(self):
        with patch("services.reference_analyzer.settings") as mock_settings:
            mock_settings.anthropic_api_key = None
            result = await analyze_references([JPEG_MAGIC])
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_images(self):
        """analyze_references must return {} when the image list is empty."""
        with patch("services.reference_analyzer.settings") as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            result = await analyze_references([])
        assert result == {}


# ---------------------------------------------------------------------------
# Tests: Anthropic client invocation
# ---------------------------------------------------------------------------


class TestAnalyzeReferencesApiCall:
    @pytest.mark.asyncio
    async def test_calls_anthropic_with_correct_model(self):
        """The function must use the claude-haiku-4-5 model."""
        mock_create = AsyncMock(
            return_value=_make_mock_response(json.dumps(_valid_style_json()))
        )
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        with (
            patch("services.reference_analyzer.settings") as mock_settings,
            patch(
                "services.reference_analyzer.AsyncAnthropic",
                return_value=mock_client,
            ),
        ):
            mock_settings.anthropic_api_key = "test-key"
            await analyze_references([JPEG_MAGIC])

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"

    @pytest.mark.asyncio
    async def test_calls_anthropic_with_correct_system_prompt(self):
        """The ANALYSIS_SYSTEM constant must be passed as the system argument."""
        mock_create = AsyncMock(
            return_value=_make_mock_response(json.dumps(_valid_style_json()))
        )
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        with (
            patch("services.reference_analyzer.settings") as mock_settings,
            patch(
                "services.reference_analyzer.AsyncAnthropic",
                return_value=mock_client,
            ),
        ):
            mock_settings.anthropic_api_key = "test-key"
            await analyze_references([JPEG_MAGIC])

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["system"] == ANALYSIS_SYSTEM

    @pytest.mark.asyncio
    async def test_passes_images_as_base64_in_content(self):
        """Each image should appear as a base64-encoded block in the message content."""
        mock_create = AsyncMock(
            return_value=_make_mock_response(json.dumps(_valid_style_json()))
        )
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        with (
            patch("services.reference_analyzer.settings") as mock_settings,
            patch(
                "services.reference_analyzer.AsyncAnthropic",
                return_value=mock_client,
            ),
        ):
            mock_settings.anthropic_api_key = "test-key"
            await analyze_references([JPEG_MAGIC])

        call_kwargs = mock_create.call_args.kwargs
        content = call_kwargs["messages"][0]["content"]
        image_blocks = [b for b in content if b.get("type") == "image"]
        assert len(image_blocks) == 1
        expected_b64 = base64.standard_b64encode(JPEG_MAGIC).decode()
        assert image_blocks[0]["source"]["data"] == expected_b64


# ---------------------------------------------------------------------------
# Tests: JSON parsing
# ---------------------------------------------------------------------------


class TestAnalyzeReferencesJsonParsing:
    @pytest.mark.asyncio
    async def test_parses_valid_json_response(self):
        """A clean JSON string in the response must be returned as a dict."""
        expected = _valid_style_json()
        mock_create = AsyncMock(return_value=_make_mock_response(json.dumps(expected)))
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        with (
            patch("services.reference_analyzer.settings") as mock_settings,
            patch(
                "services.reference_analyzer.AsyncAnthropic",
                return_value=mock_client,
            ),
        ):
            mock_settings.anthropic_api_key = "test-key"
            result = await analyze_references([JPEG_MAGIC])

        assert result == expected

    @pytest.mark.asyncio
    async def test_parses_json_wrapped_in_markdown_code_block(self):
        """JSON wrapped in ```json ... ``` must be stripped and parsed."""
        expected = _valid_style_json()
        wrapped = f"```json\n{json.dumps(expected)}\n```"
        mock_create = AsyncMock(return_value=_make_mock_response(wrapped))
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        with (
            patch("services.reference_analyzer.settings") as mock_settings,
            patch(
                "services.reference_analyzer.AsyncAnthropic",
                return_value=mock_client,
            ),
        ):
            mock_settings.anthropic_api_key = "test-key"
            result = await analyze_references([JPEG_MAGIC])

        assert result == expected

    @pytest.mark.asyncio
    async def test_parses_json_wrapped_in_plain_code_block(self):
        """JSON wrapped in ``` ... ``` (no language tag) must also parse correctly."""
        expected = _valid_style_json()
        wrapped = f"```\n{json.dumps(expected)}\n```"
        mock_create = AsyncMock(return_value=_make_mock_response(wrapped))
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        with (
            patch("services.reference_analyzer.settings") as mock_settings,
            patch(
                "services.reference_analyzer.AsyncAnthropic",
                return_value=mock_client,
            ),
        ):
            mock_settings.anthropic_api_key = "test-key"
            result = await analyze_references([JPEG_MAGIC])

        assert result == expected

    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_invalid_json_response(self):
        """Unparseable text in the response must result in {}."""
        mock_create = AsyncMock(
            return_value=_make_mock_response("This is not JSON at all.")
        )
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        with (
            patch("services.reference_analyzer.settings") as mock_settings,
            patch(
                "services.reference_analyzer.AsyncAnthropic",
                return_value=mock_client,
            ),
        ):
            mock_settings.anthropic_api_key = "test-key"
            result = await analyze_references([JPEG_MAGIC])

        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_truncated_json(self):
        """Truncated/partial JSON must result in {}."""
        mock_create = AsyncMock(
            return_value=_make_mock_response('{"person_position": "right"')
        )
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        with (
            patch("services.reference_analyzer.settings") as mock_settings,
            patch(
                "services.reference_analyzer.AsyncAnthropic",
                return_value=mock_client,
            ),
        ):
            mock_settings.anthropic_api_key = "test-key"
            result = await analyze_references([JPEG_MAGIC])

        assert result == {}


# ---------------------------------------------------------------------------
# Tests: API error handling
# ---------------------------------------------------------------------------


class TestAnalyzeReferencesErrorHandling:
    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_api_error(self):
        """An exception from the Anthropic client must result in {}."""
        mock_create = AsyncMock(side_effect=Exception("API unavailable"))
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        with (
            patch("services.reference_analyzer.settings") as mock_settings,
            patch(
                "services.reference_analyzer.AsyncAnthropic",
                return_value=mock_client,
            ),
        ):
            mock_settings.anthropic_api_key = "test-key"
            result = await analyze_references([JPEG_MAGIC])

        assert result == {}


# ---------------------------------------------------------------------------
# Tests: MIME type detection
# ---------------------------------------------------------------------------


class TestMimeTypeDetection:
    async def _get_mime_for_image(self, image_bytes: bytes) -> str:
        """Helper: invoke analyze_references and capture the mime type sent."""
        mock_create = AsyncMock(
            return_value=_make_mock_response(json.dumps(_valid_style_json()))
        )
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        with (
            patch("services.reference_analyzer.settings") as mock_settings,
            patch(
                "services.reference_analyzer.AsyncAnthropic",
                return_value=mock_client,
            ),
        ):
            mock_settings.anthropic_api_key = "test-key"
            await analyze_references([image_bytes])

        call_kwargs = mock_create.call_args.kwargs
        content = call_kwargs["messages"][0]["content"]
        image_blocks = [b for b in content if b.get("type") == "image"]
        return image_blocks[0]["source"]["media_type"]

    @pytest.mark.asyncio
    async def test_detects_jpeg_mime_type(self):
        """Images starting with \\xff\\xd8\\xff must be detected as image/jpeg."""
        mime = await self._get_mime_for_image(JPEG_MAGIC)
        assert mime == "image/jpeg"

    @pytest.mark.asyncio
    async def test_detects_png_mime_type(self):
        """Images starting with \\x89PNG must be detected as image/png."""
        mime = await self._get_mime_for_image(PNG_MAGIC)
        assert mime == "image/png"

    @pytest.mark.asyncio
    async def test_detects_webp_mime_type(self):
        """Images with RIFF...WEBP header must be detected as image/webp."""
        mime = await self._get_mime_for_image(WEBP_MAGIC)
        assert mime == "image/webp"

    @pytest.mark.asyncio
    async def test_unknown_format_falls_back_to_jpeg(self):
        """Unrecognised magic bytes should fall back to image/jpeg."""
        unknown = b"\x00\x01\x02\x03" + b"\x00" * 20
        mime = await self._get_mime_for_image(unknown)
        assert mime == "image/jpeg"


# ---------------------------------------------------------------------------
# Tests: image count limit
# ---------------------------------------------------------------------------


class TestImageLimit:
    @pytest.mark.asyncio
    async def test_limits_to_six_reference_images(self):
        """More than 6 images must be silently truncated to 6."""
        mock_create = AsyncMock(
            return_value=_make_mock_response(json.dumps(_valid_style_json()))
        )
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        images = [JPEG_MAGIC] * 10  # supply 10, expect only 6 sent

        with (
            patch("services.reference_analyzer.settings") as mock_settings,
            patch(
                "services.reference_analyzer.AsyncAnthropic",
                return_value=mock_client,
            ),
        ):
            mock_settings.anthropic_api_key = "test-key"
            await analyze_references(images)

        call_kwargs = mock_create.call_args.kwargs
        content = call_kwargs["messages"][0]["content"]
        image_blocks = [b for b in content if b.get("type") == "image"]
        assert len(image_blocks) == 6

    @pytest.mark.asyncio
    async def test_exactly_six_images_are_all_sent(self):
        """Exactly 6 images must all appear in the API call."""
        mock_create = AsyncMock(
            return_value=_make_mock_response(json.dumps(_valid_style_json()))
        )
        mock_client = MagicMock()
        mock_client.messages.create = mock_create

        images = [JPEG_MAGIC] * 6

        with (
            patch("services.reference_analyzer.settings") as mock_settings,
            patch(
                "services.reference_analyzer.AsyncAnthropic",
                return_value=mock_client,
            ),
        ):
            mock_settings.anthropic_api_key = "test-key"
            await analyze_references(images)

        call_kwargs = mock_create.call_args.kwargs
        content = call_kwargs["messages"][0]["content"]
        image_blocks = [b for b in content if b.get("type") == "image"]
        assert len(image_blocks) == 6
