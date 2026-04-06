import pytest
from unittest.mock import patch, MagicMock
from services.nano_banana import generate_thumbnail


@pytest.mark.asyncio
async def test_generate_thumbnail_returns_image_bytes():
    mock_image = MagicMock()
    mock_image_bytes = b"\x89PNG\r\n\x1a\nfake-png-data"

    mock_image.save = MagicMock(
        side_effect=lambda buf, format: buf.write(mock_image_bytes)
    )

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


@pytest.mark.asyncio
async def test_generate_thumbnail_picks_first_image_from_multiple_parts():
    first_image_bytes = b"\x89PNG\r\n\x1a\nfirst-image"
    second_image_bytes = b"\x89PNG\r\n\x1a\nsecond-image"

    mock_image_1 = MagicMock()
    mock_image_1.save = MagicMock(
        side_effect=lambda buf, format: buf.write(first_image_bytes)
    )
    mock_image_2 = MagicMock()
    mock_image_2.save = MagicMock(
        side_effect=lambda buf, format: buf.write(second_image_bytes)
    )

    mock_part_text = MagicMock()
    mock_part_text.inline_data = None

    mock_part_img1 = MagicMock()
    mock_part_img1.inline_data = True
    mock_part_img1.as_image.return_value = mock_image_1

    mock_part_img2 = MagicMock()
    mock_part_img2.inline_data = True
    mock_part_img2.as_image.return_value = mock_image_2

    mock_response = MagicMock()
    mock_response.parts = [mock_part_text, mock_part_img1, mock_part_img2]

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("services.nano_banana.genai.Client", return_value=mock_client):
        with patch("services.nano_banana.settings") as mock_settings:
            mock_settings.gemini_api_key = "test-key"
            result = await generate_thumbnail(
                prompt="test prompt",
                reference_images=[],
                personal_photos=[],
                font_files=[],
            )

    # Should return the first image part found
    assert result == first_image_bytes


@pytest.mark.asyncio
async def test_generate_thumbnail_empty_parts_list():
    mock_response = MagicMock()
    mock_response.parts = []

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


@pytest.mark.asyncio
async def test_generate_thumbnail_builds_contents_with_all_assets():
    mock_image_bytes = b"\x89PNG\r\n\x1a\nfake"
    mock_image = MagicMock()
    mock_image.save = MagicMock(
        side_effect=lambda buf, format: buf.write(mock_image_bytes)
    )

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
            await generate_thumbnail(
                prompt="Generate a thumbnail",
                reference_images=[b"ref1", b"ref2"],
                personal_photos=[b"photo1"],
                font_files=[b"font1"],
            )

    call_args = mock_client.models.generate_content.call_args
    contents = call_args[1]["contents"]
    # Should contain: ref text + 2 refs + photo text + 1 photo + font text + 1 font + prompt
    assert len(contents) == 8
    assert contents[0] == "Here are my reference thumbnails for style inspiration:"
    assert contents[-1] == "Generate a thumbnail"


@pytest.mark.asyncio
async def test_generate_thumbnail_no_assets_prompt_only():
    """With no assets, contents should just be the prompt."""
    mock_image_bytes = b"\x89PNG\r\n\x1a\nfake"
    mock_image = MagicMock()
    mock_image.save = MagicMock(
        side_effect=lambda buf, format: buf.write(mock_image_bytes)
    )

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
            await generate_thumbnail(
                prompt="Just generate something",
                reference_images=[],
                personal_photos=[],
                font_files=[],
            )

    call_args = mock_client.models.generate_content.call_args
    contents = call_args[1]["contents"]
    assert len(contents) == 1
    assert contents[0] == "Just generate something"


@pytest.mark.asyncio
async def test_generate_thumbnail_only_reference_images():
    """With only reference images, contents should have ref text + images + prompt."""
    mock_image_bytes = b"\x89PNG\r\n\x1a\nfake"
    mock_image = MagicMock()
    mock_image.save = MagicMock(
        side_effect=lambda buf, format: buf.write(mock_image_bytes)
    )

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
            await generate_thumbnail(
                prompt="Make a thumbnail",
                reference_images=[b"ref1"],
                personal_photos=[],
                font_files=[],
            )

    call_args = mock_client.models.generate_content.call_args
    contents = call_args[1]["contents"]
    # ref text + 1 ref image + prompt
    assert len(contents) == 3
    assert contents[0] == "Here are my reference thumbnails for style inspiration:"
    assert contents[-1] == "Make a thumbnail"


@pytest.mark.asyncio
async def test_generate_thumbnail_only_personal_photos():
    """With only personal photos, contents should have photo text + images + prompt."""
    mock_image_bytes = b"\x89PNG\r\n\x1a\nfake"
    mock_image = MagicMock()
    mock_image.save = MagicMock(
        side_effect=lambda buf, format: buf.write(mock_image_bytes)
    )

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
            await generate_thumbnail(
                prompt="Make a thumbnail",
                reference_images=[],
                personal_photos=[b"photo1", b"photo2"],
                font_files=[],
            )

    call_args = mock_client.models.generate_content.call_args
    contents = call_args[1]["contents"]
    # photo text + 2 photos + prompt
    assert len(contents) == 4
    assert (
        contents[0]
        == "Here are my personal photos. Pick the best one for this thumbnail:"
    )


@pytest.mark.asyncio
async def test_generate_thumbnail_uses_correct_model():
    """Should use gemini-2.5-flash-preview-image-generation model."""
    mock_image_bytes = b"\x89PNG\r\n\x1a\nfake"
    mock_image = MagicMock()
    mock_image.save = MagicMock(
        side_effect=lambda buf, format: buf.write(mock_image_bytes)
    )

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
            await generate_thumbnail(
                prompt="test",
                reference_images=[],
                personal_photos=[],
                font_files=[],
            )

    call_args = mock_client.models.generate_content.call_args
    assert call_args[1]["model"] == "gemini-2.5-flash-preview-image-generation"
