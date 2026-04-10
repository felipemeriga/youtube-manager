import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.thumbnail_state import ThumbnailState


def make_base_state(**overrides) -> ThumbnailState:
    defaults = ThumbnailState(
        conversation_id="conv-1",
        user_id="user-1",
        topic="",
        topic_research="",
        background_url=None,
        photo_name=None,
        composite_url=None,
        final_url=None,
        thumb_text=None,
        user_input="",
        user_intent=None,
        extra_instructions=None,
        photo_list=[],
    )
    defaults.update(overrides)
    return defaults


@pytest.mark.asyncio
async def test_generate_background_returns_url():
    from services.thumbnail_nodes import generate_background_node

    state = make_base_state(topic="Guerra do Ira e IA")
    fake_image = b"\x89PNG\r\n\x1a\nfake"

    with patch(
        "services.thumbnail_nodes._research_topic",
        new_callable=AsyncMock,
        return_value="",
    ):
        with patch(
            "services.thumbnail_nodes._get_supabase", new_callable=AsyncMock
        ) as mock_sb:
            sb = MagicMock()
            mock_sb.return_value = sb
            sb.storage.from_.return_value.list = AsyncMock(return_value=[])
            sb.storage.from_.return_value.upload = AsyncMock()
            with patch(
                "services.thumbnail_nodes.generate_background",
                new_callable=AsyncMock,
                return_value=fake_image,
            ):
                result = await generate_background_node(state)

    assert result["background_url"] is not None
    assert result["background_url"].startswith("user-1/bg_")


@pytest.mark.asyncio
async def test_show_photos_returns_photo_list():
    from services.thumbnail_nodes import show_photos_node

    state = make_base_state(topic="AI tutorial")

    with patch(
        "services.thumbnail_nodes._get_supabase", new_callable=AsyncMock
    ) as mock_sb:
        sb = MagicMock()
        mock_sb.return_value = sb
        sb.storage.from_.return_value.list = AsyncMock(
            return_value=[
                {"name": "photo1.jpg"},
                {"name": "photo2.jpg"},
            ]
        )
        with patch(
            "services.thumbnail_nodes.find_best_photos",
            new_callable=AsyncMock,
            return_value=["photo1.jpg"],
        ):
            result = await show_photos_node(state)

    assert len(result["photo_list"]) == 2
    assert result["photo_list"][0]["recommended"] is True


@pytest.mark.asyncio
async def test_composite_node_returns_url():
    from services.thumbnail_nodes import composite_node

    state = make_base_state(
        background_url="user-1/bg_abc.png",
        photo_name="photo1.jpg",
    )
    fake_image = b"\x89PNG\r\n\x1a\ncomposite"

    with patch(
        "services.thumbnail_nodes._get_supabase", new_callable=AsyncMock
    ) as mock_sb:
        sb = MagicMock()
        mock_sb.return_value = sb
        sb.storage.from_.return_value.download = AsyncMock(return_value=b"bg-bytes")
        sb.storage.from_.return_value.list = AsyncMock(return_value=[])
        sb.storage.from_.return_value.upload = AsyncMock()
        with patch(
            "services.thumbnail_nodes.composite_with_effects",
            new_callable=AsyncMock,
            return_value=fake_image,
        ):
            result = await composite_node(state)

    assert result["composite_url"].startswith("user-1/comp_")


@pytest.mark.asyncio
async def test_add_text_node_returns_url():
    from services.thumbnail_nodes import add_text_node

    state = make_base_state(
        composite_url="user-1/comp_abc.png",
        thumb_text="Guerra do Ira",
    )
    fake_image = b"\x89PNG\r\n\x1a\nfinal"

    with patch(
        "services.thumbnail_nodes._get_supabase", new_callable=AsyncMock
    ) as mock_sb:
        sb = MagicMock()
        mock_sb.return_value = sb
        sb.storage.from_.return_value.download = AsyncMock(return_value=b"comp-bytes")
        sb.storage.from_.return_value.list = AsyncMock(return_value=[])
        sb.storage.from_.return_value.upload = AsyncMock()
        with patch(
            "services.thumbnail_nodes.add_text_with_style",
            new_callable=AsyncMock,
            return_value=fake_image,
        ):
            result = await add_text_node(state)

    assert result["final_url"].startswith("user-1/thumb_")


@pytest.mark.asyncio
async def test_save_node_returns_final_url():
    from services.thumbnail_nodes import save_node

    state = make_base_state(final_url="user-1/thumb_abc.png")

    with patch(
        "services.thumbnail_nodes._get_supabase", new_callable=AsyncMock
    ) as mock_sb:
        sb = MagicMock()
        mock_sb.return_value = sb
        sb.storage.from_.return_value.download = AsyncMock(return_value=b"img-data")
        sb.storage.from_.return_value.upload = AsyncMock()
        sb.storage.from_.return_value.remove = AsyncMock()
        result = await save_node(state)

    assert result["final_url"].startswith("user-1/thumbnail_")
