from services.thumbnail_state import QUALITY_TIER, ThumbnailState, UserIntent


def test_thumbnail_state_has_required_fields():
    state = ThumbnailState(
        conversation_id="conv-1",
        user_id="user-1",
        topic="",
        topic_research="",
        platforms=["youtube"],
        background_urls={},
        photo_name=None,
        composite_urls={},
        final_urls={},
        thumb_text=None,
        user_input="",
        user_intent=None,
        extra_instructions=None,
        photo_list=[],
        uploaded_image_url=None,
        composite_mode="natural",
        transform_prompt=None,
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


def test_quality_tier_config():
    assert "model" in QUALITY_TIER
    assert "image_size" in QUALITY_TIER
    assert QUALITY_TIER["image_size"] == "4K"


def test_state_has_composite_mode():
    state = ThumbnailState(
        conversation_id="conv-1",
        user_id="user-1",
        topic="test",
        topic_research="",
        platforms=["youtube"],
        background_urls={},
        photo_name=None,
        composite_urls={},
        final_urls={},
        thumb_text=None,
        user_input="",
        user_intent=None,
        extra_instructions=None,
        photo_list=[],
        uploaded_image_url=None,
        composite_mode="transform",
        transform_prompt="astronaut in space",
    )
    assert state["composite_mode"] == "transform"
    assert state["transform_prompt"] == "astronaut in space"
