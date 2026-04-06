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


@pytest.mark.asyncio
async def test_ask_guardian_timeout_error():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.ReadTimeout("Connection timed out"))

    with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
        with patch("services.guardian.settings") as mock_settings:
            mock_settings.guardian_url = "http://localhost:3000"
            mock_settings.guardian_api_key = "test-key"
            with pytest.raises(Exception, match="Guardian request failed"):
                await ask_guardian(prompt="test", system="test")


@pytest.mark.asyncio
async def test_ask_guardian_network_error():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
        with patch("services.guardian.settings") as mock_settings:
            mock_settings.guardian_url = "http://localhost:3000"
            mock_settings.guardian_api_key = "test-key"
            with pytest.raises(Exception, match="Guardian request failed"):
                await ask_guardian(prompt="test", system="test")


@pytest.mark.asyncio
async def test_ask_guardian_passes_custom_timeout():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "ok"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
        with patch("services.guardian.settings") as mock_settings:
            mock_settings.guardian_url = "http://localhost:3000"
            mock_settings.guardian_api_key = "test-key"
            await ask_guardian(prompt="test", system="test", timeout=60)

    call_kwargs = mock_client.post.call_args[1]
    assert call_kwargs["json"]["timeout"] == 60000
    assert call_kwargs["timeout"] == 70


@pytest.mark.asyncio
async def test_ask_guardian_default_timeout():
    """Default timeout should be 120s, sending 120000ms to Guardian and 130s to httpx."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "ok"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
        with patch("services.guardian.settings") as mock_settings:
            mock_settings.guardian_url = "http://localhost:3000"
            mock_settings.guardian_api_key = "test-key"
            await ask_guardian(prompt="test", system="test")

    call_kwargs = mock_client.post.call_args[1]
    assert call_kwargs["json"]["timeout"] == 120000
    assert call_kwargs["timeout"] == 130


@pytest.mark.asyncio
async def test_ask_guardian_sends_authorization_header():
    """Guardian request should include Bearer token in Authorization header."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "ok"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
        with patch("services.guardian.settings") as mock_settings:
            mock_settings.guardian_url = "http://localhost:3000"
            mock_settings.guardian_api_key = "my-secret-key"
            await ask_guardian(prompt="test", system="test")

    call_kwargs = mock_client.post.call_args[1]
    assert call_kwargs["headers"]["Authorization"] == "Bearer my-secret-key"


@pytest.mark.asyncio
async def test_ask_guardian_raise_for_status_called():
    """Guardian should call raise_for_status to detect HTTP errors."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "ok"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
        with patch("services.guardian.settings") as mock_settings:
            mock_settings.guardian_url = "http://localhost:3000"
            mock_settings.guardian_api_key = "test-key"
            await ask_guardian(prompt="test", system="test")

    mock_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_ask_guardian_raise_for_status_triggers_exception():
    """When raise_for_status raises, guardian should wrap it."""
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Forbidden", request=MagicMock(), response=MagicMock(status_code=403)
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
        with patch("services.guardian.settings") as mock_settings:
            mock_settings.guardian_url = "http://localhost:3000"
            mock_settings.guardian_api_key = "test-key"
            with pytest.raises(Exception, match="Guardian request failed"):
                await ask_guardian(prompt="test", system="test")
