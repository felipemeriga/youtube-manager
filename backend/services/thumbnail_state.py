from typing_extensions import TypedDict


class UserIntent(TypedDict):
    action: str  # approve, feedback, select_photo, provide_text, save, restart
    feedback: str | None
    photo_name: str | None
    text: str | None


QUALITY_TIER = {"model": "gemini-3-pro-image-preview", "image_size": "4K"}


# Platform configs: aspect_ratio for Gemini, label for UI
PLATFORM_CONFIGS = {
    "youtube": {"aspect_ratio": "16:9", "label": "YouTube", "image_size": "4K"},
    "instagram_post": {
        "aspect_ratio": "1:1",
        "label": "Instagram Post",
        "image_size": "4K",
    },
    "instagram_story": {
        "aspect_ratio": "9:16",
        "label": "Instagram Story",
        "image_size": "4K",
    },
}

DEFAULT_PLATFORMS = ["youtube"]


class ThumbnailState(TypedDict):
    # Identity
    conversation_id: str
    user_id: str

    # Content
    topic: str
    topic_research: str

    # Platforms to generate for
    platforms: list[str]  # e.g. ["youtube", "instagram_post", "instagram_story"]

    # Artifacts per platform: {"youtube": {"url": "path", "preview_url": "path"}, ...}
    background_urls: dict[str, dict[str, str]]
    photo_name: str | None
    composite_urls: dict[str, dict[str, str]]
    final_urls: dict[str, dict[str, str]]
    thumb_text: str | None

    # User interaction
    user_input: str
    user_intent: UserIntent | None
    extra_instructions: str | None
    clarify_question: str | None

    # Photo list for selection
    photo_list: list[dict]

    # User-uploaded image storage path
    uploaded_image_url: str | None

    # Composite mode: "natural" (preserve person as-is) or "transform" (allow modifications)
    composite_mode: str  # "natural" | "transform"
    transform_prompt: str | None  # e.g. "transform me into an astronaut"
