import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.fixture
def mock_llm_settings_anthropic():
    with patch("services.llm.settings") as mock:
        mock.anthropic_api_key = "test-anthropic-key"
        mock.anthropic_model = "claude-sonnet-4-20250514"
        mock.guardian_url = "http://localhost:3000"
        mock.guardian_api_key = ""
        yield mock


@pytest.fixture
def mock_llm_settings_guardian():
    with patch("services.llm.settings") as mock:
        mock.anthropic_api_key = ""
        mock.guardian_url = "http://localhost:3000"
        mock.guardian_api_key = "test-guardian-key"
        yield mock


class TestAskLlm:
    async def test_uses_anthropic_when_key_is_set(self, mock_llm_settings_anthropic):
        from services.llm import ask_llm

        mock_text_block = MagicMock()
        mock_text_block.text = "Anthropic answer"

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("services.llm.AsyncAnthropic", return_value=mock_client):
            result = await ask_llm(
                "You are helpful.", [{"role": "user", "content": "Hello"}]
            )

        assert result == "Anthropic answer"
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs["system"] == "You are helpful."
        assert call_kwargs["messages"] == [{"role": "user", "content": "Hello"}]
        assert call_kwargs["tools"][0]["type"] == "web_search_20250305"

    async def test_falls_back_to_guardian_when_no_anthropic_key(
        self, mock_llm_settings_guardian
    ):
        from services.llm import ask_llm

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Guardian answer"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.llm.httpx.AsyncClient", return_value=mock_client):
            result = await ask_llm(
                "You are helpful.", [{"role": "user", "content": "Hello"}]
            )

        assert result == "Guardian answer"

    async def test_guardian_includes_auth_header(self, mock_llm_settings_guardian):
        from services.llm import ask_llm

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "answer"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.llm.httpx.AsyncClient", return_value=mock_client):
            await ask_llm("System prompt.", [{"role": "user", "content": "Hi"}])

        _, kwargs = mock_client.post.call_args
        assert kwargs["headers"] == {"Authorization": "Bearer test-guardian-key"}

    async def test_guardian_no_auth_header_when_no_key(self):
        with patch("services.llm.settings") as mock_settings:
            mock_settings.anthropic_api_key = ""
            mock_settings.guardian_url = "http://localhost:3000"
            mock_settings.guardian_api_key = ""

            from services.llm import ask_llm

            mock_response = MagicMock()
            mock_response.json.return_value = {"response": "answer"}
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            with patch("services.llm.httpx.AsyncClient", return_value=mock_client):
                await ask_llm("System.", [{"role": "user", "content": "Hi"}])

            _, kwargs = mock_client.post.call_args
            assert kwargs["headers"] == {}
