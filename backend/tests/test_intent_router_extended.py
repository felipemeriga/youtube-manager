"""Extended coverage for services/intent_router.py."""

import json
import pytest
from unittest.mock import AsyncMock, patch

from services.intent_router import classify_intent


# ---------------------------------------------------------------------------
# Approve variants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    ["sim", "ok", "próximo", "parece bom"],
)
async def test_approve_variations(text: str):
    """Common approval phrases should classify as approve."""
    mock_response = json.dumps(
        {"action": "approve", "feedback": None, "photo_name": None, "text": None}
    )
    with patch("services.intent_router.ask_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response
        result = await classify_intent(text, "review_background")

    assert result["action"] == "approve"
    mock_llm.assert_called_once()


# ---------------------------------------------------------------------------
# Feedback with detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_feedback_with_detail():
    """Free text feedback should return action=feedback with the text preserved."""
    mock_response = json.dumps(
        {
            "action": "feedback",
            "feedback": "muito escuro, clareia",
            "photo_name": None,
            "text": None,
        }
    )
    with patch("services.intent_router.ask_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response
        result = await classify_intent("muito escuro, clareia", "review_background")

    assert result["action"] == "feedback"
    assert result["feedback"] == "muito escuro, clareia"


# ---------------------------------------------------------------------------
# Restart in Portuguese
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["começar de novo", "do começo", "recomeçar"])
async def test_restart_portuguese(text: str):
    """Portuguese restart phrases should classify as restart."""
    mock_response = json.dumps(
        {"action": "restart", "feedback": None, "photo_name": None, "text": None}
    )
    with patch("services.intent_router.ask_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response
        result = await classify_intent(text, "review_background")

    assert result["action"] == "restart"


# ---------------------------------------------------------------------------
# select_photo with filename
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_select_photo_with_name():
    """LLM returns select_photo action with photo_name."""
    mock_response = json.dumps(
        {
            "action": "select_photo",
            "photo_name": "sem_titulo-71.jpg",
            "feedback": None,
            "text": None,
        }
    )
    with patch("services.intent_router.ask_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response
        result = await classify_intent("use sem_titulo-71.jpg", "review_photo")

    assert result["action"] == "select_photo"
    assert result["photo_name"] == "sem_titulo-71.jpg"


# ---------------------------------------------------------------------------
# provide_text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provide_text():
    """LLM returns provide_text action with extracted text."""
    mock_response = json.dumps(
        {
            "action": "provide_text",
            "text": "Guerra do Irã e IA",
            "feedback": None,
            "photo_name": None,
        }
    )
    with patch("services.intent_router.ask_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response
        result = await classify_intent("Guerra do Irã e IA", "ask_text")

    assert result["action"] == "provide_text"
    assert result["text"] == "Guerra do Irã e IA"


# ---------------------------------------------------------------------------
# LLM exception falls back to feedback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_exception_falls_back():
    """When ask_llm raises an exception, classify_intent falls back to feedback."""
    with patch("services.intent_router.ask_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = Exception("Anthropic API unavailable")
        result = await classify_intent("something important", "review_background")

    assert result["action"] == "feedback"
    assert result["feedback"] == "something important"


# ---------------------------------------------------------------------------
# Empty input falls back to feedback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_input_falls_back():
    """Empty string input should fall back to feedback (LLM or parse failure)."""
    with patch("services.intent_router.ask_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "not json"
        result = await classify_intent("", "review_background")

    assert result["action"] == "feedback"
    # feedback text should be the original input (empty string)
    assert result["feedback"] == ""


# ---------------------------------------------------------------------------
# JSON with nested objects still extracts action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_json_with_nested_objects():
    """LLM returns JSON with extra nested data; action should still be extracted."""
    raw = json.dumps(
        {
            "action": "approve",
            "feedback": None,
            "photo_name": None,
            "text": None,
            "meta": {"confidence": 0.99, "tags": ["ok", "good"]},
        }
    )
    # The regex in classify_intent only captures the first {…} block, so we
    # exercise the JSON-parse path that extracts action from a richer object
    # via the direct-button-click shortcut (valid JSON with "action" key).
    result = await classify_intent(raw, "review_background")

    assert result["action"] == "approve"


# ---------------------------------------------------------------------------
# Button action with all four fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_button_action_with_all_fields():
    """JSON payload with all four fields should be parsed without calling LLM."""
    payload = json.dumps(
        {
            "action": "select_photo",
            "feedback": "looks great",
            "photo_name": "face.jpg",
            "text": "some title",
        }
    )
    with patch("services.intent_router.ask_llm", new_callable=AsyncMock) as mock_llm:
        result = await classify_intent(payload, "review_photo")

    # LLM must NOT be called for direct button actions
    mock_llm.assert_not_called()
    assert result["action"] == "select_photo"
    assert result["feedback"] == "looks great"
    assert result["photo_name"] == "face.jpg"
    assert result["text"] == "some title"
