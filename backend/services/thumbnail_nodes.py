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
from services.thumbnail_memory import get_relevant_memories, extract_and_store_memory
from services.thumbnail_state import PLATFORM_CONFIGS, DEFAULT_PLATFORMS, ThumbnailState

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


def _get_platforms(state: ThumbnailState) -> list[str]:
    """Get platforms from state, falling back to default."""
    return state.get("platforms") or DEFAULT_PLATFORMS


async def _upload_image(user_id: str, prefix: str, image_bytes: bytes) -> str:
    """Upload image to outputs bucket using a fresh client to avoid HTTP/2 conflicts."""
    sb = await _get_supabase()
    temp_name = f"{prefix}_{uuid.uuid4().hex[:8]}.png"
    storage_path = f"{user_id}/{temp_name}"
    await sb.storage.from_("outputs").upload(
        storage_path, image_bytes, {"content-type": "image/png"}
    )
    return storage_path


async def generate_background_node(state: ThumbnailState) -> dict:
    """Generate background images for all platforms."""
    sb = await _get_supabase()
    user_id = state["user_id"]
    topic = state["topic"]
    platforms = _get_platforms(state)

    # Fetch in parallel: topic research, assets, and past style memories
    topic_research_task = _research_topic(topic)
    ref_thumbs_task = _fetch_all_assets(sb, user_id, "reference-thumbs")
    logos_task = _fetch_all_assets(sb, user_id, "logos")
    memories_task = get_relevant_memories(sb, user_id, topic)

    topic_research, ref_thumbs, logos, style_memories = await asyncio.gather(
        topic_research_task, ref_thumbs_task, logos_task, memories_task
    )

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
    if style_memories:
        prompt += "\nUser's style preferences from past thumbnails:\n"
        for mem in style_memories:
            prompt += f"- {mem}\n"
    if topic_research:
        prompt += f"\nVisual elements to include in the background:\n{topic_research}\n"
    prompt += (
        "\nUse the reference thumbnails ONLY for layout and composition guidance. "
        "The actual visual content and colors must come from the topic, NOT from the references. "
        "Place the logo in the same position as the references."
    )

    # Generate for all platforms concurrently, then upload sequentially
    async def _gen_bg(platform: str) -> tuple[str, bytes]:
        cfg = PLATFORM_CONFIGS[platform]
        bg_bytes = await generate_background(
            prompt=prompt,
            reference_images=ref_thumbs,
            logos=logos,
            aspect_ratio=cfg["aspect_ratio"],
            image_size=cfg["image_size"],
        )
        return platform, bg_bytes

    gen_results = await asyncio.gather(*[_gen_bg(p) for p in platforms])

    # Upload sequentially to avoid connection pool exhaustion
    background_urls = {}
    for platform, bg_bytes in gen_results:
        path = await _upload_image(user_id, f"bg_{platform}", bg_bytes)
        background_urls[platform] = path

    return {
        "background_urls": background_urls,
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
    """Composite person onto background with effects for all platforms."""
    sb = await _get_supabase()
    user_id = state["user_id"]
    platforms = _get_platforms(state)
    background_urls = state.get("background_urls") or {}

    person_bytes = await sb.storage.from_("personal-photos").download(
        f"{user_id}/{state['photo_name']}"
    )
    ref_thumbs = await _fetch_all_assets(sb, user_id, "reference-thumbs")
    extra = state.get("extra_instructions")

    async def _gen_comp(platform: str) -> tuple[str, bytes]:
        bg_url = background_urls.get(platform)
        if not bg_url:
            raise Exception(f"No background for platform {platform}")
        dl_sb = await _get_supabase()
        bg_bytes = await dl_sb.storage.from_("outputs").download(bg_url)
        cfg = PLATFORM_CONFIGS[platform]
        comp_bytes = await composite_with_effects(
            bg_bytes,
            person_bytes,
            ref_thumbs,
            extra_instructions=extra,
            aspect_ratio=cfg["aspect_ratio"],
            image_size=cfg["image_size"],
        )
        return platform, comp_bytes

    gen_results = await asyncio.gather(*[_gen_comp(p) for p in platforms])

    composite_urls = {}
    for platform, comp_bytes in gen_results:
        path = await _upload_image(user_id, f"comp_{platform}", comp_bytes)
        composite_urls[platform] = path

    return {"composite_urls": composite_urls, "extra_instructions": None}


async def add_text_node(state: ThumbnailState) -> dict:
    """Add styled text to composites for all platforms."""
    sb = await _get_supabase()
    user_id = state["user_id"]
    platforms = _get_platforms(state)
    composite_urls = state.get("composite_urls") or {}

    ref_thumbs = await _fetch_all_assets(sb, user_id, "reference-thumbs")

    async def _gen_text(platform: str) -> tuple[str, bytes]:
        comp_url = composite_urls.get(platform)
        if not comp_url:
            raise Exception(f"No composite for platform {platform}")
        dl_sb = await _get_supabase()
        comp_bytes = await dl_sb.storage.from_("outputs").download(comp_url)
        cfg = PLATFORM_CONFIGS[platform]
        final_bytes = await add_text_with_style(
            comp_bytes,
            state["thumb_text"],
            ref_thumbs,
            aspect_ratio=cfg["aspect_ratio"],
            image_size=cfg["image_size"],
        )
        return platform, final_bytes

    gen_results = await asyncio.gather(*[_gen_text(p) for p in platforms])

    final_urls = {}
    for platform, final_bytes in gen_results:
        path = await _upload_image(user_id, f"thumb_{platform}", final_bytes)
        final_urls[platform] = path

    return {"final_urls": final_urls}


async def save_node(state: ThumbnailState) -> dict:
    """Save final thumbnails to permanent storage for all platforms."""
    sb = await _get_supabase()
    user_id = state["user_id"]
    final_urls = state.get("final_urls") or {}

    saved_urls = {}
    for platform, temp_url in final_urls.items():
        image_data = await sb.storage.from_("outputs").download(temp_url)
        final_filename = f"thumbnail_{platform}_{uuid.uuid4().hex[:8]}.png"
        final_path = f"{user_id}/{final_filename}"
        await sb.storage.from_("outputs").upload(
            final_path, image_data, {"content-type": "image/png"}
        )
        saved_urls[platform] = final_path

    # Extract style memory in background (don't block the save)
    asyncio.create_task(extract_and_store_memory(sb, user_id, state["conversation_id"]))

    return {"final_urls": saved_urls}
