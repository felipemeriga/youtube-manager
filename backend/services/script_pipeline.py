import asyncio
import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import AsyncGenerator

from config import settings
from services.conversation_title import derive_title
from services.supabase_pool import get_async_client
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

4. Generate YouTube description — when the user asks for a video description, SEO description, or "descrição" for a script or topic:
{{"action": "description", "content": "...the YouTube description in markdown...", "message": "optional conversational text"}}

5. Conversational reply — when you need to ask for clarification, acknowledge something, or chat about anything:
{{"action": "message", "content": "your reply"}}

{script_structure}

Guidelines:
- ALWAYS search the web for current information before suggesting topics or writing scripts
- When suggesting topics, research current news and trends from the last 1-2 weeks
- When writing scripts, include real statistics with verifiable source URLs
- Write all script content in {language}
- When the user gives feedback on a script (e.g. "too long", "more humor"), rewrite incorporating feedback — do NOT restart from topic suggestions
- When the user says "save", "looks good", "approved", "perfect" about a script, use the "save" action
- When the user asks for a YouTube description ("descrição", "description", "SEO"), generate an optimized YouTube description with: compelling first line, key points, timestamps placeholder, hashtags, and call to action. If a script exists in the conversation, base the description on it. Use the "description" action.
- When unclear, ask for clarification using the "message" action
- After a script is saved, if the user brings up a new topic, start fresh topic suggestions
- Suggest 5-10 topics when using the "topics" action, each with title, angle, why_timely, source_url, and interest level
- You can also answer general questions about YouTube strategy, content creation, SEO, engagement, etc. using the "message" action"""


async def get_supabase():
    return await get_async_client()


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


# Rough estimate: 1 token ≈ 4 chars. Conservative to avoid hitting limits.
CHARS_PER_TOKEN = 4
# Context budgets per model family (leaving room for system prompt + response)
MAX_CONTEXT_TOKENS = {
    "claude-haiku-4-5-20251001": 150_000,
    "claude-sonnet-4-20250514": 150_000,
    "claude-opus-4-20250514": 150_000,
}
DEFAULT_MAX_CONTEXT_TOKENS = 150_000


def _estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def _messages_to_chat(
    messages: list[dict], max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS
) -> list[dict]:
    chat = []
    for msg in messages:
        role = msg["role"]
        if role not in ("user", "assistant"):
            continue
        content = msg["content"]
        if msg.get("type") == "topics" and role == "assistant":
            content = json.dumps({"action": "topics", "data": json.loads(content)})
        chat.append(
            {"role": role, "content": content, "_type": msg.get("type", "text")}
        )

    total_tokens = sum(_estimate_tokens(m["content"]) for m in chat)

    if total_tokens > max_tokens:
        chat = _shrink_context(chat, max_tokens)

    # Strip internal metadata before returning
    return [{"role": m["role"], "content": m["content"]} for m in chat]


def _shrink_context(chat: list[dict], max_tokens: int) -> list[dict]:
    """Compress old scripts and topics to fit within token budget."""
    # Strategy: keep the last script/topics in full, summarize older ones
    # Walk backwards to find the last script
    last_script_idx = None
    last_topics_idx = None
    for i in range(len(chat) - 1, -1, -1):
        if chat[i]["_type"] == "script" and last_script_idx is None:
            last_script_idx = i
        if chat[i]["_type"] == "topics" and last_topics_idx is None:
            last_topics_idx = i

    shrunk = []
    for i, msg in enumerate(chat):
        if msg["_type"] == "script" and i != last_script_idx:
            # Summarize old scripts
            preview = msg["content"][:100].replace("\n", " ")
            shrunk.append(
                {
                    **msg,
                    "content": f"[Previously generated script: {preview}...]",
                }
            )
        elif msg["_type"] == "topics" and i != last_topics_idx:
            # Summarize old topic lists
            try:
                topics = json.loads(msg["content"])
                if isinstance(topics, dict):
                    topics = topics.get("data", [])
                titles = [t.get("title", "?") for t in topics[:5]]
                shrunk.append(
                    {
                        **msg,
                        "content": f"[Previously suggested topics: {', '.join(titles)}]",
                    }
                )
            except (json.JSONDecodeError, TypeError):
                shrunk.append({**msg, "content": "[Previous topic suggestions]"})
        else:
            shrunk.append(msg)

    # If still over budget, drop oldest messages (keep last 20)
    total = sum(_estimate_tokens(m["content"]) for m in shrunk)
    if total > max_tokens and len(shrunk) > 20:
        shrunk = shrunk[-20:]

    return shrunk


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

        # Run the three independent reads in parallel — they don't depend on
        # each other, so a single round-trip beats three sequential ones.
        persona, memories, existing_messages = await asyncio.gather(
            _get_user_persona(sb, user_id),
            _get_user_memories(sb, user_id),
            _get_messages(sb, conversation_id),
        )

        if not persona:
            yield sse_event(
                {
                    "error": "Please set up your channel persona in Settings before generating scripts.",
                    "done": True,
                }
            )
            return

        if not existing_messages:
            await (
                sb.table("conversations")
                .update({"title": derive_title(content)})
                .eq("id", conversation_id)
                .execute()
            )

        await _save_message(sb, conversation_id, "user", content, "text")

        yield sse_event({"stage": "thinking"})

        system = _build_system_prompt(persona, memories)
        effective_model = model or settings.anthropic_model
        token_budget = MAX_CONTEXT_TOKENS.get(
            effective_model, DEFAULT_MAX_CONTEXT_TOKENS
        )
        chat_messages = _messages_to_chat(existing_messages, max_tokens=token_budget)
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

            # If there was a previous script, this is a rewrite — extract memory from feedback
            has_previous_script = any(
                m.get("type") == "script" for m in existing_messages
            )
            if has_previous_script:
                asyncio.create_task(
                    extract_memory(
                        sb=sb,
                        user_id=user_id,
                        action="rejected",
                        topic=content[:80],
                        feedback=content,
                    )
                )

        elif action_type == "description":
            desc_content = action.get("content", "")
            await _save_message(
                sb, conversation_id, "assistant", desc_content, "script"
            )
            yield sse_event(
                {"done": True, "message_type": "script", "content": desc_content}
            )

        elif action_type == "save":
            all_messages = await _get_messages(sb, conversation_id)
            script_msg = next(
                (m for m in reversed(all_messages) if m["type"] == "script"),
                None,
            )
            script_content = script_msg["content"] if script_msg else ""

            # Use conversation title for filename, not the raw save command
            conv_result = (
                await sb.table("conversations")
                .select("title")
                .eq("id", conversation_id)
                .maybe_single()
                .execute()
            )
            title = (
                conv_result.data.get("title", "")
                if conv_result and conv_result.data
                else ""
            )
            slug = slugify(title) if title and title.strip() else "script"
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

            # Extract topic title from conversation for better memory context
            topic_title = slug.replace("-", " ")
            for m in reversed(all_messages):
                if m.get("type") == "script":
                    first_line = m["content"].split("\n")[0].strip("# ")
                    if first_line:
                        topic_title = first_line
                    break

            asyncio.create_task(
                extract_memory(
                    sb=sb,
                    user_id=user_id,
                    action="approved",
                    topic=topic_title,
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
