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


def _cmd(goto: str, user_response=None, **updates) -> Command:
    """Build a Command with optional state updates."""
    if updates:
        return Command(update=updates, goto=goto)
    return Command(goto=goto)


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
    r = user_response  # shorthand for _cmd

    if action in ("approve", "save", "change_photo"):
        return _cmd("show_photos", r)
    elif action == "clarify":
        return _cmd("review_background", r, clarify_question=intent.get("feedback"))
    elif action == "restart" and intent.get("feedback"):
        return _cmd(
            "generate_background", r, user_intent=intent, topic=intent["feedback"]
        )
    else:
        return _cmd("generate_background", r, user_intent=intent)


async def review_photo(
    state: ThumbnailState,
) -> Command[Literal["composite", "show_photos", "generate_background", "ask_text"]]:
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
    r = user_response

    if action == "skip_photo":
        return _cmd(
            "ask_text",
            r,
            composite_urls=state.get("background_urls") or {},
            photo_name=None,
        )
    if action in ("restart", "change_background"):
        kw: dict = {"user_intent": intent}
        if intent.get("feedback"):
            kw["topic"] = intent["feedback"]
        return _cmd("generate_background", r, **kw)
    if action == "select_photo" and intent.get("photo_name"):
        mode = intent.get("composite_mode", "natural")
        return _cmd(
            "composite",
            r,
            photo_name=intent["photo_name"],
            extra_instructions=intent.get("feedback"),
            composite_mode=mode,
            transform_prompt=intent.get("transform_prompt"),
        )
    else:
        return _cmd("show_photos", r)


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
    r = user_response

    if action in ("approve", "save"):
        return _cmd("ask_text", r)
    elif action == "change_photo":
        return _cmd("show_photos", r, extra_instructions=intent.get("feedback"))
    elif action == "change_text":
        return _cmd("ask_text", r)
    elif action == "change_background":
        return _cmd("generate_background", r, user_intent=intent)
    elif action == "feedback":
        return _cmd(
            "composite",
            r,
            extra_instructions=intent.get("feedback"),
            user_intent=intent,
        )
    elif action == "clarify":
        return _cmd("review_composite", r, clarify_question=intent.get("feedback"))
    elif action == "restart":
        kw_rc: dict = {"user_intent": intent}
        if intent.get("feedback"):
            kw_rc["topic"] = intent["feedback"]
        return _cmd("generate_background", r, **kw_rc)
    else:
        return _cmd("show_photos", r)


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
        text = str(user_response)

    return _cmd("add_text", user_response, thumb_text=text or state["topic"])


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
    r = user_response

    if action in ("save", "approve"):
        return _cmd("save", r)
    elif action == "change_photo":
        return _cmd("show_photos", r, extra_instructions=intent.get("feedback"))
    elif action == "change_text":
        return _cmd("ask_text", r)
    elif action == "change_background":
        return _cmd("generate_background", r, user_intent=intent)
    elif action == "feedback":
        return _cmd("add_text", r, user_intent=intent)
    elif action == "provide_text":
        text = intent.get("text") or intent.get("feedback")
        if text:
            return _cmd("add_text", r, thumb_text=text)
        return _cmd("ask_text", r)
    elif action == "clarify":
        return _cmd("review_final", r, clarify_question=intent.get("feedback"))
    elif action == "restart":
        kw_rf: dict = {"user_intent": intent}
        if intent.get("feedback"):
            kw_rf["topic"] = intent["feedback"]
        return _cmd("generate_background", r, **kw_rf)
    else:
        return _cmd("save", r)


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


async def _create_checkpointer():
    """Create a fresh AsyncPostgresSaver checkpointer."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from config import settings

    cm = AsyncPostgresSaver.from_conn_string(settings.database_url)
    checkpointer = await cm.__aenter__()
    await checkpointer.setup()
    return cm, checkpointer


async def get_thumbnail_graph():
    """Get or create the compiled graph with AsyncPostgresSaver.

    Automatically reconnects if the Postgres connection was dropped.
    """
    global _graph_instance, _checkpointer_cm

    if _graph_instance is not None:
        # Test the connection — if stale, rebuild
        try:
            checkpointer = _graph_instance.checkpointer
            async with checkpointer._cursor() as cur:
                await cur.execute("SELECT 1")
        except Exception:
            logger.warning("Checkpointer connection lost, reconnecting...")
            try:
                await _checkpointer_cm.__aexit__(None, None, None)
            except Exception:
                pass
            _graph_instance = None
            _checkpointer_cm = None

    if _graph_instance is None:
        _checkpointer_cm, checkpointer = await _create_checkpointer()
        _graph_instance = build_thumbnail_graph().compile(checkpointer=checkpointer)

    return _graph_instance
