import json
import base64
import logging
import uuid
from typing import AsyncGenerator

from supabase import create_client

from config import settings
from services.guardian import ask_guardian
from services.nano_banana import generate_thumbnail

logger = logging.getLogger(__name__)


def get_supabase():
    return create_client(settings.supabase_url, settings.supabase_service_key)


def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def list_asset_urls(sb, user_id: str, bucket: str) -> list[dict]:
    """Return list of {name, url} for all files in a user's bucket folder."""
    files = sb.storage.from_(bucket).list(path=user_id)
    result = []
    for f in files:
        if f.get("name"):
            url = sb.storage.from_(bucket).get_public_url(f"{user_id}/{f['name']}")
            result.append({"name": f["name"], "url": url})
    return result


def fetch_all_assets(sb, user_id: str, bucket: str) -> list[bytes]:
    files = sb.storage.from_(bucket).list(path=user_id)
    result = []
    for f in files:
        if f.get("name"):
            data = sb.storage.from_(bucket).download(f"{user_id}/{f['name']}")
            result.append(data)
    return result


SYSTEM_PROMPT = """You are a professional YouTube thumbnail designer. The user will describe what thumbnail they want.

You will receive:
- Reference thumbnails with public URLs — view them to understand the style
- Personal photos with public URLs — view them to choose the best one
- Available font names for text

View all provided image URLs to analyze them visually. Then propose a detailed thumbnail plan including:
- Which reference thumbnail style to follow and why (reference by name)
- Which personal photo to use and why (reference by name)
- Text placement, font choice, and color scheme
- Overall composition and mood

Be specific and visual in your description. The plan will be used to generate the actual thumbnail."""


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
    sb.table("messages").insert(
        {
            "conversation_id": conversation_id,
            "role": "user",
            "content": content,
            "type": "text",
        }
    ).execute()
    logger.debug("saved user message to db")

    # Update conversation title from first message
    sb.table("conversations").update({"title": content[:50]}).eq(
        "id", conversation_id
    ).execute()

    yield sse_event({"stage": "analyzing"})

    # Get public URLs for all assets so Guardian can view them
    logger.info("listing assets for user=%s", user_id)
    ref_thumbs = list_asset_urls(sb, user_id, "reference-thumbs")
    photos = list_asset_urls(sb, user_id, "personal-photos")
    font_files = sb.storage.from_("fonts").list(path=user_id)
    font_names = [f["name"] for f in font_files if f.get("name")]
    logger.info(
        "assets found: ref_thumbs=%d photos=%d fonts=%d",
        len(ref_thumbs),
        len(photos),
        len(font_names),
    )

    def format_assets(label: str, assets: list[dict]) -> str:
        if not assets:
            return f"{label}: none"
        lines = [f"  - {a['name']}: {a['url']}" for a in assets]
        return f"{label} ({len(assets)}):\n" + "\n".join(lines)

    # Build prompt with public URLs for images
    asset_summary = "\n".join(
        [
            format_assets("Reference thumbnails", ref_thumbs),
            format_assets("Personal photos", photos),
            f"Fonts ({len(font_names)}): {', '.join(font_names) or 'none'}",
        ]
    )
    full_prompt = f"{asset_summary}\n\nUser request: {content}"

    # Ask Guardian for a plan
    logger.info("sending prompt to Guardian (%d chars)", len(full_prompt))
    plan = await ask_guardian(prompt=full_prompt, system=SYSTEM_PROMPT)
    logger.info("Guardian responded with plan (%d chars)", len(plan))

    # Stream plan tokens
    for token in plan.split():
        yield sse_event({"token": token + " "})

    # Save plan message
    sb.table("messages").insert(
        {
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": plan,
            "type": "plan",
        }
    ).execute()
    logger.info("plan saved to db, streaming done")

    yield sse_event({"message_type": "plan"})
    yield sse_event({"done": True})


async def handle_approval(
    sb, conversation_id: str, user_id: str
) -> AsyncGenerator[str, None]:
    logger.info("approval conversation=%s user=%s", conversation_id, user_id)

    # Save approval message
    sb.table("messages").insert(
        {
            "conversation_id": conversation_id,
            "role": "user",
            "content": "APPROVED",
            "type": "approval",
        }
    ).execute()

    yield sse_event({"stage": "generating"})

    # Get conversation history to find the plan
    messages = (
        sb.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
        .data
    )
    plan_message = next((m for m in reversed(messages) if m["type"] == "plan"), None)
    user_request = next((m for m in messages if m["type"] == "text"), None)
    logger.info(
        "found plan=%s user_request=%s",
        bool(plan_message),
        bool(user_request),
    )

    prompt_parts = []
    if user_request:
        prompt_parts.append(f"User request: {user_request['content']}")
    if plan_message:
        prompt_parts.append(f"Approved plan: {plan_message['content']}")
    prompt_parts.append(
        "Generate a professional YouTube thumbnail based on the above plan."
    )

    # Fetch assets
    logger.info("downloading assets for thumbnail generation")
    ref_thumbs = fetch_all_assets(sb, user_id, "reference-thumbs")
    photos = fetch_all_assets(sb, user_id, "personal-photos")
    fonts = fetch_all_assets(sb, user_id, "fonts")
    logger.info(
        "downloaded: ref_thumbs=%d photos=%d fonts=%d",
        len(ref_thumbs),
        len(photos),
        len(fonts),
    )

    # Generate thumbnail
    logger.info("calling generate_thumbnail")
    image_bytes = await generate_thumbnail(
        prompt="\n".join(prompt_parts),
        reference_images=ref_thumbs,
        personal_photos=photos,
        font_files=fonts,
    )
    logger.info("thumbnail generated, size=%d bytes", len(image_bytes))

    # Store temporarily in outputs bucket
    temp_filename = f"temp_{uuid.uuid4().hex[:8]}.png"
    storage_path = f"{user_id}/{temp_filename}"
    sb.storage.from_("outputs").upload(
        storage_path, image_bytes, {"content-type": "image/png"}
    )
    logger.info("uploaded temp thumbnail to %s", storage_path)

    # Save image message
    image_base64 = base64.b64encode(image_bytes).decode()
    sb.table("messages").insert(
        {
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": "Here's your generated thumbnail:",
            "type": "image",
            "image_url": storage_path,
        }
    ).execute()

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

    # Save the save message
    sb.table("messages").insert(
        {
            "conversation_id": conversation_id,
            "role": "user",
            "content": "SAVE_OUTPUT",
            "type": "save",
        }
    ).execute()

    # Find the most recent image message
    messages = (
        sb.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
        .data
    )
    image_message = next((m for m in reversed(messages) if m["type"] == "image"), None)

    if image_message and image_message.get("image_url"):
        temp_path = image_message["image_url"]
        final_filename = f"thumbnail_{uuid.uuid4().hex[:8]}.png"
        final_path = f"{user_id}/{final_filename}"
        logger.info("renaming %s -> %s", temp_path, final_path)

        # Download and re-upload with final name
        image_data = sb.storage.from_("outputs").download(temp_path)
        sb.storage.from_("outputs").upload(
            final_path, image_data, {"content-type": "image/png"}
        )
        sb.storage.from_("outputs").remove([temp_path])

        # Update the image message with final URL
        sb.table("messages").update({"image_url": final_path}).eq(
            "id", image_message["id"]
        ).execute()

        # Save confirmation message
        sb.table("messages").insert(
            {
                "conversation_id": conversation_id,
                "role": "assistant",
                "content": f"Thumbnail saved to outputs as {final_filename}",
                "type": "text",
            }
        ).execute()
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

    # Save regenerate message
    sb.table("messages").insert(
        {
            "conversation_id": conversation_id,
            "role": "user",
            "content": content or "REGENERATE",
            "type": "regenerate",
        }
    ).execute()

    # Re-run generation with optional feedback
    async for event in handle_approval(sb, conversation_id, user_id):
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
    sb = get_supabase()

    if msg_type == "text":
        async for event in handle_text_message(sb, conversation_id, content, user_id):
            yield event
    elif msg_type == "approval":
        async for event in handle_approval(sb, conversation_id, user_id):
            yield event
    elif msg_type == "save":
        async for event in handle_save(sb, conversation_id, user_id):
            yield event
    elif msg_type == "regenerate":
        async for event in handle_regenerate(sb, conversation_id, content, user_id):
            yield event
    else:
        logger.warning("unknown message type=%s", msg_type)
