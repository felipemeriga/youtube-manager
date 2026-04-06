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

DEFAULT_DURATION = "12 minutos"


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
    "\n\nDo NOT create, read, or write any files. Do NOT run any commands. "
    "Just reply with the requested content directly in your response."
)

IDEATION_PROMPT_TEMPLATE = (
    "You are a YouTube content strategist. Your ONLY task right now is to suggest "
    "video topic IDEAS. You are NOT writing a script. You are NOT creating content. "
    "You are ONLY suggesting topics.\n\n"
    "The user wants to make a video about this general area:\n"
    '"""\n{user_input}\n"""\n\n'
    "IMPORTANT: Your training data is outdated. You MUST search the web for "
    "current news and trends from the last 1-2 weeks before suggesting topics. "
    "Use external sources to find what is trending RIGHT NOW.\n\n"
    "Based on your research, suggest 5-10 specific video topics. The channel is a "
    "Brazilian Portuguese tech channel.\n\n"
    "Return ONLY a valid JSON array. No markdown fences. No explanation. No extra text. "
    "No script. No outline. Just the JSON array.\n\n"
    "Each element must have: "
    '"title" (string), "angle" (string), "why_timely" (string), '
    '"source_url" (string — the real URL you found), '
    '"interest" (string: "high", "medium", or "low").\n\n'
    "Example of the EXACT format expected:\n"
    '[{{"title": "Topic A", "angle": "Unique angle", "why_timely": "Recent event", '
    '"source_url": "https://example.com/article", "interest": "high"}}]' + _NO_TOOLS
)

SCRIPT_PROMPT_TEMPLATE = (
    "{persona}\n\n"
    "You are writing a complete YouTube video script in Brazilian Portuguese.\n\n"
    "Topic: {topic}\n\n"
    "Target duration: {duration}.\n\n"
    "IMPORTANT: Your training data is outdated. You MUST search the web for current "
    "information, statistics, data, and expert opinions about this topic. Use REAL, "
    "RECENT sources (last 1-2 weeks). Every fact must have a real, verifiable source URL.\n\n"
    "Write the script using this EXACT structure:\n\n"
    "# {{title}}\n\n"
    "## ⏱️ TIMING ({{duration}})\n\n"
    "A markdown table with columns: Seção | Tempo | Duração\n"
    "Sections must fit within the target duration of {duration}.\n\n"
    "---\n\n"
    "## 📊 STATS E DADOS (com fontes pra citar)\n\n"
    "Each stat as a blockquote with:\n"
    "> **Dado N**: [the fact/stat]\n"
    ">\n"
    "> *Fonte: [Source Name](real URL)*\n\n"
    "Include 6-10 verified stats with real URLs.\n\n"
    "---\n\n"
    "## 🎙️ TALKING POINTS (frases prontas pra falar)\n\n"
    '5-8 punchy one-liner quotes ready to say on camera, using "-" bullets.\n\n'
    "---\n\n"
    "## 📝 ROTEIRO COMPLETO\n\n"
    "### 🎬 ABERTURA (timing)\n"
    "Word-for-word dialogue. Provocative hook in the first 30 seconds.\n\n"
    "### 📌 SEÇÃO N: TITLE (timing)\n"
    "Word-for-word dialogue for each section with inline data citations.\n\n"
    "### 🎬 FECHAMENTO (timing)\n"
    "Strong closing + call to action.\n\n"
    "---\n\n"
    "## 🔗 FONTES VERIFICADAS\n\n"
    "Numbered list of ALL sources used, each with:\n"
    "N. **Source Name** — Article title (date) — real full URL\n\n"
    "CRITICAL: Every URL in this script must be a REAL, clickable link that you "
    "found by searching the web. Do NOT invent or hallucinate URLs." + _NO_TOOLS
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


def _extract_duration(user_message: str) -> str:
    match = re.search(r"(\d+)\s*min", user_message, re.IGNORECASE)
    if match:
        return f"{match.group(1)} minutos"
    return DEFAULT_DURATION


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

    ideation_prompt = IDEATION_PROMPT_TEMPLATE.format(user_input=user_message)
    topics_response = await ask_guardian(ideation_prompt)

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
    user_msg = _find_message(messages, "text")

    topics = json.loads(topics_msg["content"])
    topic = topics[topic_index]
    topic_title = topic.get("title", str(topic))

    duration = _extract_duration(user_msg["content"]) if user_msg else DEFAULT_DURATION

    yield sse_event({"stage": "writing_script"})

    persona = format_persona()
    script_prompt = SCRIPT_PROMPT_TEMPLATE.format(
        persona=persona, topic=topic_title, duration=duration
    )
    script = await ask_guardian(script_prompt)

    await _save_message(sb, conversation_id, "assistant", script, "script")

    yield sse_event({"done": True, "message_type": "script", "content": script})


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

        script_msg = _find_last_message(messages, "script")
        old_script = script_msg["content"] if script_msg else ""

        topics_msg = _find_message(messages, "topics")
        selection_msg = _find_message(messages, "topic_selection")
        topic_title = ""
        if topics_msg and selection_msg:
            topics = json.loads(topics_msg["content"])
            idx = int(selection_msg["content"])
            topic_title = topics[idx].get("title", "")

        user_msg = _find_message(messages, "text")
        duration = (
            _extract_duration(user_msg["content"]) if user_msg else DEFAULT_DURATION
        )

        persona = format_persona()
        script_prompt = SCRIPT_PROMPT_TEMPLATE.format(
            persona=persona, topic=topic_title, duration=duration
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
