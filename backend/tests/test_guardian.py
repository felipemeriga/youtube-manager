import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from services.guardian import ask_guardian


@pytest.mark.asyncio
async def test_ask_guardian_returns_response():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": "Here is my plan for your thumbnail..."
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
        with patch("services.guardian.settings") as mock_settings:
            mock_settings.guardian_url = "http://localhost:3000"
            mock_settings.guardian_api_key = "test-key"
            result = await ask_guardian(
                prompt="Create a thumbnail plan for a Python tutorial",
                system="You are a YouTube thumbnail designer.",
            )

    assert result == "Here is my plan for your thumbnail..."
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "http://localhost:3000/api/ask"
    body = call_args[1]["json"]
    assert "Create a thumbnail plan" in body["prompt"]
    assert body["system"] == "You are a YouTube thumbnail designer."


@pytest.mark.asyncio
async def test_ask_guardian_handles_error():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=MagicMock(status_code=500)
        )
    )

    with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
        with patch("services.guardian.settings") as mock_settings:
            mock_settings.guardian_url = "http://localhost:3000"
            mock_settings.guardian_api_key = "test-key"
            with pytest.raises(Exception, match="Guardian request failed"):
                await ask_guardian(prompt="test", system="test")
