from typing_extensions import TypedDict


class UserIntent(TypedDict):
    action: str  # approve, feedback, select_photo, provide_text, save, restart
    feedback: str | None
    photo_name: str | None
    text: str | None


class ThumbnailState(TypedDict):
    # Identity
    conversation_id: str
    user_id: str

    # Content
    topic: str
    topic_research: str

    # Artifacts (Supabase storage paths)
    background_url: str | None
    photo_name: str | None
    composite_url: str | None
    final_url: str | None
    thumb_text: str | None

    # User interaction
    user_input: str
    user_intent: UserIntent | None
    extra_instructions: str | None

    # Photo list for selection
    photo_list: list[dict]
