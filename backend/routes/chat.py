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

logger = logging.getLogger(__name__)

router = APIRouter()


def get_supabase():
    return create_client(settings.supabase_url, settings.supabase_service_key)


class ChatRequest(BaseModel):
    conversation_id: str
    content: str
    type: str = "text"


def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _get_async_supabase():
    return await create_async_client(
        settings.supabase_url, settings.supabase_service_key
    )


async def thumbnail_stream(conversation_id: str, content: str, user_id: str):
    """Run the thumbnail graph and stream SSE events."""
    graph = get_thumbnail_graph()
    config = {"configurable": {"thread_id": conversation_id}}

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
            # Resume from interrupt — try parsing content as JSON action
            try:
                resume_value = json.loads(content)
                if not isinstance(resume_value, dict) or "action" not in resume_value:
                    resume_value = content
            except (json.JSONDecodeError, TypeError):
                resume_value = content

            result = await graph.ainvoke(Command(resume=resume_value), config)
        else:
            # Fresh start — provide full initial state
            result = await graph.ainvoke(
                {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "topic": content,
                    "user_input": content,
                    "topic_research": "",
                    "background_url": None,
                    "photo_name": None,
                    "composite_url": None,
                    "final_url": None,
                    "thumb_text": None,
                    "user_intent": None,
                    "extra_instructions": None,
                    "photo_list": [],
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
                image_url = interrupt_value.get("image_url", "")
                if image_url:
                    sb = await _get_async_supabase()
                    image_data = await sb.storage.from_("outputs").download(image_url)
                    image_b64 = base64.b64encode(image_data).decode()
                    yield sse_event(
                        {
                            "message_type": msg_type,
                            "image_base64": image_b64,
                            "image_url": image_url,
                        }
                    )
            elif msg_type == "photo_grid":
                yield sse_event(
                    {
                        "message_type": "photo_grid",
                        "content": json.dumps(interrupt_value.get("photos", [])),
                    }
                )
            elif msg_type == "text_prompt":
                yield sse_event(
                    {
                        "message_type": "text_prompt",
                        "content": "What text do you want on the thumbnail?",
                        "suggestion": interrupt_value.get("suggestion", ""),
                    }
                )
        else:
            # Graph completed (saved)
            final_url = result.get("final_url", "")
            yield sse_event(
                {
                    "saved": True,
                    "content": "Thumbnail saved!",
                    "path": final_url,
                }
            )

    except Exception as e:
        logger.exception("thumbnail graph error")
        yield sse_event({"error": str(e)})

    yield sse_event({"done": True})


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
        )

    return StreamingResponse(stream, media_type="text/event-stream")
