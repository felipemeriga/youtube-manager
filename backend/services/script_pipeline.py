import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import AsyncGenerator

from supabase._async.client import create_client as create_async_client

from config import settings
from persona import format_persona
from services.guardian import ask_guardian

logger = logging.getLogger(__name__)


async def get_supabase():
    return await create_async_client(
        settings.supabase_url, settings.supabase_service_key
    )


def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[-\s]+", "-", text)
    return text[:60]


_NO_TOOLS = (
    "\n\nIMPORTANT: Respond with text only. Do NOT use any tools. "
    "Do NOT create, read, or write any files. Do NOT run any commands. "
    "Just reply with the requested content directly in your response."
)

IDEATION_PROMPT = (
    "You are a YouTube content strategist. Your ONLY task is to suggest video topics. "
    "Do NOT write scripts, outlines, or any content.\n\n"
    "Based on the user's input, suggest 5-10 video topics related to RECENT news and "
    "trends (last 1-2 weeks). The channel is a Brazilian Portuguese tech channel.\n\n"
    "Return ONLY a valid JSON array with no markdown fences, no explanation, no extra text. "
    "Each element must have: "
    '"title" (string), "angle" (string), "why_timely" (string), '
    '"interest" (string: "high", "medium", or "low").\n\n'
    "Example format:\n"
    '[{"title": "...", "angle": "...", "why_timely": "...", "interest": "high"}]'
    + _NO_TOOLS
)

RESEARCH_PROMPT = (
    "Research this topic in depth: {topic}. Find recent articles, data, statistics, "
    "expert opinions, and real-world examples. Provide a structured summary with "
    "sources. Focus on content from the last 1-2 weeks."
    + _NO_TOOLS
)

OUTLINE_PROMPT = (
    "{persona}\n\nBased on this research:\n{research}\n\nCreate a video outline for "
    "the topic: {topic}. Include:\n- Hook (first 30 seconds)\n- Sections with key "
    "points and estimated duration\n- Transitions between sections\n- Call to action\n"
    "- Total estimated video duration\n\nFormat as structured markdown."
    + _NO_TOOLS
)

SCRIPT_PROMPT = (
    "{persona}\n\nBased on this outline:\n{outline}\n\nAnd this research:\n{research}"
    "\n\nWrite a complete video script in Brazilian Portuguese. Include:\n"
    "- Word-for-word dialogue for each section\n- Timing markers\n"
    "- Stats and data with inline citations from the research\n\n"
    "Format as markdown with clear section headers."
    + _NO_TOOLS
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _save_message(
    sb, conversation_id: str, role: str, content: str, msg_type: str
):
    await (
        sb.table("messages")
        .insert(
            {
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "type": msg_type,
            }
        )
        .execute()
    )


async def _get_messages(sb, conversation_id: str) -> list[dict]:
    response = (
        await sb.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )
    return response.data


def _find_message(messages: list[dict], msg_type: str) -> dict | None:
    return next((m for m in messages if m["type"] == msg_type), None)


def _find_last_message(messages: list[dict], msg_type: str) -> dict | None:
    return next((m for m in reversed(messages) if m["type"] == msg_type), None)


# ---------------------------------------------------------------------------
# Stage handlers
# ---------------------------------------------------------------------------


async def handle_ideation(
    conversation_id: str, user_message: str, user_id: str
) -> AsyncGenerator[str, None]:
    logger.info("ideation conversation=%s user=%s", conversation_id, user_id)
    sb = await get_supabase()

    await _save_message(sb, conversation_id, "user", user_message, "text")

    await (
        sb.table("conversations")
        .update({"title": user_message[:50]})
        .eq("id", conversation_id)
        .execute()
    )

    yield sse_event({"stage": "finding_trends"})

    topics_response = await ask_guardian(IDEATION_PROMPT, context=user_message)

    await _save_message(sb, conversation_id, "assistant", topics_response, "topics")

    yield sse_event(
        {"done": True, "message_type": "topics", "content": topics_response}
    )


async def handle_topic_selection(
    conversation_id: str, topic_index: int, user_id: str
) -> AsyncGenerator[str, None]:
    logger.info(
        "topic_selection conversation=%s topic=%d user=%s",
        conversation_id,
        topic_index,
        user_id,
    )
    sb = await get_supabase()

    await _save_message(
        sb, conversation_id, "user", str(topic_index), "topic_selection"
    )

    messages = await _get_messages(sb, conversation_id)
    topics_msg = _find_message(messages, "topics")

    topics = json.loads(topics_msg["content"])
    topic = topics[topic_index]
    topic_title = topic.get("title", str(topic))

    # Stage 1: Research
    yield sse_event({"stage": "researching"})

    research_prompt = RESEARCH_PROMPT.format(topic=topic_title)
    research = await ask_guardian(research_prompt)

    await _save_message(sb, conversation_id, "assistant", research, "research")

    # Stage 2: Outline
    yield sse_event({"stage": "writing_outline"})

    persona = format_persona()
    outline_prompt = OUTLINE_PROMPT.format(
        persona=persona, research=research, topic=topic_title
    )
    outline = await ask_guardian(outline_prompt)

    await _save_message(sb, conversation_id, "assistant", outline, "outline")

    yield sse_event({"done": True, "message_type": "outline", "content": outline})


async def handle_outline_approval(
    conversation_id: str, approved: bool, feedback: str, user_id: str
) -> AsyncGenerator[str, None]:
    logger.info(
        "outline_approval conversation=%s approved=%s user=%s",
        conversation_id,
        approved,
        user_id,
    )
    sb = await get_supabase()

    approval_content = "approved" if approved else f"rejected: {feedback}"
    await _save_message(sb, conversation_id, "user", approval_content, "approval")

    messages = await _get_messages(sb, conversation_id)
    research_msg = _find_last_message(messages, "research")
    research = research_msg["content"] if research_msg else ""

    topics_msg = _find_message(messages, "topics")
    selection_msg = _find_message(messages, "topic_selection")
    topic_title = ""
    if topics_msg and selection_msg:
        topics = json.loads(topics_msg["content"])
        idx = int(selection_msg["content"])
        topic_title = topics[idx].get("title", "")

    if approved:
        yield sse_event({"stage": "writing_script"})

        outline_msg = _find_last_message(messages, "outline")
        outline = outline_msg["content"] if outline_msg else ""
        persona = format_persona()

        script_prompt = SCRIPT_PROMPT.format(
            persona=persona, outline=outline, research=research
        )
        script = await ask_guardian(script_prompt)

        await _save_message(sb, conversation_id, "assistant", script, "script")

        yield sse_event({"done": True, "message_type": "script", "content": script})
    else:
        yield sse_event({"stage": "writing_outline"})

        outline_msg = _find_last_message(messages, "outline")
        old_outline = outline_msg["content"] if outline_msg else ""
        persona = format_persona()

        outline_prompt = OUTLINE_PROMPT.format(
            persona=persona, research=research, topic=topic_title
        )
        outline_prompt += (
            f"\n\nPrevious outline:\n{old_outline}\n\nFeedback: {feedback}"
        )
        new_outline = await ask_guardian(outline_prompt)

        await _save_message(sb, conversation_id, "assistant", new_outline, "outline")

        yield sse_event(
            {"done": True, "message_type": "outline", "content": new_outline}
        )


async def handle_script_approval(
    conversation_id: str, approved: bool, feedback: str, user_id: str
) -> AsyncGenerator[str, None]:
    logger.info(
        "script_approval conversation=%s approved=%s user=%s",
        conversation_id,
        approved,
        user_id,
    )
    sb = await get_supabase()

    approval_content = "approved" if approved else f"rejected: {feedback}"
    await _save_message(sb, conversation_id, "user", approval_content, "approval")

    messages = await _get_messages(sb, conversation_id)

    if approved:
        yield sse_event({"stage": "saving"})

        script_msg = _find_last_message(messages, "script")
        script_content = script_msg["content"] if script_msg else ""

        topics_msg = _find_message(messages, "topics")
        selection_msg = _find_message(messages, "topic_selection")
        slug = "script"
        if topics_msg and selection_msg:
            topics = json.loads(topics_msg["content"])
            idx = int(selection_msg["content"])
            slug = slugify(topics[idx].get("title", "script"))

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = f"{user_id}/{slug}-{timestamp}.md"

        await sb.storage.from_("scripts").upload(
            path,
            script_content.encode("utf-8"),
            {"content-type": "text/markdown"},
        )

        await _save_message(
            sb, conversation_id, "assistant", f"Script saved to {path}", "saved"
        )

        yield sse_event({"done": True, "saved": True, "path": path})
    else:
        yield sse_event({"stage": "writing_script"})

        research_msg = _find_last_message(messages, "research")
        research = research_msg["content"] if research_msg else ""
        outline_msg = _find_last_message(messages, "outline")
        outline = outline_msg["content"] if outline_msg else ""
        script_msg = _find_last_message(messages, "script")
        old_script = script_msg["content"] if script_msg else ""
        persona = format_persona()

        script_prompt = SCRIPT_PROMPT.format(
            persona=persona, outline=outline, research=research
        )
        script_prompt += f"\n\nPrevious script:\n{old_script}\n\nFeedback: {feedback}"
        new_script = await ask_guardian(script_prompt)

        await _save_message(sb, conversation_id, "assistant", new_script, "script")

        yield sse_event({"done": True, "message_type": "script", "content": new_script})


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


async def handle_script_chat_message(
    conversation_id: str,
    content: str,
    msg_type: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    logger.info(
        "script_chat_message type=%s conversation=%s user=%s",
        msg_type,
        conversation_id,
        user_id,
    )
    try:
        if msg_type == "text":
            async for event in handle_ideation(conversation_id, content, user_id):
                yield event
        elif msg_type == "topic_selection":
            topic_index = int(content)
            async for event in handle_topic_selection(
                conversation_id, topic_index, user_id
            ):
                yield event
        elif msg_type == "approve_outline":
            async for event in handle_outline_approval(
                conversation_id, True, content, user_id
            ):
                yield event
        elif msg_type == "reject_outline":
            async for event in handle_outline_approval(
                conversation_id, False, content, user_id
            ):
                yield event
        elif msg_type == "approve_script":
            async for event in handle_script_approval(
                conversation_id, True, content, user_id
            ):
                yield event
        elif msg_type == "reject_script":
            async for event in handle_script_approval(
                conversation_id, False, content, user_id
            ):
                yield event
        else:
            logger.warning("unknown script message type=%s", msg_type)
    except Exception as e:
        logger.exception("error in script pipeline type=%s: %s", msg_type, e)
        yield sse_event({"error": str(e), "done": True})
