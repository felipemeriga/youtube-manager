import asyncio
import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import AsyncGenerator

from supabase._async.client import create_client as create_async_client

from config import settings
from routes.personas import DEFAULT_SCRIPT_SECTIONS
from services.llm import ask_llm
from services.memory_extractor import extract_memory

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """You are a YouTube content strategist and scriptwriter.

## Channel Persona: {channel_name}

**Language:** {language}

{persona_text}

{memories_section}

You help the user create YouTube video scripts through natural conversation. Based on the conversation context, decide what action to take.

You MUST respond with ONLY a valid JSON object (no markdown fences, no extra text). Use one of these actions:

1. Suggest topics — when the user describes a video idea or asks for topic suggestions:
{{"action": "topics", "data": [{{"title": "...", "angle": "...", "why_timely": "...", "source_url": "...", "interest": "high|medium|low"}}, ...], "message": "optional conversational text"}}

2. Write/rewrite a script — when the user picks a topic, asks you to write, or gives feedback on an existing script:
{{"action": "script", "content": "...full markdown script...", "message": "optional conversational text"}}

3. Save the script — when the user explicitly approves or says to save:
{{"action": "save", "message": "optional conversational text"}}

4. Conversational reply — when you need to ask for clarification, acknowledge something, or chat:
{{"action": "message", "content": "your reply"}}

{script_structure}

Guidelines:
- ALWAYS search the web for current information before suggesting topics or writing scripts
- When suggesting topics, research current news and trends from the last 1-2 weeks
- When writing scripts, include real statistics with verifiable source URLs
- Write all script content in {language}
- When the user gives feedback on a script (e.g. "too long", "more humor"), rewrite incorporating feedback — do NOT restart from topic suggestions
- When the user says "save", "looks good", "approved", "perfect" about a script, use the "save" action
- When unclear, ask for clarification using the "message" action
- After a script is saved, if the user brings up a new topic, start fresh topic suggestions
- Suggest 5-10 topics when using the "topics" action, each with title, angle, why_timely, source_url, and interest level"""


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


async def _get_user_persona(sb, user_id: str) -> dict | None:
    result = (
        await sb.table("channel_personas")
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    return result.data if result else None


async def _get_user_memories(sb, user_id: str) -> list[dict]:
    result = (
        await sb.table("user_memories")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def _build_system_prompt(persona: dict, memories: list[dict]) -> str:
    if memories:
        memories_text = "## Your Learned Preferences\n\n" + "\n".join(
            f"- {m['content']}" for m in memories
        )
    else:
        memories_text = ""

    sections = persona.get("script_template") or DEFAULT_SCRIPT_SECTIONS
    enabled = sorted(
        [s for s in sections if s.get("enabled", True)],
        key=lambda s: s.get("order", 0),
    )
    if enabled:
        lines = [
            "## REQUIRED Script Structure\n",
            "When writing or rewriting a script, you MUST use these sections in this exact order:\n",
        ]
        for i, s in enumerate(enabled, 1):
            lines.append(f"{i}. **{s['name']}** — {s['description']}")
        lines.append(
            "\nDo NOT add extra sections. Do NOT skip any of these sections. Follow this structure exactly."
        )
        script_structure = "\n".join(lines)
    else:
        script_structure = ""

    return SYSTEM_PROMPT_TEMPLATE.format(
        channel_name=persona["channel_name"],
        language=persona["language"],
        persona_text=persona["persona_text"],
        memories_section=memories_text,
        script_structure=script_structure,
    )


def _messages_to_chat(messages: list[dict]) -> list[dict]:
    chat = []
    for msg in messages:
        role = msg["role"]
        if role not in ("user", "assistant"):
            continue
        content = msg["content"]
        if msg.get("type") == "topics" and role == "assistant":
            content = json.dumps({"action": "topics", "data": json.loads(content)})
        chat.append({"role": role, "content": content})
    return chat


def _parse_action(response_text: str) -> dict:
    text = response_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return {"action": "message", "content": response_text}


async def handle_script_chat_message(
    conversation_id: str,
    content: str,
    user_id: str,
    model: str | None = None,
) -> AsyncGenerator[str, None]:
    logger.info(
        "script_chat conversation=%s user=%s",
        conversation_id,
        user_id,
    )
    try:
        sb = await get_supabase()

        persona = await _get_user_persona(sb, user_id)
        if not persona:
            yield sse_event(
                {
                    "error": "Please set up your channel persona in Settings before generating scripts.",
                    "done": True,
                }
            )
            return

        memories = await _get_user_memories(sb, user_id)
        existing_messages = await _get_messages(sb, conversation_id)

        if not existing_messages:
            await (
                sb.table("conversations")
                .update({"title": content[:50]})
                .eq("id", conversation_id)
                .execute()
            )

        await _save_message(sb, conversation_id, "user", content, "text")

        yield sse_event({"stage": "thinking"})

        system = _build_system_prompt(persona, memories)
        chat_messages = _messages_to_chat(existing_messages)
        chat_messages.append({"role": "user", "content": content})

        response_text = await ask_llm(system, chat_messages, model=model)
        action = _parse_action(response_text)
        action_type = action.get("action", "message")

        if action_type == "topics":
            topics_data = action.get("data", [])
            topics_json = json.dumps(topics_data)
            await _save_message(sb, conversation_id, "assistant", topics_json, "topics")
            yield sse_event(
                {"done": True, "message_type": "topics", "content": topics_json}
            )

        elif action_type == "script":
            script_content = action.get("content", "")
            await _save_message(
                sb, conversation_id, "assistant", script_content, "script"
            )
            yield sse_event(
                {"done": True, "message_type": "script", "content": script_content}
            )

        elif action_type == "save":
            all_messages = await _get_messages(sb, conversation_id)
            script_msg = next(
                (m for m in reversed(all_messages) if m["type"] == "script"),
                None,
            )
            script_content = script_msg["content"] if script_msg else ""

            slug = slugify(content) if content.strip() else "script"
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            path = f"{user_id}/{slug}-{timestamp}.md"

            await sb.storage.from_("scripts").upload(
                path,
                script_content.encode("utf-8"),
                {"content-type": "text/markdown"},
            )

            save_message = action.get("message", f"Script saved to {path}")
            await _save_message(sb, conversation_id, "assistant", save_message, "saved")

            yield sse_event({"done": True, "saved": True, "path": path})

            asyncio.create_task(
                extract_memory(
                    sb=sb,
                    user_id=user_id,
                    action="approved",
                    topic=slug,
                    feedback="",
                )
            )

        elif action_type == "message":
            msg_content = action.get("content", "")
            await _save_message(sb, conversation_id, "assistant", msg_content, "text")
            yield sse_event(
                {"done": True, "message_type": "text", "content": msg_content}
            )

        else:
            await _save_message(sb, conversation_id, "assistant", response_text, "text")
            yield sse_event(
                {"done": True, "message_type": "text", "content": response_text}
            )

    except Exception as e:
        logger.exception("error in script pipeline: %s", e)
        yield sse_event({"error": str(e), "done": True})
