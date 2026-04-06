import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx


@pytest.fixture
def mock_guardian_settings():
    with patch("services.guardian.settings") as mock:
        mock.guardian_url = "http://localhost:3000"
        mock.guardian_api_key = "test-key"
        yield mock


class TestAskGuardian:
    async def test_success_returns_response(self, mock_guardian_settings):
        from services.guardian import ask_guardian

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Generated answer"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
            result = await ask_guardian("What is Python?")

        assert result == "Generated answer"
        mock_client.post.assert_called_once_with(
            "http://localhost:3000/api/ask",
            json={"message": "What is Python?"},
            headers={"x-api-key": "test-key"},
        )

    async def test_with_context_concatenates_prompt(self, mock_guardian_settings):
        from services.guardian import ask_guardian

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Contextual answer"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
            result = await ask_guardian("Summarize this", context="Some context")

        assert result == "Contextual answer"
        mock_client.post.assert_called_once_with(
            "http://localhost:3000/api/ask",
            json={"message": "Summarize this\n\nSome context"},
            headers={"x-api-key": "test-key"},
        )

    async def test_http_error_raises(self, mock_guardian_settings):
        from services.guardian import ask_guardian

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await ask_guardian("fail prompt")

    async def test_empty_response_field_returns_empty_string(
        self, mock_guardian_settings
    ):
        from services.guardian import ask_guardian

        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
            result = await ask_guardian("prompt")

        assert result == ""

    async def test_empty_context_is_ignored(self, mock_guardian_settings):
        from services.guardian import ask_guardian

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "answer"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.guardian.httpx.AsyncClient", return_value=mock_client):
            result = await ask_guardian("prompt", context="")

        mock_client.post.assert_called_once_with(
            "http://localhost:3000/api/ask",
            json={"message": "prompt"},
            headers={"x-api-key": "test-key"},
        )
        assert result == "answer"
