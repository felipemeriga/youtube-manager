import pytest
from unittest.mock import patch, MagicMock
from services.nano_banana import generate_thumbnail


def make_mock_client(image_bytes=b"\x89PNG\r\n\x1a\nfake-png-data", has_image=True):
    mock_image = MagicMock()
    mock_image.image_bytes = image_bytes

    mock_part = MagicMock()
    mock_part.inline_data = True if has_image else None
    mock_part.as_image.return_value = mock_image

    mock_response = MagicMock()
    mock_response.parts = [mock_part]

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    return mock_client


@pytest.mark.asyncio
async def test_generate_thumbnail_returns_image_bytes():
    mock_client = make_mock_client()

    with patch("services.nano_banana.genai.Client", return_value=mock_client):
        with patch("services.nano_banana.settings") as mock_settings:
            mock_settings.gemini_api_key = "test-key"
            result = await generate_thumbnail(
                prompt="A tech-style YouTube thumbnail",
                reference_images=[b"ref-image-1-bytes"],
                personal_photos=[b"photo-1-bytes"],
            )

    assert result is not None
    assert isinstance(result, bytes)
    mock_client.models.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_generate_thumbnail_no_image_in_response():
    mock_client = make_mock_client(has_image=False)

    with patch("services.nano_banana.genai.Client", return_value=mock_client):
        with patch("services.nano_banana.settings") as mock_settings:
            mock_settings.gemini_api_key = "test-key"
            with pytest.raises(Exception, match="No image generated"):
                await generate_thumbnail(
                    prompt="test prompt",
                    reference_images=[],
                    personal_photos=[],
                )


@pytest.mark.asyncio
async def test_generate_thumbnail_picks_first_image():
    first_bytes = b"\x89PNG\r\n\x1a\nfirst-image"
    second_bytes = b"\x89PNG\r\n\x1a\nsecond-image"

    mock_image_1 = MagicMock()
    mock_image_1.image_bytes = first_bytes
    mock_image_2 = MagicMock()
    mock_image_2.image_bytes = second_bytes

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
            )

    assert result == first_bytes


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
                )


@pytest.mark.asyncio
async def test_generate_thumbnail_builds_contents_with_all_assets():
    mock_client = make_mock_client()

    with patch("services.nano_banana.genai.Client", return_value=mock_client):
        with patch("services.nano_banana.settings") as mock_settings:
            mock_settings.gemini_api_key = "test-key"
            await generate_thumbnail(
                prompt="Generate a thumbnail",
                reference_images=[b"ref1", b"ref2"],
                personal_photos=[b"photo1"],
                logos=[b"logo1"],
            )

    call_args = mock_client.models.generate_content.call_args
    contents = call_args[1]["contents"]
    # ref text + 2 refs + logo text + 1 logo + photo text + 1 photo + prompt
    assert len(contents) == 8
    assert contents[0] == "Here are my reference thumbnails for style inspiration:"
    assert contents[-1] == "Generate a thumbnail"


@pytest.mark.asyncio
async def test_generate_thumbnail_no_assets_prompt_only():
    mock_client = make_mock_client()

    with patch("services.nano_banana.genai.Client", return_value=mock_client):
        with patch("services.nano_banana.settings") as mock_settings:
            mock_settings.gemini_api_key = "test-key"
            await generate_thumbnail(
                prompt="Just generate something",
                reference_images=[],
                personal_photos=[],
            )

    call_args = mock_client.models.generate_content.call_args
    contents = call_args[1]["contents"]
    assert len(contents) == 1
    assert contents[0] == "Just generate something"


@pytest.mark.asyncio
async def test_generate_thumbnail_only_reference_images():
    mock_client = make_mock_client()

    with patch("services.nano_banana.genai.Client", return_value=mock_client):
        with patch("services.nano_banana.settings") as mock_settings:
            mock_settings.gemini_api_key = "test-key"
            await generate_thumbnail(
                prompt="Make a thumbnail",
                reference_images=[b"ref1"],
                personal_photos=[],
            )

    call_args = mock_client.models.generate_content.call_args
    contents = call_args[1]["contents"]
    # ref text + 1 ref image + prompt
    assert len(contents) == 3
    assert contents[0] == "Here are my reference thumbnails for style inspiration:"
    assert contents[-1] == "Make a thumbnail"


@pytest.mark.asyncio
async def test_generate_thumbnail_only_personal_photos():
    mock_client = make_mock_client()

    with patch("services.nano_banana.genai.Client", return_value=mock_client):
        with patch("services.nano_banana.settings") as mock_settings:
            mock_settings.gemini_api_key = "test-key"
            await generate_thumbnail(
                prompt="Make a thumbnail",
                reference_images=[],
                personal_photos=[b"photo1", b"photo2"],
            )

    call_args = mock_client.models.generate_content.call_args
    contents = call_args[1]["contents"]
    # photo text + 2 photos + prompt
    assert len(contents) == 4
    assert "personal photos" in contents[0].lower()


@pytest.mark.asyncio
async def test_generate_thumbnail_uses_correct_model():
    mock_client = make_mock_client()

    with patch("services.nano_banana.genai.Client", return_value=mock_client):
        with patch("services.nano_banana.settings") as mock_settings:
            mock_settings.gemini_api_key = "test-key"
            await generate_thumbnail(
                prompt="test",
                reference_images=[],
                personal_photos=[],
            )

    call_args = mock_client.models.generate_content.call_args
    assert call_args[1]["model"] == "gemini-3-pro-image-preview"
