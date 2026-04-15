import asyncio
import base64
import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import create_client
from supabase._async.client import create_client as create_async_client
from langgraph.types import Command

from auth import get_current_user
from config import settings
from services.script_pipeline import handle_script_chat_message
from services.thumbnail_graph import get_thumbnail_graph
from services.thumbnail_nodes import _make_preview

logger = logging.getLogger(__name__)

router = APIRouter()


def get_supabase():
    return create_client(settings.supabase_url, settings.supabase_service_key)


class ChatRequest(BaseModel):
    conversation_id: str
    content: str
    type: str = "text"
    image_url: str | None = None  # Storage path of uploaded image
    platforms: list[str] | None = None  # e.g. ["youtube", "instagram_post"]
    quality_tier: str | None = None


def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _get_async_supabase():
    return await create_async_client(
        settings.supabase_url, settings.supabase_service_key
    )


async def _save_message(sb, conversation_id, role, content, msg_type, image_url=None):
    """Save a message to the messages table for chat history."""
    payload = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "type": msg_type,
    }
    if image_url:
        payload["image_url"] = image_url
    await sb.table("messages").insert(payload).execute()


def _user_label(content: str) -> str:
    """Generate a readable label for the user's action."""
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict) and "action" in parsed:
            action = parsed["action"]
            if action == "approve":
                return "Aprovado ✓"
            if action == "feedback":
                return parsed.get("feedback") or "Refazer"
            if action == "select_photo":
                name = parsed.get("photo_name", "")
                feedback = parsed.get("feedback")
                if feedback:
                    return f'Selecionado: {name} — "{feedback}"'
                return f"Selecionado: {name}"
            if action == "provide_text":
                return f'Texto: "{parsed.get("text", "")}"'
            if action == "save":
                return "Salvar"
            return action
    except (json.JSONDecodeError, TypeError):
        pass
    return content


async def _resolve_image_url(sb, user_id: str, image_url: str | None) -> str | None:
    """Resolve an image URL to an outputs storage path.

    Handles:
    - None → None
    - Already in outputs (user_id/filename) → pass through
    - From another bucket (bucket/filename) → copy to outputs
    """
    if not image_url:
        return None

    import uuid as _uuid

    known_buckets = ["personal-photos", "reference-thumbs", "logos"]
    for bucket in known_buckets:
        if image_url.startswith(f"{bucket}/"):
            filename = image_url[len(bucket) + 1 :]
            src_path = f"{user_id}/{filename}"
            data = await sb.storage.from_(bucket).download(src_path)
            dest_name = f"uploaded_{_uuid.uuid4().hex[:6]}.png"
            dest_path = f"{user_id}/{dest_name}"
            await sb.storage.from_("outputs").upload(
                dest_path, data, {"content-type": "image/png"}
            )
            return dest_path

    # Already an outputs path
    return image_url


async def thumbnail_stream(
    conversation_id: str,
    content: str,
    user_id: str,
    image_url: str | None = None,
    platforms: list[str] | None = None,
    quality_tier: str | None = None,
):
    """Run the thumbnail graph and stream SSE events."""
    graph = await get_thumbnail_graph()
    config = {"configurable": {"thread_id": conversation_id}}
    sb = await _get_async_supabase()

    # Resolve image from other buckets to outputs
    image_url = await _resolve_image_url(sb, user_id, image_url)

    # Check if there's a pending interrupt (resume) or fresh start
    has_interrupt = False
    try:
        state = await graph.aget_state(config)
        if state and state.tasks:
            for task in state.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    has_interrupt = True
                    break
    except Exception:
        pass

    yield sse_event({"stage": "generating"})

    try:
        if has_interrupt:
            # Save user message
            label = _user_label(content)
            await _save_message(sb, conversation_id, "user", label, "text")

            # Resume from interrupt
            try:
                resume_value = json.loads(content)
                if not isinstance(resume_value, dict) or "action" not in resume_value:
                    resume_value = content
            except (json.JSONDecodeError, TypeError):
                resume_value = content

            # Include uploaded image in resume value if provided
            if image_url and isinstance(resume_value, dict):
                resume_value["image_url"] = image_url
            elif image_url and isinstance(resume_value, str):
                resume_value = {
                    "action": "use_as_background",
                    "image_url": image_url,
                    "feedback": resume_value if resume_value else None,
                }

            # Embed quality_tier in resume value so graph nodes can read it
            # (aupdate_state forks the checkpoint and breaks interrupt flow)
            if quality_tier and isinstance(resume_value, dict):
                resume_value["quality_tier"] = quality_tier

            result = await graph.ainvoke(Command(resume=resume_value), config)
        else:
            # Fresh start — save user message and set title
            await _save_message(sb, conversation_id, "user", content, "text")
            await (
                sb.table("conversations")
                .update({"title": content[:50]})
                .eq("id", conversation_id)
                .execute()
            )

            result = await graph.ainvoke(
                {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "topic": content,
                    "user_input": content,
                    "topic_research": "",
                    "platforms": platforms or ["youtube"],
                    "background_urls": {},
                    "photo_name": None,
                    "composite_urls": {},
                    "final_urls": {},
                    "thumb_text": None,
                    "user_intent": None,
                    "extra_instructions": None,
                    "photo_list": [],
                    "uploaded_image_url": image_url,
                    "quality_tier": quality_tier or "balanced",
                    "clarify_question": None,
                },
                config,
            )

        # Check if graph interrupted (needs user input)
        state = await graph.aget_state(config)
        pending_interrupts = []
        if state and state.tasks:
            for task in state.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    pending_interrupts.extend(task.interrupts)

        if pending_interrupts:
            interrupt_value = pending_interrupts[0].value
            msg_type = interrupt_value.get("type", "text")

            if msg_type in ("background", "composite", "image"):
                image_urls = interrupt_value.get("image_urls") or {}
                if image_urls:
                    images_payload = {}
                    for platform, paths in image_urls.items():
                        url = paths.get("url", "") if isinstance(paths, dict) else paths
                        preview_url = (
                            paths.get("preview_url", "")
                            if isinstance(paths, dict)
                            else ""
                        )

                        # Download preview (or original as fallback) for tiny base64
                        preview_data = None
                        for attempt in range(3):
                            try:
                                dl_path = preview_url or url
                                preview_data = await sb.storage.from_(
                                    "outputs"
                                ).download(dl_path)
                                break
                            except Exception:
                                if attempt < 2:
                                    await asyncio.sleep(1)

                        if not preview_data:
                            continue

                        # Generate tiny ~200px placeholder for SSE
                        try:
                            tiny_bytes = _make_preview(preview_data, max_edge=200)
                            tiny_b64 = base64.b64encode(tiny_bytes).decode()
                        except Exception:
                            tiny_b64 = base64.b64encode(preview_data).decode()

                        images_payload[platform] = {
                            "preview_base64": tiny_b64,
                            "preview_url": preview_url,
                            "url": url,
                        }

                    if not images_payload:
                        yield sse_event(
                            {"error": "Falha ao baixar imagem", "done": True}
                        )
                        return

                    # Save assistant message
                    labels = {
                        "background": "Aqui está o fundo.",
                        "composite": "Aqui está a composição.",
                        "image": "Aqui está sua thumbnail final!",
                    }
                    first_paths = next(iter(image_urls.values()))
                    first_url = (
                        first_paths.get("url", "")
                        if isinstance(first_paths, dict)
                        else first_paths
                    )
                    await _save_message(
                        sb,
                        conversation_id,
                        "assistant",
                        labels.get(msg_type, ""),
                        msg_type,
                        image_url=first_url,
                    )

                    first_payload = next(iter(images_payload.values()))
                    event_data: dict = {
                        "done": True,
                        "message_type": msg_type,
                        "images": images_payload,
                        # Backward compat
                        "image_base64": first_payload["preview_base64"],
                        "image_url": first_url,
                    }
                    if interrupt_value.get("clarify_question"):
                        event_data["clarify_question"] = interrupt_value[
                            "clarify_question"
                        ]
                    yield sse_event(event_data)
                    return
            elif msg_type == "photo_grid":
                photos_json = json.dumps(interrupt_value.get("photos", []))
                await _save_message(
                    sb,
                    conversation_id,
                    "assistant",
                    photos_json,
                    "photo_grid",
                )
                yield sse_event(
                    {
                        "done": True,
                        "message_type": "photo_grid",
                        "content": photos_json,
                    }
                )
                return
            elif msg_type == "text_prompt":
                await _save_message(
                    sb,
                    conversation_id,
                    "assistant",
                    "Qual texto você quer na thumbnail?",
                    "text_prompt",
                )
                yield sse_event(
                    {
                        "done": True,
                        "message_type": "text_prompt",
                        "content": "Qual texto você quer na thumbnail?",
                        "suggestion": interrupt_value.get("suggestion", ""),
                    }
                )
                return
        else:
            # Graph completed (saved)
            await _save_message(
                sb,
                conversation_id,
                "assistant",
                "Thumbnail salva!",
                "text",
            )
            final_urls = result.get("final_urls") or {}
            first_paths = next(iter(final_urls.values()), {})
            first_url = (
                first_paths.get("url", "")
                if isinstance(first_paths, dict)
                else first_paths or ""
            )
            yield sse_event(
                {
                    "done": True,
                    "saved": True,
                    "content": "Thumbnail salva!",
                    "paths": final_urls,
                    "path": first_url,
                }
            )
            return

    except Exception as e:
        logger.exception("thumbnail graph error")
        yield sse_event({"error": str(e), "done": True})
        return

    yield sse_event({"done": True})


@router.get("/api/conversations/{conversation_id}/status")
async def conversation_status(
    conversation_id: str, user_id: str = Depends(get_current_user)
):
    """Check if a thumbnail conversation has a pending interrupt.

    When the graph is waiting at an image interrupt, returns the interrupt
    payload (with tiny preview base64) so the frontend can display it even
    if the original SSE stream was abandoned.
    """
    try:
        graph = await get_thumbnail_graph()
        config = {"configurable": {"thread_id": conversation_id}}
        state = await graph.aget_state(config)
        if state and state.tasks:
            for task in state.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    interrupt_value = task.interrupts[0].value
                    msg_type = interrupt_value.get("type", "unknown")
                    result: dict = {
                        "status": "waiting",
                        "type": msg_type,
                    }

                    # For image interrupts, build the same payload the SSE
                    # would have sent so the frontend can display it.
                    if msg_type in ("background", "composite", "image"):
                        image_urls = interrupt_value.get("image_urls") or {}
                        if image_urls:
                            sb = await _get_async_supabase()
                            images_payload: dict = {}
                            for platform, paths in image_urls.items():
                                url = (
                                    paths.get("url", "")
                                    if isinstance(paths, dict)
                                    else paths
                                )
                                preview_url = (
                                    paths.get("preview_url", "")
                                    if isinstance(paths, dict)
                                    else ""
                                )
                                try:
                                    dl_path = preview_url or url
                                    preview_data = await sb.storage.from_(
                                        "outputs"
                                    ).download(dl_path)
                                    tiny_bytes = _make_preview(
                                        preview_data, max_edge=200
                                    )
                                    tiny_b64 = base64.b64encode(tiny_bytes).decode()
                                except Exception:
                                    tiny_b64 = ""
                                images_payload[platform] = {
                                    "preview_base64": tiny_b64,
                                    "preview_url": preview_url,
                                    "url": url,
                                }
                            if images_payload:
                                result["images"] = images_payload

                    elif msg_type == "photo_grid":
                        result["photos"] = interrupt_value.get("photos", [])
                    elif msg_type == "text_prompt":
                        result["suggestion"] = interrupt_value.get("suggestion", "")

                    # Also save the assistant message to DB so it persists
                    labels = {
                        "background": "Aqui está o fundo.",
                        "composite": "Aqui está a composição.",
                        "image": "Aqui está sua thumbnail final!",
                        "photo_grid": "",
                        "text_prompt": "Qual texto você quer na thumbnail?",
                    }
                    if msg_type in labels:
                        sb = await _get_async_supabase()
                        content = labels[msg_type]
                        if msg_type == "photo_grid":
                            content = json.dumps(interrupt_value.get("photos", []))
                        image_urls_raw = interrupt_value.get("image_urls") or {}
                        first_url = None
                        if image_urls_raw:
                            fp = next(iter(image_urls_raw.values()))
                            first_url = (
                                fp.get("url", "") if isinstance(fp, dict) else fp
                            )
                        await _save_message(
                            sb,
                            conversation_id,
                            "assistant",
                            content,
                            msg_type,
                            image_url=first_url,
                        )

                    return result
        if state and state.values:
            return {"status": "idle"}
        return {"status": "new"}
    except Exception:
        logger.exception("conversation status check failed")
        return {"status": "unknown"}


@router.post("/api/chat")
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user)):
    sb = get_supabase()
    conv = (
        sb.table("conversations")
        .select("mode, model")
        .eq("id", request.conversation_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    mode = conv.data.get("mode", "thumbnail") if conv.data else "thumbnail"
    model = conv.data.get("model") if conv.data else None

    if mode == "script":
        stream = handle_script_chat_message(
            conversation_id=request.conversation_id,
            content=request.content,
            user_id=user_id,
            model=model,
        )
    else:
        stream = thumbnail_stream(
            conversation_id=request.conversation_id,
            content=request.content,
            user_id=user_id,
            image_url=request.image_url,
            platforms=request.platforms,
            quality_tier=request.quality_tier,
        )

    return StreamingResponse(stream, media_type="text/event-stream")
