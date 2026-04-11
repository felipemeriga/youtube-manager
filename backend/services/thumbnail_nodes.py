import asyncio
import logging
import uuid

from supabase._async.client import create_client as create_async_client

from config import settings
from services.llm import ask_llm
from services.nano_banana import (
    generate_background,
    composite_with_effects,
    add_text_with_style,
)
from services.photo_search import find_best_photos
from services.thumbnail_state import ThumbnailState

logger = logging.getLogger(__name__)

CREATIVE_BRIEF_MODEL = "claude-haiku-4-5-20251001"

TOPIC_RESEARCH_SYSTEM = (
    "You research topics to help an image generation AI create better YouTube thumbnails.\n\n"
    "The thumbnail style, typography, layout, and composition are already defined by reference images — do NOT suggest any style changes.\n\n"
    "Your ONLY job is to research the TOPIC and suggest specific visual elements that represent it. "
    "Use web search to find current, relevant information.\n\n"
    "Output a short list (5-8 bullet points) of specific visual elements related to this topic. "
    "Be specific and visual."
)


async def _get_supabase():
    return await create_async_client(
        settings.supabase_url, settings.supabase_service_key
    )


async def _research_topic(topic: str) -> str:
    if not settings.anthropic_api_key:
        return ""
    try:
        return await ask_llm(
            system=TOPIC_RESEARCH_SYSTEM,
            messages=[
                {"role": "user", "content": f"Research visual elements for: {topic}"}
            ],
            model=CREATIVE_BRIEF_MODEL,
        )
    except Exception:
        logger.exception("topic research failed")
        return ""


async def _fetch_all_assets(sb, user_id: str, bucket: str) -> list[bytes]:
    files = await sb.storage.from_(bucket).list(path=user_id)
    names = [f["name"] for f in files if f.get("name")]

    async def _download(name: str) -> bytes:
        return await sb.storage.from_(bucket).download(f"{user_id}/{name}")

    results = await asyncio.gather(*[_download(n) for n in names])
    return list(results)


async def generate_background_node(state: ThumbnailState) -> dict:
    """Generate background image from topic + references + logos."""
    sb = await _get_supabase()
    user_id = state["user_id"]
    topic = state["topic"]

    topic_research = await _research_topic(topic)
    ref_thumbs = await _fetch_all_assets(sb, user_id, "reference-thumbs")
    logos = await _fetch_all_assets(sb, user_id, "logos")

    feedback = ""
    if state.get("user_intent") and state["user_intent"]["action"] == "feedback":
        feedback = state["user_intent"].get("feedback") or ""

    prompt_topic = f"{topic}\n\nAdditional feedback: {feedback}" if feedback else topic

    prompt = (
        "GENERATE ONLY THE BACKGROUND AND LOGO.\n"
        "Do NOT include any person, face, or human figure.\n"
        "Do NOT include any text or title.\n\n"
        f"Topic: {prompt_topic}\n"
        "The background MUST visually represent this topic. "
        "Use imagery, colors, and elements directly related to it.\n"
    )
    if topic_research:
        prompt += f"\nVisual elements to include in the background:\n{topic_research}\n"
    prompt += (
        "\nUse the reference thumbnails ONLY for layout and composition guidance. "
        "The actual visual content and colors must come from the topic, NOT from the references. "
        "Place the logo in the same position as the references."
    )

    background_bytes = await generate_background(
        prompt=prompt,
        reference_images=ref_thumbs,
        logos=logos,
    )

    temp_name = f"bg_{uuid.uuid4().hex[:8]}.png"
    storage_path = f"{user_id}/{temp_name}"
    await sb.storage.from_("outputs").upload(
        storage_path, background_bytes, {"content-type": "image/png"}
    )

    return {
        "background_url": storage_path,
        "topic_research": topic_research,
    }


async def show_photos_node(state: ThumbnailState) -> dict:
    """List personal photos with semantic recommendations."""
    sb = await _get_supabase()
    user_id = state["user_id"]
    topic = state["topic"]

    all_files = await sb.storage.from_("personal-photos").list(path=user_id)
    all_names = [f["name"] for f in all_files if f.get("name")]
    best = await find_best_photos(sb, user_id, topic, limit=5)

    photos = []
    for name in all_names:
        photos.append(
            {
                "name": name,
                "url": f"/api/assets/personal-photos/{name}",
                "recommended": name in best,
            }
        )
    photos.sort(key=lambda p: (not p["recommended"], p["name"]))

    return {"photo_list": photos}


async def composite_node(state: ThumbnailState) -> dict:
    """Composite person onto background with effects."""
    sb = await _get_supabase()
    user_id = state["user_id"]

    background_bytes = await sb.storage.from_("outputs").download(
        state["background_url"]
    )
    person_bytes = await sb.storage.from_("personal-photos").download(
        f"{user_id}/{state['photo_name']}"
    )
    ref_thumbs = await _fetch_all_assets(sb, user_id, "reference-thumbs")

    extra = state.get("extra_instructions")
    composite_bytes = await composite_with_effects(
        background_bytes,
        person_bytes,
        ref_thumbs,
        extra_instructions=extra,
    )

    temp_name = f"comp_{uuid.uuid4().hex[:8]}.png"
    storage_path = f"{user_id}/{temp_name}"
    await sb.storage.from_("outputs").upload(
        storage_path, composite_bytes, {"content-type": "image/png"}
    )

    return {"composite_url": storage_path, "extra_instructions": None}


async def add_text_node(state: ThumbnailState) -> dict:
    """Add styled text to composite using Gemini."""
    sb = await _get_supabase()
    user_id = state["user_id"]

    composite_bytes = await sb.storage.from_("outputs").download(state["composite_url"])
    ref_thumbs = await _fetch_all_assets(sb, user_id, "reference-thumbs")

    final_bytes = await add_text_with_style(
        composite_bytes, state["thumb_text"], ref_thumbs
    )

    temp_name = f"thumb_{uuid.uuid4().hex[:8]}.png"
    storage_path = f"{user_id}/{temp_name}"
    await sb.storage.from_("outputs").upload(
        storage_path, final_bytes, {"content-type": "image/png"}
    )

    return {"final_url": storage_path}


async def save_node(state: ThumbnailState) -> dict:
    """Save final thumbnail to permanent storage."""
    sb = await _get_supabase()
    user_id = state["user_id"]

    image_data = await sb.storage.from_("outputs").download(state["final_url"])

    final_filename = f"thumbnail_{uuid.uuid4().hex[:8]}.png"
    final_path = f"{user_id}/{final_filename}"
    await sb.storage.from_("outputs").upload(
        final_path, image_data, {"content-type": "image/png"}
    )

    # Keep temp file — it's referenced by the chat message history.
    # Old temp files can be cleaned up periodically.

    return {"final_url": final_path}
