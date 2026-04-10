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
# Review nodes (human-in-the-loop with interrupt)
# ---------------------------------------------------------------------------


async def review_background(
    state: ThumbnailState,
) -> Command[Literal["generate_background", "show_photos"]]:
    """Interrupt to show background. Resume routes based on user intent."""
    user_response = interrupt(
        {
            "type": "background",
            "image_url": state["background_url"],
        }
    )

    # Parse intent — button clicks send dicts, free text sends strings
    if isinstance(user_response, dict) and "action" in user_response:
        intent = user_response
    else:
        intent = await classify_intent(str(user_response), "review_background")

    action = intent.get("action", "approve")

    if action in ("approve", "save"):
        return Command(goto="show_photos")
    else:
        # feedback or restart — regenerate background
        return Command(
            update={"user_intent": intent},
            goto="generate_background",
        )


async def review_photo(
    state: ThumbnailState,
) -> Command[Literal["composite", "show_photos"]]:
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

    if action == "select_photo" and intent.get("photo_name"):
        return Command(
            update={
                "photo_name": intent["photo_name"],
                "extra_instructions": intent.get("feedback"),
            },
            goto="composite",
        )
    else:
        return Command(goto="show_photos")


async def review_composite(
    state: ThumbnailState,
) -> Command[Literal["ask_text", "show_photos", "composite", "generate_background"]]:
    """Interrupt to show composite. Resume routes based on user intent."""
    user_response = interrupt(
        {
            "type": "composite",
            "image_url": state["composite_url"],
        }
    )

    if isinstance(user_response, dict) and "action" in user_response:
        intent = user_response
    else:
        intent = await classify_intent(str(user_response), "review_composite")

    action = intent.get("action", "approve")

    if action in ("approve", "save"):
        return Command(goto="ask_text")
    elif action == "feedback":
        return Command(
            update={
                "extra_instructions": intent.get("feedback"),
                "user_intent": intent,
            },
            goto="composite",
        )
    elif action == "restart":
        return Command(goto="generate_background")
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
) -> Command[Literal["save", "add_text", "ask_text", "generate_background"]]:
    """Interrupt to show final thumbnail. Resume routes to save or redo."""
    user_response = interrupt(
        {
            "type": "image",
            "image_url": state["final_url"],
        }
    )

    if isinstance(user_response, dict) and "action" in user_response:
        intent = user_response
    else:
        intent = await classify_intent(str(user_response), "review_final")

    action = intent.get("action", "save")

    if action in ("save", "approve"):
        return Command(goto="save")
    elif action == "feedback":
        text = intent.get("text") or intent.get("feedback")
        if text:
            return Command(update={"thumb_text": text}, goto="add_text")
        return Command(goto="ask_text")
    elif action == "restart":
        return Command(goto="generate_background")
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

    # Review nodes (human-in-the-loop)
    builder.add_node("review_background", review_background)
    builder.add_node("review_photo", review_photo)
    builder.add_node("review_composite", review_composite)
    builder.add_node("ask_text", ask_text)
    builder.add_node("review_final", review_final)

    # Static edges: generation -> review (one-way)
    builder.add_edge(START, "generate_background")
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
