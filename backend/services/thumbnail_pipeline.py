import base64
import json
import logging
import uuid
from typing import AsyncGenerator

from supabase._async.client import create_client as create_async_client

from config import settings
from services.llm import ask_llm
from services.nano_banana import generate_background
from services.image_compositor import composite_person, overlay_text
from services.photo_search import find_best_photos

logger = logging.getLogger(__name__)

CREATIVE_BRIEF_MODEL = "claude-haiku-4-5-20251001"
MAX_PERSONAL_PHOTOS = 5

TOPIC_RESEARCH_SYSTEM = (
    "You research topics to help an image generation AI create better YouTube thumbnails.\n\n"
    "The thumbnail style, typography, layout, and composition are already defined by reference images — do NOT suggest any style changes.\n\n"
    "Your ONLY job is to research the TOPIC and suggest specific visual elements that represent it. "
    "Use web search to find current, relevant information.\n\n"
    "Output a short list (5-8 bullet points) of specific visual elements related to this topic. "
    "Be specific and visual."
)


async def get_supabase():
    return await create_async_client(
        settings.supabase_url, settings.supabase_service_key
    )


def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _save_message(sb, conversation_id: str, role: str, content: str, msg_type: str, image_url: str | None = None):
    payload = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "type": msg_type,
    }
    if image_url:
        payload["image_url"] = image_url
    await sb.table("messages").insert(payload).execute()


async def _get_messages(sb, conversation_id: str) -> list[dict]:
    response = (
        await sb.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )
    return response.data


async def _research_topic(topic: str) -> str:
    if not settings.anthropic_api_key:
        return ""
    try:
        research = await ask_llm(
            system=TOPIC_RESEARCH_SYSTEM,
            messages=[{"role": "user", "content": f"Research visual elements for: {topic}"}],
            model=CREATIVE_BRIEF_MODEL,
        )
        return research
    except Exception:
        logger.exception("topic research failed")
        return ""


async def _get_text_style(sb, user_id: str) -> dict:
    """Get stored text style from channel_personas."""
    result = await sb.table("channel_personas").select("text_style").eq("user_id", user_id).maybe_single().execute()
    if result and result.data and result.data.get("text_style"):
        return result.data["text_style"]
    # Default style
    return {
        "person_position": "right",
        "person_size_pct": 70,
        "person_vertical": "bottom-aligned",
        "text_position": "left",
        "text_vertical": "center",
        "text_color": "#FFFFFF",
        "text_stroke": True,
        "text_stroke_color": "#000000",
        "text_stroke_width": 3,
        "text_shadow": False,
        "text_size_ratio": 0.08,
        "text_max_width_ratio": 0.5,
        "logo_position": "top-left",
        "logo_size_ratio": 0.08,
    }


async def _get_font_bytes(sb, user_id: str) -> bytes | None:
    """Get the user's font file from the fonts bucket."""
    try:
        files = await sb.storage.from_("fonts").list(path=user_id)
        font_files = [f for f in files if f.get("name") and f["name"].endswith((".ttf", ".otf", ".woff"))]
        if font_files:
            return await sb.storage.from_("fonts").download(f"{user_id}/{font_files[0]['name']}")
    except Exception:
        logger.exception("failed to load font")
    return None


async def fetch_all_assets(sb, user_id: str, bucket: str) -> list[bytes]:
    files = await sb.storage.from_(bucket).list(path=user_id)
    result = []
    for f in files:
        if f.get("name"):
            data = await sb.storage.from_(bucket).download(f"{user_id}/{f['name']}")
            result.append(data)
    return result


# ---------------------------------------------------------------------------
# Step 1: Background + Logo
# ---------------------------------------------------------------------------

async def handle_step1_background(
    sb, conversation_id: str, content: str, user_id: str
) -> AsyncGenerator[str, None]:
    """Generate background + logo only."""
    logger.info("step1_background conversation=%s user=%s", conversation_id, user_id)

    await _save_message(sb, conversation_id, "user", content, "text")
    await sb.table("conversations").update({"title": content[:50]}).eq("id", conversation_id).execute()

    yield sse_event({"stage": "analyzing"})

    topic_research = await _research_topic(content)

    yield sse_event({"stage": "generating"})

    ref_thumbs = await fetch_all_assets(sb, user_id, "reference-thumbs")
    logos = await fetch_all_assets(sb, user_id, "logos")

    prompt = (
        "GENERATE ONLY THE BACKGROUND AND LOGO.\n"
        "Do NOT include any person, face, or human figure.\n"
        "Do NOT include any text or title.\n\n"
        f"Topic: {content}\n"
    )
    if topic_research:
        prompt += f"\nVisual ideas for the background:\n{topic_research}\n"
    prompt += (
        "\nMatch the same visual style, color grading, and effects as the reference thumbnails. "
        "Place the logo in the same position as the references."
    )

    background_bytes = await generate_background(
        prompt=prompt,
        reference_images=ref_thumbs,
        logos=logos,
    )

    # Store temporarily
    temp_name = f"bg_{uuid.uuid4().hex[:8]}.png"
    storage_path = f"{user_id}/{temp_name}"
    await sb.storage.from_("outputs").upload(
        storage_path, background_bytes, {"content-type": "image/png"}
    )

    image_base64 = base64.b64encode(background_bytes).decode()
    await _save_message(sb, conversation_id, "assistant",
                        "Here's the background. Approve to pick a photo, or reject to regenerate.",
                        "background", image_url=storage_path)

    yield sse_event({
        "message_type": "background",
        "image_base64": image_base64,
        "image_url": storage_path,
    })
    yield sse_event({"done": True})


# ---------------------------------------------------------------------------
# Step 2: Photo Selection + Compositing
# ---------------------------------------------------------------------------

async def handle_step2_show_photos(
    sb, conversation_id: str, user_id: str
) -> AsyncGenerator[str, None]:
    """Show photo grid for user selection."""
    logger.info("step2_show_photos conversation=%s user=%s", conversation_id, user_id)

    await _save_message(sb, conversation_id, "user", "approved_background", "approval")

    # Get topic from first user message
    messages = await _get_messages(sb, conversation_id)
    topic = next((m["content"] for m in messages if m["type"] == "text"), "")

    # Get all photos
    all_files = await sb.storage.from_("personal-photos").list(path=user_id)
    all_names = [f["name"] for f in all_files if f.get("name")]

    # Get semantic matches
    best = await find_best_photos(sb, user_id, topic, limit=5)

    # Build photo list with match info
    photos = []
    for name in all_names:
        url = f"/api/assets/personal-photos/{name}"
        photos.append({
            "name": name,
            "url": url,
            "recommended": name in best,
        })

    # Sort: recommended first
    photos.sort(key=lambda p: (not p["recommended"], p["name"]))

    photo_grid_json = json.dumps(photos)
    await _save_message(sb, conversation_id, "assistant", photo_grid_json, "photo_grid")

    yield sse_event({"done": True, "message_type": "photo_grid", "content": photo_grid_json})


async def handle_step2_composite(
    sb, conversation_id: str, photo_name: str, user_id: str
) -> AsyncGenerator[str, None]:
    """Composite selected photo onto background."""
    logger.info("step2_composite conversation=%s photo=%s user=%s", conversation_id, photo_name, user_id)

    await _save_message(sb, conversation_id, "user", photo_name, "photo_selected")

    yield sse_event({"stage": "generating"})

    # Get background image
    messages = await _get_messages(sb, conversation_id)
    bg_msg = next((m for m in reversed(messages) if m["type"] == "background"), None)
    if not bg_msg or not bg_msg.get("image_url"):
        yield sse_event({"error": "No background found", "done": True})
        return

    background_bytes = await sb.storage.from_("outputs").download(bg_msg["image_url"])
    person_bytes = await sb.storage.from_("personal-photos").download(f"{user_id}/{photo_name}")
    style = await _get_text_style(sb, user_id)

    composite_bytes = composite_person(background_bytes, person_bytes, style)

    # Store temporarily
    temp_name = f"comp_{uuid.uuid4().hex[:8]}.png"
    storage_path = f"{user_id}/{temp_name}"
    await sb.storage.from_("outputs").upload(
        storage_path, composite_bytes, {"content-type": "image/png"}
    )

    image_base64 = base64.b64encode(composite_bytes).decode()
    await _save_message(sb, conversation_id, "assistant",
                        "Here's the composite. Approve to add text, or pick a different photo.",
                        "composite", image_url=storage_path)

    yield sse_event({
        "message_type": "composite",
        "image_base64": image_base64,
        "image_url": storage_path,
    })
    yield sse_event({"done": True})


# ---------------------------------------------------------------------------
# Step 3: Typography
# ---------------------------------------------------------------------------

async def handle_step3_typography(
    sb, conversation_id: str, user_id: str
) -> AsyncGenerator[str, None]:
    """Add text overlay to composite image."""
    logger.info("step3_typography conversation=%s user=%s", conversation_id, user_id)

    await _save_message(sb, conversation_id, "user", "approved_composite", "approval")

    yield sse_event({"stage": "generating"})

    messages = await _get_messages(sb, conversation_id)

    # Get topic
    topic = next((m["content"] for m in messages if m["type"] == "text"), "Untitled")

    # Get composite image
    comp_msg = next((m for m in reversed(messages) if m["type"] == "composite"), None)
    if not comp_msg or not comp_msg.get("image_url"):
        yield sse_event({"error": "No composite found", "done": True})
        return

    composite_bytes = await sb.storage.from_("outputs").download(comp_msg["image_url"])
    style = await _get_text_style(sb, user_id)
    font_bytes = await _get_font_bytes(sb, user_id)

    final_bytes = overlay_text(composite_bytes, topic, style, font_bytes)

    # Store as final thumbnail
    temp_name = f"thumb_{uuid.uuid4().hex[:8]}.png"
    storage_path = f"{user_id}/{temp_name}"
    await sb.storage.from_("outputs").upload(
        storage_path, final_bytes, {"content-type": "image/png"}
    )

    image_base64 = base64.b64encode(final_bytes).decode()
    await _save_message(sb, conversation_id, "assistant",
                        "Here's your final thumbnail!",
                        "image", image_url=storage_path)

    yield sse_event({
        "message_type": "image",
        "image_base64": image_base64,
        "image_url": storage_path,
    })
    yield sse_event({"done": True})


# ---------------------------------------------------------------------------
# Save (same as before)
# ---------------------------------------------------------------------------

async def handle_save(
    sb, conversation_id: str, user_id: str
) -> AsyncGenerator[str, None]:
    logger.info("save conversation=%s user=%s", conversation_id, user_id)

    await _save_message(sb, conversation_id, "user", "SAVE_OUTPUT", "save")

    messages = await _get_messages(sb, conversation_id)
    image_message = next((m for m in reversed(messages) if m["type"] == "image"), None)

    if image_message and image_message.get("image_url"):
        temp_path = image_message["image_url"]
        final_filename = f"thumbnail_{uuid.uuid4().hex[:8]}.png"
        final_path = f"{user_id}/{final_filename}"

        image_data = await sb.storage.from_("outputs").download(temp_path)
        await sb.storage.from_("outputs").upload(
            final_path, image_data, {"content-type": "image/png"}
        )
        await sb.storage.from_("outputs").remove([temp_path])

        await sb.table("messages").update({"image_url": final_path}).eq("id", image_message["id"]).execute()

        await _save_message(sb, conversation_id, "assistant",
                            f"Thumbnail saved as {final_filename}", "text")

        yield sse_event({
            "done": True,
            "saved": True,
            "content": f"Thumbnail saved as {final_filename}",
            "path": final_path,
        })
    else:
        yield sse_event({"done": True, "error": "No image found to save"})


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

async def handle_chat_message(
    conversation_id: str,
    content: str,
    msg_type: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    logger.info("chat_message type=%s conversation=%s user=%s", msg_type, conversation_id, user_id)
    try:
        sb = await get_supabase()

        if msg_type == "text":
            # Step 1: Generate background
            async for event in handle_step1_background(sb, conversation_id, content, user_id):
                yield event
        elif msg_type == "approve_background":
            # Step 2a: Show photo grid
            async for event in handle_step2_show_photos(sb, conversation_id, user_id):
                yield event
        elif msg_type == "select_photo":
            # Step 2b: Composite selected photo
            async for event in handle_step2_composite(sb, conversation_id, content, user_id):
                yield event
        elif msg_type == "approve_composite":
            # Step 3: Add typography
            async for event in handle_step3_typography(sb, conversation_id, user_id):
                yield event
        elif msg_type == "save":
            async for event in handle_save(sb, conversation_id, user_id):
                yield event
        elif msg_type == "regenerate":
            # Re-do step 1 with the original topic
            messages = await _get_messages(sb, conversation_id)
            original = next((m["content"] for m in messages if m["type"] == "text"), content)
            regen_content = original
            if content and content != "REGENERATE":
                regen_content = f"{original}\n\nAdditional feedback: {content}"
            async for event in handle_step1_background(sb, conversation_id, regen_content, user_id):
                yield event
        else:
            logger.warning("unknown message type=%s", msg_type)
    except Exception as e:
        logger.exception("error in thumbnail pipeline type=%s: %s", msg_type, e)
        yield sse_event({"error": str(e), "done": True})
