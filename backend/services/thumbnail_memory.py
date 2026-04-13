"""Cross-session thumbnail style memory using vector embeddings.

On save: summarize the session's style choices → embed → store.
On new conversation: search for relevant past memories by topic → inject into prompts.
"""

import logging

import voyageai

from config import settings
from services.llm import ask_llm

logger = logging.getLogger(__name__)

SUMMARY_MODEL = "claude-haiku-4-5-20251001"
EMBEDDING_MODEL = "voyage-3"
MAX_MEMORIES = 30

SUMMARY_SYSTEM = """You summarize a YouTube thumbnail creation session into style preferences.

You will receive the conversation history of a thumbnail creation session. Extract the key style preferences in 2-4 concise sentences in Portuguese.

Focus on:
- Background style (colors, theme, mood, elements)
- What was rejected and why
- Composition preferences (person position, effects, glow)
- Typography choices (font style, color, position)
- Overall aesthetic direction

Be specific and actionable — these preferences will guide future thumbnail generation.
Return ONLY the summary, no labels or prefixes."""


async def extract_and_store_memory(sb, user_id: str, conversation_id: str) -> None:
    """Extract style preferences from a completed thumbnail session and store as embedded memory."""
    if not settings.anthropic_api_key or not settings.voyage_api_key:
        return

    try:
        # Get conversation messages
        result = (
            await sb.table("messages")
            .select("role, content, type")
            .eq("conversation_id", conversation_id)
            .order("created_at")
            .execute()
        )
        messages = result.data or []
        if len(messages) < 3:
            return  # Too short to extract meaningful preferences

        # Get conversation title (topic)
        conv_result = (
            await sb.table("conversations")
            .select("title")
            .eq("id", conversation_id)
            .maybe_single()
            .execute()
        )
        topic = (
            conv_result.data.get("title", "")
            if conv_result and conv_result.data
            else ""
        )

        # Build conversation summary for Claude
        conv_text = f"Tema: {topic}\n\n"
        for msg in messages:
            role = "Usuário" if msg["role"] == "user" else "Assistente"
            msg_type = msg.get("type", "text")
            content = msg["content"]
            if msg_type in ("photo_grid",):
                continue  # Skip large JSON
            if len(content) > 200:
                content = content[:200] + "..."
            conv_text += f"{role} ({msg_type}): {content}\n"

        # Extract summary
        summary = await ask_llm(
            system=SUMMARY_SYSTEM,
            messages=[{"role": "user", "content": conv_text}],
            model=SUMMARY_MODEL,
        )
        summary = summary.strip()
        if not summary or len(summary) < 20:
            return

        # Embed
        client = voyageai.Client(api_key=settings.voyage_api_key)
        embed_result = client.embed([f"{topic}: {summary}"], model=EMBEDDING_MODEL)
        embedding = embed_result.embeddings[0]

        # Check memory count and evict oldest if needed
        count_result = (
            await sb.table("thumbnail_memories")
            .select("id, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        existing = count_result.data or []
        if len(existing) >= MAX_MEMORIES:
            oldest = existing[-1]
            await (
                sb.table("thumbnail_memories").delete().eq("id", oldest["id"]).execute()
            )

        # Store
        await (
            sb.table("thumbnail_memories")
            .insert(
                {
                    "user_id": user_id,
                    "topic": topic or "",
                    "content": summary,
                    "embedding": embedding,
                }
            )
            .execute()
        )
        logger.info("thumbnail memory stored for user=%s topic=%s", user_id, topic[:50])

    except Exception:
        logger.exception("thumbnail memory extraction failed for user=%s", user_id)


async def get_relevant_memories(
    sb, user_id: str, topic: str, limit: int = 3
) -> list[str]:
    """Search for past thumbnail style memories relevant to the current topic."""
    if not settings.voyage_api_key:
        return []

    try:
        client = voyageai.Client(api_key=settings.voyage_api_key)
        embed_result = client.embed([topic], model=EMBEDDING_MODEL)
        query_embedding = embed_result.embeddings[0]

        result = await sb.rpc(
            "match_thumbnail_memories",
            {
                "query_embedding": query_embedding,
                "match_user_id": user_id,
                "match_count": limit,
            },
        ).execute()

        if result.data:
            memories = [row["content"] for row in result.data]
            logger.info(
                "found %d thumbnail memories for topic='%s'",
                len(memories),
                topic[:50],
            )
            return memories

        return []
    except Exception:
        logger.exception("thumbnail memory search failed for topic='%s'", topic[:50])
        return []
