import json
import logging
import re

from services.llm import ask_llm
from services.thumbnail_state import UserIntent

logger = logging.getLogger(__name__)

ROUTER_MODEL = "claude-haiku-4-5-20251001"

ROUTER_SYSTEM = """You classify user intent for a YouTube thumbnail creation workflow.
Current step: {step}

The thumbnail is built in layers through a PIPELINE:
  1. review_background — user sees ONLY the background (no person, no text yet)
  2. review_photo — user picks which personal photo to use
  3. review_composite — user sees background + person composited together (no text yet)
  4. ask_text — user provides the text content
  5. review_final — user sees the complete thumbnail (background + person + text)

Each layer is added in order. The user is currently at step "{step}".

Classify the user's message into ONE of these actions:

- approve: user is happy and wants to proceed to the next step (e.g. "looks good", "yes", "approved", "next", "ok")
- feedback: user wants visual tweaks that the image AI can handle directly — effects, colors, positioning, sizing, shadows, filters, styling adjustments to the CURRENT layer. The same content stays, only the presentation changes. (e.g. "mais escuro", "move to the left", "add shadow to text", "bigger font", "mais zoom na foto", "coloque um contorno brilhante", "mude a cor do texto")
- change_photo: user wants to SELECT a different personal photo or ADD their photo to the thumbnail. This requires showing the photo selection grid. (e.g. "adicione minha foto", "troque a foto", "use another photo", "quero outra foto minha", "change the person")
- change_text: user wants to REPLACE the text content with different words. This requires asking them for the new text. (e.g. "mude o texto", "quero outro título", "change the title", "escreva outro texto", "não gostei do texto")
- change_background: user wants a new background generated (different style, colors, or theme, but same topic). (e.g. "mude o fundo", "quero outro background", "change the background", "gere outro fundo", "não gostei do fundo")
- select_photo: user picked a specific photo by filename (extract the filename into photo_name)
- provide_text: user provided the actual text content for the thumbnail (extract into text)
- save: user wants to save the final result (e.g. "save", "download", "done", "salvar")
- restart: user wants to start completely over with a NEW topic or theme. (e.g. "start over", "new topic", "quero mudar o tema", "começar de novo")
- clarify: you cannot confidently determine what the user wants. The message is ambiguous between two or more actions. Put your best guess of what to ask in "feedback". (e.g. "mude isso" — change what? the text? the photo? the background?)
- use_as_background: user uploaded/provided an image to use as the background
- use_as_composite: user uploaded/provided an image that already has the person composited, just needs text
- skip_to_text: user wants to go directly to adding text on an image

KEY DISTINCTIONS:
- "feedback" = tweak HOW something looks (effects, position, size, color). The AI regenerates with adjustments.
- "change_photo" = change WHICH person photo is used. Must show the photo grid for selection.
- "change_text" = change WHAT the text says. Must ask the user for new text.
- "change_background" = generate a NEW background image. Same topic, different visual.
- "restart" = completely new topic/theme from scratch.
- "clarify" = genuinely ambiguous. Use sparingly — only when you truly can't tell.

PIPELINE-AWARE RULES (very important):
- If the user asks about something that belongs to a LATER step, classify as "approve" to advance the pipeline.
  The missing element will be added in its proper step.
- At "review_background": text and person are NOT supposed to be there yet. If the user says
  "falta o texto" or "cadê a pessoa", classify as "approve" — those come in later steps.
  Only use "feedback" for changes to the background itself (colors, style, elements, brightness).
- At "review_composite": text is NOT supposed to be there yet. If the user says "falta o texto"
  or "precisa de texto", classify as "approve" — text comes in the next step.
  Only use "feedback" for changes to the person compositing (position, size, effects, glow).
- At "review_final": ALL layers are present. "feedback" here means visual tweaks to the text styling.

Examples:
- At review_background: "ficou legal mas falta o texto!" → approve (text comes later)
- At review_background: "falta minha foto!" → approve (photo comes later)
- At review_background: "muito escuro, clareia o fundo" → feedback (background tweak)
- At review_composite: "cadê o texto?" → approve (text comes next)
- At review_composite: "minha foto tá muito pequena" → feedback (composite tweak)
- At review_final: "adicione minha foto pessoal no lado direito" → change_photo
- At review_final: "aumente o tamanho da fonte" → feedback (text styling tweak)
- At review_final: "mude o texto para 'Python Tips'" → provide_text
- At review_final: "quero mudar o texto" → change_text
- At review_final: "mude o fundo para algo mais colorido" → change_background
- At any step: "quero um tema completamente diferente" → restart
- At any step: "mude isso" → clarify (ambiguous — change what?)

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
