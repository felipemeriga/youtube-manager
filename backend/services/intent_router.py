import json
import logging
import re

from services.llm import ask_llm
from services.thumbnail_state import UserIntent

logger = logging.getLogger(__name__)

ROUTER_MODEL = "claude-haiku-4-5-20251001"

ROUTER_SYSTEM = """You classify user intent for a YouTube thumbnail creation workflow.
Current step: {step}

Classify the user's message into ONE of these actions:
- approve: user is happy with the result (e.g. "looks good", "yes", "approved", "next", "ok")
- feedback: user wants changes (e.g. "too dark", "make it bigger", "redo", "I don't like it")
- select_photo: user picked a photo (extract the filename into photo_name)
- provide_text: user provided text for the thumbnail (extract into text)
- save: user wants to save the final result (e.g. "save", "download", "done")
- restart: user wants to start completely over (e.g. "start over", "new topic")

Return ONLY a JSON object with these fields:
{{"action": "...", "feedback": "..." or null, "photo_name": "..." or null, "text": "..." or null}}"""


async def classify_intent(user_input: str, current_step: str) -> UserIntent:
    """Classify user input into a structured intent.

    If user_input is a JSON string with an "action" field, use it directly
    (this is the button-click path). Otherwise, call the LLM to classify.
    """
    # Try parsing as direct action (button clicks)
    try:
        parsed = json.loads(user_input)
        if isinstance(parsed, dict) and "action" in parsed:
            return UserIntent(
                action=parsed["action"],
                feedback=parsed.get("feedback"),
                photo_name=parsed.get("photo_name"),
                text=parsed.get("text"),
            )
    except (json.JSONDecodeError, TypeError):
        pass

    # Call LLM to classify free text
    try:
        system = ROUTER_SYSTEM.format(step=current_step)
        response = await ask_llm(
            system=system,
            messages=[{"role": "user", "content": user_input}],
            model=ROUTER_MODEL,
        )

        # Extract JSON from response
        text = response.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        data = json.loads(text)
        return UserIntent(
            action=data.get("action", "feedback"),
            feedback=data.get("feedback"),
            photo_name=data.get("photo_name"),
            text=data.get("text"),
        )
    except Exception:
        logger.exception("intent classification failed, falling back to feedback")
        return UserIntent(
            action="feedback",
            feedback=user_input,
            photo_name=None,
            text=None,
        )
