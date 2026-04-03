import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO

from services.nano_banana import generate_thumbnail


@pytest.mark.asyncio
async def test_generate_thumbnail_returns_image_bytes():
    mock_image = MagicMock()
    mock_image_bytes = b"\x89PNG\r\n\x1a\nfake-png-data"

    mock_buffer = BytesIO(mock_image_bytes)
    mock_image.save = MagicMock(side_effect=lambda buf, format: buf.write(mock_image_bytes))

    mock_part = MagicMock()
    mock_part.inline_data = True
    mock_part.as_image.return_value = mock_image

    mock_response = MagicMock()
    mock_response.parts = [mock_part]

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("services.nano_banana.genai.Client", return_value=mock_client):
        with patch("services.nano_banana.settings") as mock_settings:
            mock_settings.gemini_api_key = "test-key"
            result = await generate_thumbnail(
                prompt="A tech-style YouTube thumbnail with Python code background",
                reference_images=[b"ref-image-1-bytes"],
                personal_photos=[b"photo-1-bytes"],
                font_files=[b"font-1-bytes"],
            )

    assert result is not None
    assert isinstance(result, bytes)
    mock_client.models.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_generate_thumbnail_no_image_in_response():
    mock_part = MagicMock()
    mock_part.inline_data = None

    mock_response = MagicMock()
    mock_response.parts = [mock_part]

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("services.nano_banana.genai.Client", return_value=mock_client):
        with patch("services.nano_banana.settings") as mock_settings:
            mock_settings.gemini_api_key = "test-key"
            with pytest.raises(Exception, match="No image generated"):
                await generate_thumbnail(
                    prompt="test prompt",
                    reference_images=[],
                    personal_photos=[],
                    font_files=[],
                )
