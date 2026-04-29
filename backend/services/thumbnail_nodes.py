import asyncio
import io
import logging
import time
import uuid
from collections import OrderedDict

from PIL import Image
from config import settings
from services.supabase_pool import get_async_client
from services.llm import ask_llm
from services.nano_banana import (
    generate_background,
    composite_with_effects,
    add_text_with_style,
)
from services.photo_search import find_best_photos
from services.thumbnail_memory import get_relevant_memories, extract_and_store_memory
from services.thumbnail_state import (
    PLATFORM_CONFIGS,
    DEFAULT_PLATFORMS,
    QUALITY_TIER,
    ThumbnailState,
)

logger = logging.getLogger(__name__)

# In-process asset cache: (user_id, bucket) -> (timestamp, data).
# Bounded LRU so the worker process can't grow without limit as new
# user_id/bucket pairs are seen.
_asset_cache: "OrderedDict[tuple[str, str], tuple[float, list[bytes]]]" = OrderedDict()
_CACHE_TTL = 600  # 10 minutes
_CACHE_MAX = 64  # ~ 4 buckets * 16 active users

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
    return await get_async_client()


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


async def _fetch_all_assets(_sb_unused, user_id: str, bucket: str) -> list[bytes]:
    """Fetch all assets from a bucket with in-process caching.

    Uses a single shared client with concurrent downloads via semaphore.
    """
    cache_key = (user_id, bucket)
    cached = _asset_cache.get(cache_key)
    if cached:
        ts, data = cached
        if time.time() - ts < _CACHE_TTL:
            _asset_cache.move_to_end(cache_key)
            logger.debug(
                "asset cache hit for %s/%s (%d items)", user_id, bucket, len(data)
            )
            return data
        # Expired — drop and refetch
        _asset_cache.pop(cache_key, None)

    sb = await _get_supabase()

    for attempt in range(3):
        try:
            files = await sb.storage.from_(bucket).list(path=user_id)
            break
        except Exception:
            if attempt == 2:
                logger.warning("Failed to list %s after 3 attempts", bucket)
                return []
            await asyncio.sleep(1)

    names = [f["name"] for f in files if f.get("name")]
    if not names:
        return []

    sem = asyncio.Semaphore(10)

    async def _dl(name: str) -> bytes | None:
        async with sem:
            for attempt in range(3):
                try:
                    return await sb.storage.from_(bucket).download(f"{user_id}/{name}")
                except Exception:
                    if attempt == 2:
                        logger.warning("Failed to download %s/%s", bucket, name)
                    await asyncio.sleep(0.5)
            return None

    results = await asyncio.gather(*[_dl(n) for n in names])
    data = [r for r in results if r is not None]

    _asset_cache[cache_key] = (time.time(), data)
    while len(_asset_cache) > _CACHE_MAX:
        _asset_cache.popitem(last=False)
    logger.info(
        "asset cache miss for %s/%s — downloaded %d items", user_id, bucket, len(data)
    )
    return data


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


def _make_preview(image_bytes: bytes, max_edge: int = 720) -> bytes:
    """Resize image to max_edge on longest side, return as JPEG bytes."""
    img = Image.open(io.BytesIO(image_bytes))
    img.thumbnail((max_edge, max_edge), Image.LANCZOS)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=80)
    return buf.getvalue()


async def _upload_image_with_preview(
    user_id: str, prefix: str, image_bytes: bytes
) -> tuple[str, str]:
    """Upload original image and 720p JPEG preview. Returns (original_path, preview_path)."""
    sb = await _get_supabase()
    name_id = uuid.uuid4().hex[:8]
    original_name = f"{prefix}_{name_id}.png"
    preview_name = f"preview_{prefix}_{name_id}.jpg"
    original_path = f"{user_id}/{original_name}"
    preview_path = f"{user_id}/{preview_name}"

    await sb.storage.from_("outputs").upload(
        original_path, image_bytes, {"content-type": "image/png"}
    )

    try:
        preview_bytes = _make_preview(image_bytes)
        await sb.storage.from_("outputs").upload(
            preview_path, preview_bytes, {"content-type": "image/jpeg"}
        )
    except Exception:
        logger.warning("preview upload failed for %s, skipping", original_path)
        preview_path = ""

    return original_path, preview_path


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
        "Generate ONLY the background + logo. NO text, NO people.\n"
        "Text and person are added in later steps — including them now causes duplicates.\n"
        "Leave space for where the person and text will go.\n\n"
        f"Topic: {prompt_topic}\n"
        "Use imagery, colors, and elements that represent this topic.\n"
    )
    if style_memories:
        prompt += "\nStyle preferences:\n"
        for mem in style_memories:
            prompt += f"- {mem}\n"
    if topic_research:
        prompt += f"\nVisual elements for the background:\n{topic_research}\n"
    prompt += "\nMatch logo placement from references. Colors/content must come from the topic."

    # When feedback (not restart), download previous backgrounds for context
    previous_bgs: dict[str, bytes] = {}
    existing_bg_urls = state.get("background_urls") or {}
    if feedback and existing_bg_urls:

        async def _dl_prev_bg(platform: str, paths: dict) -> tuple[str, bytes]:
            dl_sb = await _get_supabase()
            url = paths["url"] if isinstance(paths, dict) else paths
            data = await dl_sb.storage.from_("outputs").download(url)
            return platform, data

        prev_results = await asyncio.gather(
            *[_dl_prev_bg(p, u) for p, u in existing_bg_urls.items()]
        )
        previous_bgs = dict(prev_results)

    tier = QUALITY_TIER

    # Generate for all platforms concurrently, then upload sequentially
    async def _gen_bg(platform: str) -> tuple[str, bytes]:
        cfg = PLATFORM_CONFIGS[platform]
        bg_bytes = await generate_background(
            prompt=prompt,
            reference_images=ref_thumbs,
            logos=logos,
            previous_image=previous_bgs.get(platform),
            aspect_ratio=cfg["aspect_ratio"],
            image_size=tier["image_size"],
            model=tier["model"],
        )
        return platform, bg_bytes

    gen_results = await asyncio.gather(*[_gen_bg(p) for p in platforms])

    # Upload all platforms in parallel (shared singleton client handles pooling)
    async def _upload_bg(platform: str, bg_bytes: bytes):
        original_path, preview_path = await _upload_image_with_preview(
            user_id, f"bg_{platform}", bg_bytes
        )
        return platform, {"url": original_path, "preview_url": preview_path}

    upload_results = await asyncio.gather(*[_upload_bg(p, b) for p, b in gen_results])
    background_urls = dict(upload_results)

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
    composite_mode = state.get("composite_mode") or "natural"
    transform_prompt = state.get("transform_prompt")

    # When feedback, download previous composites for context
    previous_comps: dict[str, bytes] = {}
    existing_comp_urls = state.get("composite_urls") or {}
    is_feedback = (
        state.get("user_intent") and state["user_intent"]["action"] == "feedback"
    )
    if is_feedback and existing_comp_urls:

        async def _dl_prev_comp(platform: str, paths: dict) -> tuple[str, bytes]:
            dl_sb = await _get_supabase()
            url = paths["url"] if isinstance(paths, dict) else paths
            data = await dl_sb.storage.from_("outputs").download(url)
            return platform, data

        prev_results = await asyncio.gather(
            *[_dl_prev_comp(p, u) for p, u in existing_comp_urls.items()]
        )
        previous_comps = dict(prev_results)

    tier = QUALITY_TIER

    async def _gen_comp(platform: str) -> tuple[str, bytes]:
        bg_paths = background_urls.get(platform)
        if not bg_paths:
            raise Exception(f"No background for platform {platform}")
        bg_url = bg_paths["url"] if isinstance(bg_paths, dict) else bg_paths
        dl_sb = await _get_supabase()
        bg_bytes = await dl_sb.storage.from_("outputs").download(bg_url)
        cfg = PLATFORM_CONFIGS[platform]
        comp_bytes = await composite_with_effects(
            bg_bytes,
            person_bytes,
            ref_thumbs,
            extra_instructions=extra,
            previous_image=previous_comps.get(platform),
            composite_mode=composite_mode,
            transform_prompt=transform_prompt,
            aspect_ratio=cfg["aspect_ratio"],
            image_size=tier["image_size"],
            model=tier["model"],
        )
        return platform, comp_bytes

    gen_results = await asyncio.gather(*[_gen_comp(p) for p in platforms])

    async def _upload_comp(platform: str, comp_bytes: bytes):
        original_path, preview_path = await _upload_image_with_preview(
            user_id, f"comp_{platform}", comp_bytes
        )
        return platform, {"url": original_path, "preview_url": preview_path}

    upload_results = await asyncio.gather(*[_upload_comp(p, b) for p, b in gen_results])
    composite_urls = dict(upload_results)

    return {"composite_urls": composite_urls, "extra_instructions": None}


async def add_text_node(state: ThumbnailState) -> dict:
    """Add styled text to composites for all platforms."""
    sb = await _get_supabase()
    user_id = state["user_id"]
    platforms = _get_platforms(state)
    composite_urls = state.get("composite_urls") or {}

    all_refs = await _fetch_all_assets(sb, user_id, "reference-thumbs")
    # Only need 2 references for typography style — fewer images = higher
    # chance of 4K output succeeding and faster API calls
    ref_thumbs = all_refs[:2]

    # Extract feedback for text styling (e.g. "add shadow", "bigger font")
    text_feedback = None
    if state.get("user_intent") and state["user_intent"]["action"] == "feedback":
        text_feedback = state["user_intent"].get("feedback")

    # When re-doing text, download previous finals for context
    previous_finals: dict[str, bytes] = {}
    existing_final_urls = state.get("final_urls") or {}
    if existing_final_urls:

        async def _dl_prev_final(platform: str, paths: dict) -> tuple[str, bytes]:
            dl_sb = await _get_supabase()
            url = paths["url"] if isinstance(paths, dict) else paths
            data = await dl_sb.storage.from_("outputs").download(url)
            return platform, data

        prev_results = await asyncio.gather(
            *[_dl_prev_final(p, u) for p, u in existing_final_urls.items()]
        )
        previous_finals = dict(prev_results)

    tier = QUALITY_TIER

    async def _gen_text(platform: str) -> tuple[str, bytes]:
        comp_paths = composite_urls.get(platform)
        if not comp_paths:
            raise Exception(f"No composite for platform {platform}")
        comp_url = comp_paths["url"] if isinstance(comp_paths, dict) else comp_paths
        dl_sb = await _get_supabase()
        comp_bytes = await dl_sb.storage.from_("outputs").download(comp_url)
        cfg = PLATFORM_CONFIGS[platform]
        final_bytes = await add_text_with_style(
            comp_bytes,
            state["thumb_text"],
            ref_thumbs,
            previous_image=previous_finals.get(platform),
            extra_instructions=text_feedback,
            aspect_ratio=cfg["aspect_ratio"],
            image_size=tier["image_size"],
            model=tier["model"],
        )
        return platform, final_bytes

    gen_results = await asyncio.gather(*[_gen_text(p) for p in platforms])

    async def _upload_text(platform: str, final_bytes: bytes):
        original_path, preview_path = await _upload_image_with_preview(
            user_id, f"thumb_{platform}", final_bytes
        )
        return platform, {"url": original_path, "preview_url": preview_path}

    upload_results = await asyncio.gather(*[_upload_text(p, b) for p, b in gen_results])
    final_urls = dict(upload_results)

    return {"final_urls": final_urls}


async def save_node(state: ThumbnailState) -> dict:
    """Save final thumbnails to permanent storage for all platforms."""
    sb = await _get_supabase()
    user_id = state["user_id"]
    final_urls = state.get("final_urls") or {}

    async def _save_one(platform: str, paths) -> tuple[str, dict]:
        temp_url = paths["url"] if isinstance(paths, dict) else paths
        image_data = await sb.storage.from_("outputs").download(temp_url)
        final_filename = f"thumbnail_{platform}_{uuid.uuid4().hex[:8]}.png"
        final_path = f"{user_id}/{final_filename}"
        await sb.storage.from_("outputs").upload(
            final_path, image_data, {"content-type": "image/png"}
        )
        return platform, {"url": final_path, "preview_url": ""}

    save_results = await asyncio.gather(
        *[_save_one(p, paths) for p, paths in final_urls.items()]
    )
    saved_urls = dict(save_results)

    # Extract style memory in background (don't block the save)
    asyncio.create_task(extract_and_store_memory(sb, user_id, state["conversation_id"]))

    return {"final_urls": saved_urls}
