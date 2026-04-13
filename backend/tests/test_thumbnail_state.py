from services.thumbnail_state import ThumbnailState, UserIntent


def test_thumbnail_state_has_required_fields():
    state = ThumbnailState(
        conversation_id="conv-1",
        user_id="user-1",
        topic="",
        topic_research="",
        background_url=None,
        photo_name=None,
        composite_url=None,
        final_url=None,
        thumb_text=None,
        user_input="",
        user_intent=None,
        extra_instructions=None,
        photo_list=[],
    )
    assert state["conversation_id"] == "conv-1"
    assert state["user_id"] == "user-1"
    assert state["topic"] == ""


def test_user_intent_structure():
    intent = UserIntent(
        action="approve",
        feedback=None,
        photo_name=None,
        text=None,
    )
    assert intent["action"] == "approve"
