import logging
from typing import Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command

from services.intent_router import classify_intent
from services.thumbnail_nodes import (
    generate_background_node,
    show_photos_node,
    composite_node,
    add_text_node,
    save_node,
)
from services.thumbnail_state import ThumbnailState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entry router (flexible start based on uploaded image)
# ---------------------------------------------------------------------------


async def entry_router(
    state: ThumbnailState,
) -> Command[
    Literal["generate_background", "show_photos", "review_composite", "ask_text"]
]:
    """Route to the right starting node based on user input and uploaded image."""
    uploaded = state.get("uploaded_image_url")

    if uploaded:
        # User provided an image — classify what to do with it
        intent = await classify_intent(
            state.get("user_input", ""),
            "entry_with_image",
        )
        action = intent.get("action", "use_as_background")

        platforms = state.get("platforms") or ["youtube"]
        if action in ("use_as_composite", "skip_to_text"):
            # Image is a composite — use for all platforms
            return Command(
                update={
                    "composite_urls": {
                        p: {"url": uploaded, "preview_url": ""} for p in platforms
                    }
                },
                goto="ask_text",
            )
        else:
            # Default: use as background for all platforms
            return Command(
                update={
                    "background_urls": {
                        p: {"url": uploaded, "preview_url": ""} for p in platforms
                    }
                },
                goto="show_photos",
            )

    # No image — normal flow, generate background
    return Command(goto="generate_background")


# ---------------------------------------------------------------------------
# Review nodes (human-in-the-loop with interrupt)
# ---------------------------------------------------------------------------


async def review_background(
    state: ThumbnailState,
) -> Command[Literal["generate_background", "show_photos", "review_background"]]:
    """Interrupt to show background. Resume routes based on user intent."""
    payload: dict = {
        "type": "background",
        "image_urls": state.get("background_urls") or {},
    }
    if state.get("clarify_question"):
        payload["clarify_question"] = state["clarify_question"]
    user_response = interrupt(payload)

    # Parse intent — button clicks send dicts, free text sends strings
    if isinstance(user_response, dict) and "action" in user_response:
        intent = user_response
    else:
        intent = await classify_intent(str(user_response), "review_background")

    action = intent.get("action", "approve")

    if action in ("approve", "save", "change_photo"):
        return Command(goto="show_photos")
    elif action == "clarify":
        # Ask the user to clarify — re-interrupt with a question
        return Command(
            update={"clarify_question": intent.get("feedback")},
            goto="review_background",
        )
    else:
        # feedback, change_background, or restart — regenerate background
        updates: dict = {"user_intent": intent}
        if action == "restart" and intent.get("feedback"):
            updates["topic"] = intent["feedback"]
        return Command(
            update=updates,
            goto="generate_background",
        )


async def review_photo(
    state: ThumbnailState,
) -> Command[Literal["composite", "show_photos", "generate_background"]]:
    """Interrupt to show photo grid. Resume routes based on selection."""
    user_response = interrupt(
        {
            "type": "photo_grid",
            "photos": state["photo_list"],
        }
    )

    if isinstance(user_response, dict) and "action" in user_response:
        intent = user_response
    else:
        intent = await classify_intent(str(user_response), "review_photo")

    action = intent.get("action", "select_photo")

    if action in ("restart", "change_background"):
        updates: dict = {"user_intent": intent}
        if intent.get("feedback"):
            updates["topic"] = intent["feedback"]
        return Command(
            update=updates,
            goto="generate_background",
        )
    if action == "select_photo" and intent.get("photo_name"):
        return Command(
            update={
                "photo_name": intent["photo_name"],
                "extra_instructions": intent.get("feedback"),
            },
            goto="composite",
        )
    else:
        # change_photo, clarify, or anything else — stay on photo grid
        return Command(goto="show_photos")


async def review_composite(
    state: ThumbnailState,
) -> Command[
    Literal[
        "ask_text",
        "show_photos",
        "composite",
        "generate_background",
        "review_composite",
    ]
]:
    """Interrupt to show composite. Resume routes based on user intent."""
    payload_comp: dict = {
        "type": "composite",
        "image_urls": state.get("composite_urls") or {},
    }
    if state.get("clarify_question"):
        payload_comp["clarify_question"] = state["clarify_question"]
    user_response = interrupt(payload_comp)

    if isinstance(user_response, dict) and "action" in user_response:
        intent = user_response
    else:
        intent = await classify_intent(str(user_response), "review_composite")

    action = intent.get("action", "approve")

    if action in ("approve", "save"):
        return Command(goto="ask_text")
    elif action == "change_photo":
        return Command(
            update={"extra_instructions": intent.get("feedback")},
            goto="show_photos",
        )
    elif action == "change_text":
        return Command(goto="ask_text")
    elif action == "change_background":
        return Command(
            update={"user_intent": intent},
            goto="generate_background",
        )
    elif action == "feedback":
        return Command(
            update={
                "extra_instructions": intent.get("feedback"),
                "user_intent": intent,
            },
            goto="composite",
        )
    elif action == "clarify":
        return Command(
            update={"clarify_question": intent.get("feedback")},
            goto="review_composite",
        )
    elif action == "restart":
        updates_rc: dict = {"user_intent": intent}
        if intent.get("feedback"):
            updates_rc["topic"] = intent["feedback"]
        return Command(update=updates_rc, goto="generate_background")
    else:
        return Command(goto="show_photos")


async def ask_text(state: ThumbnailState) -> Command[Literal["add_text"]]:
    """Interrupt to ask user for thumbnail text."""
    user_response = interrupt(
        {
            "type": "text_prompt",
            "suggestion": state["topic"],
        }
    )

    if isinstance(user_response, dict) and "action" in user_response:
        intent = user_response
        text = intent.get("text") or intent.get("feedback")
    else:
        # Free text — treat the entire response as the thumbnail text
        text = str(user_response)

    return Command(
        update={"thumb_text": text or state["topic"]},
        goto="add_text",
    )


async def review_final(
    state: ThumbnailState,
) -> Command[
    Literal[
        "save",
        "add_text",
        "ask_text",
        "show_photos",
        "composite",
        "generate_background",
        "review_final",
    ]
]:
    """Interrupt to show final thumbnail. Resume routes to save or redo."""
    payload_final: dict = {
        "type": "image",
        "image_urls": state.get("final_urls") or {},
    }
    if state.get("clarify_question"):
        payload_final["clarify_question"] = state["clarify_question"]
    user_response = interrupt(payload_final)

    if isinstance(user_response, dict) and "action" in user_response:
        intent = user_response
    else:
        intent = await classify_intent(str(user_response), "review_final")

    action = intent.get("action", "save")

    if action in ("save", "approve"):
        return Command(goto="save")
    elif action == "change_photo":
        return Command(
            update={"extra_instructions": intent.get("feedback")},
            goto="show_photos",
        )
    elif action == "change_text":
        return Command(goto="ask_text")
    elif action == "change_background":
        return Command(
            update={"user_intent": intent},
            goto="generate_background",
        )
    elif action == "feedback":
        # Visual tweaks on the final image (text effects, styling) —
        # keep the same text, send feedback to the text rendering step
        return Command(
            update={"user_intent": intent},
            goto="add_text",
        )
    elif action == "provide_text":
        # User provided new text content directly
        text = intent.get("text") or intent.get("feedback")
        if text:
            return Command(update={"thumb_text": text}, goto="add_text")
        return Command(goto="ask_text")
    elif action == "clarify":
        return Command(
            update={"clarify_question": intent.get("feedback")},
            goto="review_final",
        )
    elif action == "restart":
        updates_rf: dict = {"user_intent": intent}
        if intent.get("feedback"):
            updates_rf["topic"] = intent["feedback"]
        return Command(update=updates_rf, goto="generate_background")
    else:
        return Command(goto="save")


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------


def build_thumbnail_graph(use_memory_checkpointer: bool = False):
    """Build and compile the thumbnail StateGraph.

    Args:
        use_memory_checkpointer: If True, use InMemorySaver (for tests).
            If False, returns the uncompiled builder (caller adds checkpointer).
    """
    builder = StateGraph(ThumbnailState)

    # Generation nodes
    builder.add_node("generate_background", generate_background_node)
    builder.add_node("show_photos", show_photos_node)
    builder.add_node("composite", composite_node)
    builder.add_node("add_text", add_text_node)
    builder.add_node("save", save_node)

    # Entry router (flexible start)
    builder.add_node("entry_router", entry_router)

    # Review nodes (human-in-the-loop)
    builder.add_node("review_background", review_background)
    builder.add_node("review_photo", review_photo)
    builder.add_node("review_composite", review_composite)
    builder.add_node("ask_text", ask_text)
    builder.add_node("review_final", review_final)

    # Static edges: generation -> review (one-way)
    builder.add_edge(START, "entry_router")
    builder.add_edge("generate_background", "review_background")
    builder.add_edge("show_photos", "review_photo")
    builder.add_edge("composite", "review_composite")
    builder.add_edge("add_text", "review_final")
    builder.add_edge("save", END)

    # NOTE: Review nodes use Command for routing — no static edges from them

    if use_memory_checkpointer:
        return builder.compile(checkpointer=InMemorySaver())

    return builder


_graph_instance = None
_checkpointer_cm = None


async def get_thumbnail_graph():
    """Get or create the compiled graph with AsyncPostgresSaver."""
    global _graph_instance, _checkpointer_cm
    if _graph_instance is None:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from config import settings

        _checkpointer_cm = AsyncPostgresSaver.from_conn_string(settings.database_url)
        checkpointer = await _checkpointer_cm.__aenter__()
        await checkpointer.setup()
        _graph_instance = build_thumbnail_graph().compile(checkpointer=checkpointer)
    return _graph_instance
