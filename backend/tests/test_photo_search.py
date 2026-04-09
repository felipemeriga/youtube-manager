import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_find_best_photos_returns_filenames():
    mock_sb = MagicMock()
    mock_sb.rpc.return_value.execute = AsyncMock(
        return_value=MagicMock(
            data=[
                {"file_name": "photo1.jpg", "description": "...", "similarity": 0.9},
                {"file_name": "photo2.jpg", "description": "...", "similarity": 0.8},
            ]
        )
    )

    mock_client = MagicMock()
    mock_client.embed.return_value = MagicMock(embeddings=[[0.1] * 1024])

    with (
        patch("services.photo_search.settings") as mock_settings,
        patch("services.photo_search.voyageai.Client", return_value=mock_client),
    ):
        mock_settings.voyage_api_key = "voy-test"

        from services.photo_search import find_best_photos

        result = await find_best_photos(mock_sb, "user-1", "confident tech talk")

    assert result == ["photo1.jpg", "photo2.jpg"]


@pytest.mark.asyncio
async def test_find_best_photos_returns_empty_when_no_key():
    mock_sb = MagicMock()

    with patch("services.photo_search.settings") as mock_settings:
        mock_settings.voyage_api_key = ""

        from services.photo_search import find_best_photos

        result = await find_best_photos(mock_sb, "user-1", "topic")

    assert result == []
