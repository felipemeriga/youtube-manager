import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_describe_photo_calls_haiku_vision():
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text="Man with confident expression, arms crossed")
    ]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with (
        patch("services.photo_indexer.AsyncAnthropic", return_value=mock_client),
        patch("services.photo_indexer.settings") as mock_settings,
    ):
        mock_settings.anthropic_api_key = "sk-test"

        from services.photo_indexer import describe_photo

        result = await describe_photo(b"fake-image-bytes")

    assert result == "Man with confident expression, arms crossed"
    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"


@pytest.mark.asyncio
async def test_index_photo_stores_in_db():
    mock_sb = MagicMock()
    mock_sb.table.return_value.upsert.return_value.execute = AsyncMock()

    with (
        patch(
            "services.photo_indexer.describe_photo",
            new_callable=AsyncMock,
            return_value="Confident man",
        ),
        patch("services.photo_indexer.embed_text", return_value=[0.1] * 1024),
    ):
        from services.photo_indexer import index_photo

        await index_photo(mock_sb, "user-1", "photo.jpg", b"fake")

    mock_sb.table.return_value.upsert.assert_called_once()
    upsert_data = mock_sb.table.return_value.upsert.call_args[0][0]
    assert upsert_data["user_id"] == "user-1"
    assert upsert_data["file_name"] == "photo.jpg"
    assert upsert_data["description"] == "Confident man"
    assert len(upsert_data["embedding"]) == 1024
