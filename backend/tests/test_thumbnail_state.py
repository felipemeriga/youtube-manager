from services.thumbnail_state import QUALITY_TIERS, ThumbnailState, UserIntent


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
        quality_tier="balanced",
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


def test_quality_tiers_config():
    assert set(QUALITY_TIERS.keys()) == {"fast", "balanced", "quality"}
    for tier, config in QUALITY_TIERS.items():
        assert "model" in config, f"Tier '{tier}' missing 'model' key"
        assert "image_size" in config, f"Tier '{tier}' missing 'image_size' key"


def test_state_has_quality_tier():
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
        quality_tier="fast",
    )
    assert state["quality_tier"] == "fast"
