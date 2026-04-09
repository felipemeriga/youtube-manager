import json
import base64
import logging
import random
import uuid
from typing import AsyncGenerator

from supabase._async.client import create_client as create_async_client

from config import settings
from services.llm import ask_llm
from services.nano_banana import generate_thumbnail

logger = logging.getLogger(__name__)


async def get_supabase():
    return await create_async_client(
        settings.supabase_url, settings.supabase_service_key
    )


def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def fetch_all_assets(sb, user_id: str, bucket: str) -> list[bytes]:
    files = await sb.storage.from_(bucket).list(path=user_id)
    result = []
    for f in files:
        if f.get("name"):
            data = await sb.storage.from_(bucket).download(f"{user_id}/{f['name']}")
            result.append(data)
    return result


MAX_PERSONAL_PHOTOS = 5

CREATIVE_BRIEF_MODEL = "claude-haiku-4-5-20251001"

CREATIVE_BRIEF_SYSTEM = """You are a YouTube thumbnail design expert. Your job is to research current trends and write a detailed creative brief for an image generation AI.

You have access to web search — use it to find:
- Current YouTube thumbnail trends for this topic/niche
- What top creators are doing with their thumbnails right now
- Color psychology and visual elements that drive clicks
- Any relevant current events or visual trends

Output a detailed image generation prompt that includes:
1. Specific visual composition (layout, focal point, rule of thirds)
2. Color palette (specific hex codes or color descriptions based on trends)
3. Typography style (font feel, size emphasis, text placement)
4. Emotional tone and expression guidance
5. Background elements and effects
6. Any trending visual techniques you found

Write the prompt as direct instructions to an image generator. Be specific and actionable, not vague."""


async def _create_creative_brief(topic: str) -> str:
    """Use Claude Haiku with web search to create an informed thumbnail brief."""
    if not settings.anthropic_api_key:
        return ""

    try:
        brief = await ask_llm(
            system=CREATIVE_BRIEF_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Create a detailed thumbnail generation prompt for this topic:\n\n"
                        f"{topic}\n\n"
                        f"Research current trends first, then write the creative brief."
                    ),
                }
            ],
            model=CREATIVE_BRIEF_MODEL,
        )
        logger.info("creative brief generated, length=%d", len(brief))
        return brief
    except Exception:
        logger.exception("creative brief generation failed, using raw prompt")
        return ""


async def handle_text_message(
    sb, conversation_id: str, content: str, user_id: str
) -> AsyncGenerator[str, None]:
    logger.info(
        "text_message conversation=%s user=%s content=%s",
        conversation_id,
        user_id,
        content[:80],
    )

    # Save user message
    await (
        sb.table("messages")
        .insert(
            {
                "conversation_id": conversation_id,
                "role": "user",
                "content": content,
                "type": "text",
            }
        )
        .execute()
    )

    # Update conversation title from first message
    await (
        sb.table("conversations")
        .update({"title": content[:50]})
        .eq("id", conversation_id)
        .execute()
    )

    yield sse_event({"stage": "analyzing"})

    # Generate creative brief with Claude (web search enabled)
    creative_brief = await _create_creative_brief(content)

    yield sse_event({"stage": "generating"})

    # Fetch assets
    logger.info("downloading assets for user=%s", user_id)
    ref_thumbs = await fetch_all_assets(sb, user_id, "reference-thumbs")
    logos = await fetch_all_assets(sb, user_id, "logos")

    all_photo_files = await sb.storage.from_("personal-photos").list(path=user_id)
    photo_names = [f["name"] for f in all_photo_files if f.get("name")]
    selected_names = random.sample(
        photo_names, min(MAX_PERSONAL_PHOTOS, len(photo_names))
    )
    photos = []
    for name in selected_names:
        data = await sb.storage.from_("personal-photos").download(f"{user_id}/{name}")
        photos.append(data)
    logger.info(
        "downloaded: ref_thumbs=%d logos=%d photos=%d/%d",
        len(ref_thumbs),
        len(logos),
        len(photos),
        len(photo_names),
    )

    # Build prompt with creative brief context
    brief_section = ""
    if creative_brief:
        brief_section = (
            f"\n\n## Creative Brief (from trend research):\n{creative_brief}\n\n"
            "Use the creative brief above to inform your design choices, "
            "but ALWAYS prioritize matching the reference thumbnails' style.\n"
        )

    prompt = (
        f"Topic: {content}\n"
        f"{brief_section}\n"
        "CRITICAL INSTRUCTIONS:\n"
        "You MUST replicate the EXACT same visual style, layout, and branding "
        "from the reference thumbnails. Study them carefully:\n"
        "- The channel logo image is provided separately — place it in the "
        "EXACT same position and size as it appears in the reference thumbnails "
        "(typically top-left corner). Use the actual logo image, do NOT "
        "recreate or write the logo text manually.\n"
        "- Use the EXACT same font/typeface as the reference thumbnails for "
        "all title text. Match the font family, weight, size, color, stroke, "
        "shadow, and letter spacing precisely.\n"
        "- Same composition structure (person placement, background style)\n"
        "- Same color grading, lighting, and visual effects\n"
        "- Same overall quality and professional polish\n\n"
        "The ONLY things that should change from the references are:\n"
        "1. The title text (use the topic above)\n"
        "2. The background theme/elements (match the topic)\n"
        "3. The person's photo (use one of the personal photos provided)\n\n"
        "Everything else — logo, layout, text style, composition — "
        "must be virtually identical to the references."
    )

    logger.info("calling generate_thumbnail")
    image_bytes = await generate_thumbnail(
        prompt=prompt,
        reference_images=ref_thumbs,
        personal_photos=photos,
        logos=logos,
    )
    logger.info("thumbnail generated, size=%d bytes", len(image_bytes))

    # Store temporarily in outputs bucket
    temp_filename = f"temp_{uuid.uuid4().hex[:8]}.png"
    storage_path = f"{user_id}/{temp_filename}"
    await sb.storage.from_("outputs").upload(
        storage_path, image_bytes, {"content-type": "image/png"}
    )

    # Save image message
    image_base64 = base64.b64encode(image_bytes).decode()
    await (
        sb.table("messages")
        .insert(
            {
                "conversation_id": conversation_id,
                "role": "assistant",
                "content": "Here's your generated thumbnail:",
                "type": "image",
                "image_url": storage_path,
            }
        )
        .execute()
    )

    yield sse_event(
        {
            "message_type": "image",
            "image_base64": image_base64,
            "image_url": storage_path,
        }
    )
    yield sse_event({"done": True})


async def handle_save(
    sb, conversation_id: str, user_id: str
) -> AsyncGenerator[str, None]:
    logger.info("save conversation=%s user=%s", conversation_id, user_id)

    await (
        sb.table("messages")
        .insert(
            {
                "conversation_id": conversation_id,
                "role": "user",
                "content": "SAVE_OUTPUT",
                "type": "save",
            }
        )
        .execute()
    )

    response = (
        await sb.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )
    messages = response.data
    image_message = next((m for m in reversed(messages) if m["type"] == "image"), None)

    if image_message and image_message.get("image_url"):
        temp_path = image_message["image_url"]
        final_filename = f"thumbnail_{uuid.uuid4().hex[:8]}.png"
        final_path = f"{user_id}/{final_filename}"
        logger.info("renaming %s -> %s", temp_path, final_path)

        image_data = await sb.storage.from_("outputs").download(temp_path)
        await sb.storage.from_("outputs").upload(
            final_path, image_data, {"content-type": "image/png"}
        )
        await sb.storage.from_("outputs").remove([temp_path])

        await (
            sb.table("messages")
            .update({"image_url": final_path})
            .eq("id", image_message["id"])
            .execute()
        )

        await (
            sb.table("messages")
            .insert(
                {
                    "conversation_id": conversation_id,
                    "role": "assistant",
                    "content": f"Thumbnail saved to outputs as {final_filename}",
                    "type": "text",
                }
            )
            .execute()
        )
        logger.info("thumbnail saved as %s", final_filename)

        yield sse_event(
            {
                "done": True,
                "saved": True,
                "content": f"Thumbnail saved as {final_filename}",
                "path": final_path,
            }
        )
    else:
        logger.warning("no image found to save in conversation=%s", conversation_id)
        yield sse_event({"done": True, "error": "No image found to save"})


async def handle_regenerate(
    sb, conversation_id: str, content: str, user_id: str
) -> AsyncGenerator[str, None]:
    logger.info(
        "regenerate conversation=%s user=%s feedback=%s",
        conversation_id,
        user_id,
        (content or "none")[:80],
    )

    await (
        sb.table("messages")
        .insert(
            {
                "conversation_id": conversation_id,
                "role": "user",
                "content": content or "REGENERATE",
                "type": "regenerate",
            }
        )
        .execute()
    )

    # Get original user request
    response = (
        await sb.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )
    messages = response.data
    user_request = next((m for m in messages if m["type"] == "text"), None)

    original_content = user_request["content"] if user_request else ""
    regenerate_content = original_content
    if content and content != "REGENERATE":
        regenerate_content = f"{original_content}\n\nAdditional feedback: {content}"

    async for event in handle_text_message(
        sb, conversation_id, regenerate_content, user_id
    ):
        yield event


async def handle_chat_message(
    conversation_id: str,
    content: str,
    msg_type: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    logger.info(
        "chat_message type=%s conversation=%s user=%s",
        msg_type,
        conversation_id,
        user_id,
    )
    try:
        sb = await get_supabase()

        if msg_type == "text":
            async for event in handle_text_message(
                sb, conversation_id, content, user_id
            ):
                yield event
        elif msg_type == "save":
            async for event in handle_save(sb, conversation_id, user_id):
                yield event
        elif msg_type == "regenerate":
            async for event in handle_regenerate(sb, conversation_id, content, user_id):
                yield event
        else:
            logger.warning("unknown message type=%s", msg_type)
    except Exception as e:
        logger.exception("error in chat pipeline type=%s: %s", msg_type, e)
        yield sse_event({"error": str(e), "done": True})
