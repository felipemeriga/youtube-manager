import logging
import re

from services.llm import ask_llm

logger = logging.getLogger(__name__)

MAX_MEMORIES = 20

EXTRACTION_PROMPT = """You are analyzing a user's interaction with a YouTube script to extract preferences.

Action: {action}
Topic: {topic}
Feedback: {feedback}

Existing memories:
{memories}

Rules:
- Extract ONE concise, actionable preference from this interaction
- If it contradicts an existing memory, return REPLACE:<id> followed by the new text
- If it's redundant with an existing memory, return SKIP
- Keep preferences actionable (e.g. "Prefers scripts under 10 minutes" not "User said too long")

Return ONLY: the preference text, or REPLACE:<id> <new text>, or SKIP"""


async def extract_memory(
    sb, user_id: str, action: str, topic: str, feedback: str
) -> None:
    try:
        result = (
            await sb.table("user_memories")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        existing = result.data or []

        if existing:
            memories_text = "\n".join(f"- [{m['id']}] {m['content']}" for m in existing)
        else:
            memories_text = "none yet"

        prompt = EXTRACTION_PROMPT.format(
            action=action,
            topic=topic,
            feedback=feedback or "none — user approved without changes",
            memories=memories_text,
        )

        response = await ask_llm(
            system="You extract user preferences from script feedback.",
            messages=[{"role": "user", "content": prompt}],
        )
        response = response.strip()

        if response == "SKIP":
            logger.info("memory extraction: SKIP for user=%s", user_id)
            return

        replace_match = re.match(r"REPLACE:(\S+)\s+(.*)", response, re.DOTALL)
        if replace_match:
            old_id = replace_match.group(1)
            new_content = replace_match.group(2).strip()
            await sb.table("user_memories").delete().eq("id", old_id).execute()
            await (
                sb.table("user_memories")
                .insert(
                    {
                        "user_id": user_id,
                        "content": new_content,
                        "source_action": action,
                        "source_feedback": feedback or "",
                    }
                )
                .execute()
            )
            logger.info("memory extraction: REPLACE %s for user=%s", old_id, user_id)
            return

        # New memory
        if len(existing) >= MAX_MEMORIES:
            oldest = existing[-1]
            await sb.table("user_memories").delete().eq("id", oldest["id"]).execute()
            logger.info(
                "memory extraction: evicted oldest %s for user=%s",
                oldest["id"],
                user_id,
            )

        await (
            sb.table("user_memories")
            .insert(
                {
                    "user_id": user_id,
                    "content": response,
                    "source_action": action,
                    "source_feedback": feedback or "",
                }
            )
            .execute()
        )
        logger.info("memory extraction: new memory for user=%s", user_id)

    except Exception:
        logger.exception("memory extraction failed for user=%s", user_id)
