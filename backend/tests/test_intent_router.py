import json
import pytest
from unittest.mock import AsyncMock, patch

from services.intent_router import classify_intent


@pytest.mark.asyncio
async def test_button_action_bypasses_llm():
    """JSON action payloads skip the LLM entirely."""
    result = await classify_intent('{"action": "approve"}', "review_background")
    assert result["action"] == "approve"


@pytest.mark.asyncio
async def test_button_action_with_extra_fields():
    result = await classify_intent(
        '{"action": "select_photo", "photo_name": "photo.jpg"}',
        "review_photo",
    )
    assert result["action"] == "select_photo"
    assert result["photo_name"] == "photo.jpg"


@pytest.mark.asyncio
async def test_freetext_calls_llm():
    """Free text input should call the LLM for classification."""
    mock_response = json.dumps(
        {
            "action": "feedback",
            "feedback": "make it darker",
        }
    )
    with patch("services.intent_router.ask_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response
        result = await classify_intent("make it darker please", "review_background")

    assert result["action"] == "feedback"
    assert result["feedback"] == "make it darker"
    mock_llm.assert_called_once()


@pytest.mark.asyncio
async def test_freetext_llm_returns_invalid_json_falls_back():
    """If LLM returns invalid JSON, fall back to feedback action."""
    with patch("services.intent_router.ask_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "not json at all"
        result = await classify_intent("something weird", "review_background")

    assert result["action"] == "feedback"
    assert result["feedback"] == "something weird"
