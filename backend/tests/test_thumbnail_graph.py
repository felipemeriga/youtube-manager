import sys

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langgraph.types import Command

from services.thumbnail_graph import build_thumbnail_graph


@pytest.fixture
def mock_supabase():
    sb = MagicMock()
    sb.storage.from_.return_value.list = AsyncMock(return_value=[])
    sb.storage.from_.return_value.download = AsyncMock(return_value=b"fake")
    sb.storage.from_.return_value.upload = AsyncMock()
    sb.storage.from_.return_value.remove = AsyncMock()
    return sb


def _initial_state():
    return {
        "conversation_id": "conv-1",
        "user_id": "user-1",
        "topic": "AI tutorial",
        "user_input": "",
        "topic_research": "",
        "background_url": None,
        "photo_name": None,
        "composite_url": None,
        "final_url": None,
        "thumb_text": None,
        "user_intent": None,
        "extra_instructions": None,
        "photo_list": [],
    }


def test_graph_structure():
    """Graph builder creates expected nodes and edges."""
    builder = build_thumbnail_graph(use_memory_checkpointer=False)

    node_names = set(builder.nodes.keys())
    expected_nodes = {
        "generate_background",
        "review_background",
        "show_photos",
        "review_photo",
        "composite",
        "review_composite",
        "ask_text",
        "add_text",
        "review_final",
        "save",
    }
    assert expected_nodes.issubset(node_names), (
        f"Missing nodes: {expected_nodes - node_names}"
    )


def test_graph_compiles_with_checkpointer():
    """Graph compiles successfully with InMemorySaver."""
    graph = build_thumbnail_graph(use_memory_checkpointer=True)
    # Compiled graph should have an invoke method
    assert hasattr(graph, "invoke")
    assert hasattr(graph, "ainvoke")


def test_graph_returns_builder_without_checkpointer():
    """Without checkpointer flag, returns uncompiled builder."""
    builder = build_thumbnail_graph(use_memory_checkpointer=False)
    # Builder has nodes but no invoke method (it's not compiled)
    assert hasattr(builder, "nodes")
    assert hasattr(builder, "compile")


# ---------------------------------------------------------------------------
# Full integration tests (require Python 3.11+ for async interrupt support)
# ---------------------------------------------------------------------------

_requires_py311 = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="LangGraph interrupt() requires Python 3.11+ in async context",
)


@_requires_py311
@pytest.mark.asyncio
async def test_graph_starts_and_interrupts_at_background(mock_supabase):
    """Graph should generate background then interrupt for review."""
    fake_image = b"\x89PNG\r\n\x1a\nfake"

    with patch(
        "services.thumbnail_nodes._get_supabase",
        new_callable=AsyncMock,
        return_value=mock_supabase,
    ):
        with patch(
            "services.thumbnail_nodes._research_topic",
            new_callable=AsyncMock,
            return_value="",
        ):
            with patch(
                "services.thumbnail_nodes.generate_background",
                new_callable=AsyncMock,
                return_value=fake_image,
            ):
                graph = build_thumbnail_graph(use_memory_checkpointer=True)
                config = {"configurable": {"thread_id": "test-1"}}

                result = await graph.ainvoke(_initial_state(), config)

    # Should have background_url set and be interrupted
    assert result.get("background_url") is not None
    assert result["background_url"].startswith("user-1/bg_")


@_requires_py311
@pytest.mark.asyncio
async def test_graph_approve_background_shows_photos(mock_supabase):
    """After approving background, graph should show photos and interrupt."""
    fake_image = b"\x89PNG\r\n\x1a\nfake"

    mock_supabase.storage.from_.return_value.list = AsyncMock(
        return_value=[{"name": "photo1.jpg"}, {"name": "photo2.jpg"}]
    )

    with patch(
        "services.thumbnail_nodes._get_supabase",
        new_callable=AsyncMock,
        return_value=mock_supabase,
    ):
        with patch(
            "services.thumbnail_nodes._research_topic",
            new_callable=AsyncMock,
            return_value="",
        ):
            with patch(
                "services.thumbnail_nodes.generate_background",
                new_callable=AsyncMock,
                return_value=fake_image,
            ):
                with patch(
                    "services.thumbnail_nodes.find_best_photos",
                    new_callable=AsyncMock,
                    return_value=["photo1.jpg"],
                ):
                    graph = build_thumbnail_graph(use_memory_checkpointer=True)
                    config = {"configurable": {"thread_id": "test-2"}}

                    # Start — generates background, interrupts
                    await graph.ainvoke(_initial_state(), config)

                    # Resume with approval
                    result = await graph.ainvoke(
                        Command(resume={"action": "approve"}),
                        config,
                    )

    # Should have photo_list populated
    assert len(result.get("photo_list", [])) > 0


# ---------------------------------------------------------------------------
# Review node unit tests (test routing logic without running full graph)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_background_approve_routes_to_show_photos():
    """review_background should route to show_photos on approve."""
    from services.thumbnail_graph import review_background

    state = {**_initial_state(), "background_url": "user-1/bg_abc.png"}

    with patch(
        "services.thumbnail_graph.interrupt", return_value={"action": "approve"}
    ):
        result = await review_background(state)

    assert isinstance(result, Command)
    assert result.goto == "show_photos"


@pytest.mark.asyncio
async def test_review_background_feedback_routes_to_generate():
    """review_background should route back to generate_background on feedback."""
    from services.thumbnail_graph import review_background

    state = {**_initial_state(), "background_url": "user-1/bg_abc.png"}

    with patch(
        "services.thumbnail_graph.interrupt",
        return_value={"action": "feedback", "feedback": "too dark"},
    ):
        result = await review_background(state)

    assert isinstance(result, Command)
    assert result.goto == "generate_background"
    assert result.update["user_intent"]["action"] == "feedback"


@pytest.mark.asyncio
async def test_review_photo_select_routes_to_composite():
    """review_photo should route to composite when a photo is selected."""
    from services.thumbnail_graph import review_photo

    state = {
        **_initial_state(),
        "photo_list": [
            {
                "name": "photo1.jpg",
                "url": "/api/assets/personal-photos/photo1.jpg",
                "recommended": True,
            }
        ],
    }

    with patch(
        "services.thumbnail_graph.interrupt",
        return_value={"action": "select_photo", "photo_name": "photo1.jpg"},
    ):
        result = await review_photo(state)

    assert isinstance(result, Command)
    assert result.goto == "composite"
    assert result.update["photo_name"] == "photo1.jpg"


@pytest.mark.asyncio
async def test_review_composite_approve_routes_to_ask_text():
    """review_composite should route to ask_text on approve."""
    from services.thumbnail_graph import review_composite

    state = {**_initial_state(), "composite_url": "user-1/comp_abc.png"}

    with patch(
        "services.thumbnail_graph.interrupt", return_value={"action": "approve"}
    ):
        result = await review_composite(state)

    assert isinstance(result, Command)
    assert result.goto == "ask_text"


@pytest.mark.asyncio
async def test_review_composite_feedback_routes_to_composite():
    """review_composite should route back to composite on feedback."""
    from services.thumbnail_graph import review_composite

    state = {**_initial_state(), "composite_url": "user-1/comp_abc.png"}

    with patch(
        "services.thumbnail_graph.interrupt",
        return_value={"action": "feedback", "feedback": "make brighter"},
    ):
        result = await review_composite(state)

    assert isinstance(result, Command)
    assert result.goto == "composite"
    assert result.update["extra_instructions"] == "make brighter"


@pytest.mark.asyncio
async def test_review_composite_restart_routes_to_generate_background():
    """review_composite should route to generate_background on restart."""
    from services.thumbnail_graph import review_composite

    state = {**_initial_state(), "composite_url": "user-1/comp_abc.png"}

    with patch(
        "services.thumbnail_graph.interrupt", return_value={"action": "restart"}
    ):
        result = await review_composite(state)

    assert isinstance(result, Command)
    assert result.goto == "generate_background"


@pytest.mark.asyncio
async def test_ask_text_sets_thumb_text():
    """ask_text should set thumb_text from user response."""
    from services.thumbnail_graph import ask_text

    state = {**_initial_state(), "topic": "AI tutorial"}

    with patch("services.thumbnail_graph.interrupt", return_value="My Custom Title"):
        result = await ask_text(state)

    assert isinstance(result, Command)
    assert result.goto == "add_text"
    assert result.update["thumb_text"] == "My Custom Title"


@pytest.mark.asyncio
async def test_ask_text_falls_back_to_topic():
    """ask_text should use topic as fallback when text is empty."""
    from services.thumbnail_graph import ask_text

    state = {**_initial_state(), "topic": "AI tutorial"}

    with patch(
        "services.thumbnail_graph.interrupt",
        return_value={"action": "provide_text", "text": ""},
    ):
        result = await ask_text(state)

    assert isinstance(result, Command)
    assert result.goto == "add_text"
    assert result.update["thumb_text"] == "AI tutorial"


@pytest.mark.asyncio
async def test_review_final_save_routes_to_save():
    """review_final should route to save on approve/save."""
    from services.thumbnail_graph import review_final

    state = {**_initial_state(), "final_url": "user-1/thumb_abc.png"}

    with patch("services.thumbnail_graph.interrupt", return_value={"action": "save"}):
        result = await review_final(state)

    assert isinstance(result, Command)
    assert result.goto == "save"


@pytest.mark.asyncio
async def test_review_final_feedback_with_text_routes_to_add_text():
    """review_final with feedback text should route to add_text."""
    from services.thumbnail_graph import review_final

    state = {**_initial_state(), "final_url": "user-1/thumb_abc.png"}

    with patch(
        "services.thumbnail_graph.interrupt",
        return_value={"action": "feedback", "text": "Bigger font"},
    ):
        result = await review_final(state)

    assert isinstance(result, Command)
    assert result.goto == "add_text"
    assert result.update["thumb_text"] == "Bigger font"


@pytest.mark.asyncio
async def test_review_final_restart_routes_to_generate_background():
    """review_final restart should route to generate_background."""
    from services.thumbnail_graph import review_final

    state = {**_initial_state(), "final_url": "user-1/thumb_abc.png"}

    with patch(
        "services.thumbnail_graph.interrupt", return_value={"action": "restart"}
    ):
        result = await review_final(state)

    assert isinstance(result, Command)
    assert result.goto == "generate_background"


@pytest.mark.asyncio
async def test_review_background_free_text_calls_classify_intent():
    """review_background should call classify_intent for free text input."""
    from services.thumbnail_graph import review_background

    state = {**_initial_state(), "background_url": "user-1/bg_abc.png"}

    mock_intent = {
        "action": "approve",
        "feedback": None,
        "photo_name": None,
        "text": None,
    }
    with patch("services.thumbnail_graph.interrupt", return_value="looks good"):
        with patch(
            "services.thumbnail_graph.classify_intent",
            new_callable=AsyncMock,
            return_value=mock_intent,
        ):
            result = await review_background(state)

    assert isinstance(result, Command)
    assert result.goto == "show_photos"
