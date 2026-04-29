"""Tests for parallelized upload/download operations in thumbnail_nodes."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.thumbnail_state import ThumbnailState


def make_base_state(**overrides) -> ThumbnailState:
    defaults = ThumbnailState(
        conversation_id="conv-1",
        user_id="user-1",
        topic="",
        topic_research="",
        platforms=["youtube", "instagram_post"],
        background_urls={},
        photo_name=None,
        composite_urls={},
        final_urls={},
        thumb_text=None,
        user_input="",
        user_intent=None,
        extra_instructions=None,
        photo_list=[],
        uploaded_image_url=None,
        composite_mode="natural",
        transform_prompt=None,
    )
    defaults.update(overrides)
    return defaults


@pytest.mark.asyncio
async def test_background_uploads_run_in_parallel():
    """Uploads after background generation should use asyncio.gather, not sequential loops."""
    from services.thumbnail_nodes import generate_background_node

    state = make_base_state(topic="test topic")
    fake_image = b"\x89PNG\r\n\x1a\nfake"

    upload_times = []

    async def track_upload(*args, **kwargs):
        upload_times.append(asyncio.get_event_loop().time())

    with (
        patch(
            "services.thumbnail_nodes._research_topic",
            new_callable=AsyncMock,
            return_value="",
        ),
        patch(
            "services.thumbnail_nodes.get_relevant_memories",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "services.thumbnail_nodes._get_supabase", new_callable=AsyncMock
        ) as mock_sb,
        patch(
            "services.thumbnail_nodes.generate_background",
            new_callable=AsyncMock,
            return_value=fake_image,
        ),
        patch("services.thumbnail_nodes._make_preview", return_value=b"preview-jpg"),
    ):
        sb = MagicMock()
        mock_sb.return_value = sb
        sb.storage.from_.return_value.list = AsyncMock(return_value=[])
        sb.storage.from_.return_value.upload = AsyncMock(side_effect=track_upload)

        result = await generate_background_node(state)

    # Both platforms should have results
    assert "youtube" in result["background_urls"]
    assert "instagram_post" in result["background_urls"]
    # Upload was called (2 per platform: original + preview) = 4 total
    assert sb.storage.from_.return_value.upload.call_count == 4


@pytest.mark.asyncio
async def test_composite_uploads_run_in_parallel():
    """Uploads after compositing should use asyncio.gather, not sequential loops."""
    from services.thumbnail_nodes import composite_node

    state = make_base_state(
        background_urls={
            "youtube": {"url": "user-1/bg_yt.png", "preview_url": ""},
            "instagram_post": {"url": "user-1/bg_ig.png", "preview_url": ""},
        },
        photo_name="photo1.jpg",
    )
    fake_image = b"\x89PNG\r\n\x1a\ncomposite"

    with (
        patch(
            "services.thumbnail_nodes._get_supabase", new_callable=AsyncMock
        ) as mock_sb,
        patch(
            "services.thumbnail_nodes.composite_with_effects",
            new_callable=AsyncMock,
            return_value=fake_image,
        ),
        patch("services.thumbnail_nodes._make_preview", return_value=b"preview-jpg"),
    ):
        sb = MagicMock()
        mock_sb.return_value = sb
        sb.storage.from_.return_value.download = AsyncMock(return_value=b"bg-bytes")
        sb.storage.from_.return_value.list = AsyncMock(return_value=[])
        sb.storage.from_.return_value.upload = AsyncMock()

        result = await composite_node(state)

    assert "youtube" in result["composite_urls"]
    assert "instagram_post" in result["composite_urls"]
    # 2 platforms * 2 uploads (original + preview) = 4
    assert sb.storage.from_.return_value.upload.call_count == 4


@pytest.mark.asyncio
async def test_text_node_uploads_run_in_parallel():
    """Uploads after text addition should use asyncio.gather, not sequential loops."""
    from services.thumbnail_nodes import add_text_node

    state = make_base_state(
        composite_urls={
            "youtube": {"url": "user-1/comp_yt.png", "preview_url": ""},
            "instagram_post": {"url": "user-1/comp_ig.png", "preview_url": ""},
        },
        thumb_text="Test Text",
    )
    fake_image = b"\x89PNG\r\n\x1a\nfinal"

    with (
        patch(
            "services.thumbnail_nodes._get_supabase", new_callable=AsyncMock
        ) as mock_sb,
        patch(
            "services.thumbnail_nodes.add_text_with_style",
            new_callable=AsyncMock,
            return_value=fake_image,
        ),
        patch("services.thumbnail_nodes._make_preview", return_value=b"preview-jpg"),
    ):
        sb = MagicMock()
        mock_sb.return_value = sb
        sb.storage.from_.return_value.download = AsyncMock(return_value=b"comp-bytes")
        sb.storage.from_.return_value.list = AsyncMock(return_value=[])
        sb.storage.from_.return_value.upload = AsyncMock()

        result = await add_text_node(state)

    assert "youtube" in result["final_urls"]
    assert "instagram_post" in result["final_urls"]
    assert sb.storage.from_.return_value.upload.call_count == 4


@pytest.mark.asyncio
async def test_fetch_all_assets_uses_shared_client():
    """_fetch_all_assets should use a single shared client, not one per file."""
    from services.thumbnail_nodes import _fetch_all_assets, _asset_cache

    # Clear cache
    _asset_cache.clear()

    with patch(
        "services.thumbnail_nodes._get_supabase", new_callable=AsyncMock
    ) as mock_sb:
        sb = MagicMock()
        mock_sb.return_value = sb
        sb.storage.from_.return_value.list = AsyncMock(
            return_value=[{"name": "a.jpg"}, {"name": "b.jpg"}, {"name": "c.jpg"}]
        )
        sb.storage.from_.return_value.download = AsyncMock(return_value=b"data")

        result = await _fetch_all_assets(None, "user-1", "reference-thumbs")

    assert len(result) == 3
    # Should create only 1 client (shared), not 1 per file
    assert mock_sb.call_count == 1

    _asset_cache.clear()


@pytest.mark.asyncio
async def test_save_node_parallel_uploads():
    """save_node should upload all platforms in parallel."""
    from services.thumbnail_nodes import save_node

    state = make_base_state(
        final_urls={
            "youtube": {"url": "user-1/thumb_yt.png", "preview_url": ""},
            "instagram_post": {"url": "user-1/thumb_ig.png", "preview_url": ""},
        }
    )

    with patch(
        "services.thumbnail_nodes._get_supabase", new_callable=AsyncMock
    ) as mock_sb:
        sb = MagicMock()
        mock_sb.return_value = sb
        sb.storage.from_.return_value.download = AsyncMock(return_value=b"img-data")
        sb.storage.from_.return_value.upload = AsyncMock()

        result = await save_node(state)

    assert "youtube" in result["final_urls"]
    assert "instagram_post" in result["final_urls"]
    # 2 platforms * 1 upload each = 2
    assert sb.storage.from_.return_value.upload.call_count == 2
