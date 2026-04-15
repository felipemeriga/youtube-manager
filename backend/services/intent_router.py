import json
import logging
import re

from services.llm import ask_llm
from services.thumbnail_state import UserIntent

logger = logging.getLogger(__name__)

ROUTER_MODEL = "claude-haiku-4-5-20251001"

ROUTER_SYSTEM = """You are the intent classifier for a YouTube thumbnail creator app.

HOW THE APP WORKS:
Thumbnails are built in 5 steps. Each step adds one layer. The user is at step "{step}".
  1. review_background → background only (no person, no text yet)
  2. review_photo → user picks a personal photo (or skips)
  3. review_composite → background + person (no text yet)
  4. ask_text → user types the title text
  5. review_final → complete thumbnail (background + person + text)

CRITICAL: If the user asks for something from a LATER step, classify as "approve" to advance.
Example: at review_background, "falta o texto" → approve (text is step 4, not missing — it hasn't happened yet).

ACTIONS:
- approve — proceed to next step ("looks good", "yes", "ok", "next")
- feedback — visual tweak to CURRENT layer only: colors, position, size, effects, shadows ("mais escuro", "bigger font", "add glow")
- change_photo — go back to photo selection grid ("troque a foto", "outra foto", "change the person")
- change_text — ask user for new text content ("mude o texto", "quero outro título")
- change_background — regenerate background, same topic ("mude o fundo", "outro background")
- skip_photo — skip adding a person, go straight to text ("sem pessoa", "pular foto", "skip photo", "não quero foto")
- select_photo — user chose a specific file (extract filename into photo_name)
- provide_text — user gave the actual text (extract into text field)
- save — save final result ("save", "done", "salvar")
- restart — new topic entirely ("começar de novo", "outro tema")
- clarify — genuinely ambiguous, ask what they mean (put question in feedback)
- use_as_background — uploaded image to use as background, then pick a person photo to composite
- use_as_composite — uploaded image is ready (already has person/content), just needs text added
- skip_to_text — same as use_as_composite: skip background and composition, go straight to adding text

WHEN STEP IS "entry_with_image":
The user uploaded an image. Decide what to do with it:
- If they want to use it as a background and add a person on top → use_as_background
- If they want to just add text to it (skip background generation AND person composition) → use_as_composite
- If they mention "pular", "skip", "só texto", "just add text", "direto pro texto" → use_as_composite
- Default to use_as_background if unclear

WHAT "feedback" MEANS AT EACH STEP:
- review_background: tweak the background (colors, style, brightness). NOT "add text" or "add person".
- review_composite: tweak the person compositing (position, size, glow, effects). NOT "add text".
- review_final: tweak text styling (font size, shadow, color, position). All layers exist here.

Return ONLY: {{"action": "...", "feedback": "..." or null, "photo_name": "..." or null, "text": "..." or null}}"""


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

        # Extract JSON from response — find first { ... } block
        text = response.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        # Find the first JSON object in the response
        match = re.search(r"\{[^}]+\}", text)
        if match:
            text = match.group(0)

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
