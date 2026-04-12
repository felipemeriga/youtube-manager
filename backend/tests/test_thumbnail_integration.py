"""Integration tests for the LangGraph thumbnail pipeline.

These tests run the actual graph with mocked external services
(Supabase, Gemini, Anthropic) using InMemorySaver for checkpointing.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langgraph.types import Command

from services.thumbnail_graph import build_thumbnail_graph


@pytest.fixture
def mock_supabase():
    sb = MagicMock()
    sb.storage.from_.return_value.list = AsyncMock(return_value=[{"name": "ref1.jpg"}])
    sb.storage.from_.return_value.download = AsyncMock(return_value=b"fake-image-bytes")
    sb.storage.from_.return_value.upload = AsyncMock()
    sb.storage.from_.return_value.remove = AsyncMock()
    return sb


def make_initial_state(topic: str = "Test topic") -> dict:
    return {
        "conversation_id": "conv-1",
        "user_id": "user-1",
        "topic": topic,
        "user_input": topic,
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


@pytest.mark.asyncio
async def test_full_flow_background_to_photos(mock_supabase):
    """Full flow: generate background → approve → show photos."""
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
                with patch(
                    "services.thumbnail_nodes.find_best_photos",
                    new_callable=AsyncMock,
                    return_value=["ref1.jpg"],
                ):
                    mock_supabase.storage.from_.return_value.list = AsyncMock(
                        return_value=[{"name": "photo1.jpg"}, {"name": "photo2.jpg"}]
                    )

                    graph = build_thumbnail_graph(use_memory_checkpointer=True)
                    config = {"configurable": {"thread_id": "integration-1"}}

                    # Step 1: Start → generates background, interrupts at review_background
                    result = await graph.ainvoke(make_initial_state(), config)
                    assert result.get("background_url") is not None

                    # Step 2: Approve background → shows photos, interrupts at review_photo
                    result = await graph.ainvoke(
                        Command(resume={"action": "approve"}), config
                    )
                    assert len(result.get("photo_list", [])) > 0


@pytest.mark.asyncio
async def test_full_flow_photos_to_composite(mock_supabase):
    """Full flow: through to composite step."""
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
                with patch(
                    "services.thumbnail_nodes.find_best_photos",
                    new_callable=AsyncMock,
                    return_value=[],
                ):
                    with patch(
                        "services.thumbnail_nodes.composite_with_effects",
                        new_callable=AsyncMock,
                        return_value=fake_image,
                    ):
                        mock_supabase.storage.from_.return_value.list = AsyncMock(
                            return_value=[{"name": "photo1.jpg"}]
                        )

                        graph = build_thumbnail_graph(use_memory_checkpointer=True)
                        config = {"configurable": {"thread_id": "integration-2"}}

                        # Generate background
                        await graph.ainvoke(make_initial_state(), config)
                        # Approve background
                        await graph.ainvoke(
                            Command(resume={"action": "approve"}), config
                        )
                        # Select photo
                        result = await graph.ainvoke(
                            Command(
                                resume={
                                    "action": "select_photo",
                                    "photo_name": "photo1.jpg",
                                }
                            ),
                            config,
                        )
                        assert result.get("composite_url") is not None


@pytest.mark.asyncio
async def test_feedback_regenerates_background(mock_supabase):
    """Feedback on background should regenerate it."""
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
            ) as mock_gen:
                graph = build_thumbnail_graph(use_memory_checkpointer=True)
                config = {"configurable": {"thread_id": "integration-3"}}

                # Generate background (call #1)
                result1 = await graph.ainvoke(make_initial_state(), config)
                first_url = result1["background_url"]

                # Send feedback (call #2)
                result2 = await graph.ainvoke(
                    Command(resume={"action": "feedback", "feedback": "too dark"}),
                    config,
                )
                second_url = result2["background_url"]

                # Should have generated twice, with different URLs
                assert mock_gen.call_count == 2
                assert first_url != second_url


@pytest.mark.asyncio
async def test_full_flow_to_text_prompt(mock_supabase):
    """Full flow through to text prompt."""
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
                with patch(
                    "services.thumbnail_nodes.find_best_photos",
                    new_callable=AsyncMock,
                    return_value=[],
                ):
                    with patch(
                        "services.thumbnail_nodes.composite_with_effects",
                        new_callable=AsyncMock,
                        return_value=fake_image,
                    ):
                        mock_supabase.storage.from_.return_value.list = AsyncMock(
                            return_value=[{"name": "p.jpg"}]
                        )

                        graph = build_thumbnail_graph(use_memory_checkpointer=True)
                        config = {"configurable": {"thread_id": "integration-4"}}

                        await graph.ainvoke(make_initial_state(), config)
                        await graph.ainvoke(
                            Command(resume={"action": "approve"}), config
                        )
                        await graph.ainvoke(
                            Command(
                                resume={"action": "select_photo", "photo_name": "p.jpg"}
                            ),
                            config,
                        )
                        # Approve composite → should interrupt at ask_text
                        await graph.ainvoke(
                            Command(resume={"action": "approve"}), config
                        )
                        # The graph should be at ask_text interrupt
                        state = await graph.aget_state(config)
                        has_interrupt = any(
                            hasattr(t, "interrupts") and t.interrupts
                            for t in state.tasks
                        )
                        assert has_interrupt
