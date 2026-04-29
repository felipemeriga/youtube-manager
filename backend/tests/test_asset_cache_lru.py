"""Regression tests for the bounded LRU behavior of _asset_cache."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services import thumbnail_nodes


@pytest.fixture(autouse=True)
def clear_cache():
    thumbnail_nodes._asset_cache.clear()
    yield
    thumbnail_nodes._asset_cache.clear()


def _patch_storage():
    """Patch supabase + storage so _fetch_all_assets returns predictable bytes.

    sb.storage.from_(bucket) is sync; only .list/.download are async.
    """
    sb = MagicMock()

    async def _list(path):
        return [{"name": f"{path}.png"}]

    async def _download(p):
        return b"data:" + p.encode()

    bucket_api = MagicMock()
    bucket_api.list = AsyncMock(side_effect=_list)
    bucket_api.download = AsyncMock(side_effect=_download)
    sb.storage.from_.return_value = bucket_api

    return patch.object(
        thumbnail_nodes, "_get_supabase", AsyncMock(return_value=sb)
    )


@pytest.mark.asyncio
async def test_cache_evicts_oldest_when_over_max():
    """When the cache exceeds _CACHE_MAX entries, oldest are evicted."""
    with _patch_storage():
        # Fill the cache past the limit
        for i in range(thumbnail_nodes._CACHE_MAX + 5):
            await thumbnail_nodes._fetch_all_assets(None, f"user-{i}", "reference-thumbs")

        assert len(thumbnail_nodes._asset_cache) == thumbnail_nodes._CACHE_MAX
        # First inserted users should be gone
        assert ("user-0", "reference-thumbs") not in thumbnail_nodes._asset_cache
        assert ("user-4", "reference-thumbs") not in thumbnail_nodes._asset_cache
        # Most recent should remain
        last = ("user-" + str(thumbnail_nodes._CACHE_MAX + 4), "reference-thumbs")
        assert last in thumbnail_nodes._asset_cache


@pytest.mark.asyncio
async def test_cache_hit_promotes_entry_to_mru():
    """Re-fetching a cached key moves it to most-recently-used position."""
    with _patch_storage():
        await thumbnail_nodes._fetch_all_assets(None, "user-A", "reference-thumbs")
        await thumbnail_nodes._fetch_all_assets(None, "user-B", "reference-thumbs")
        # Re-hit user-A; this should bump it to MRU
        await thumbnail_nodes._fetch_all_assets(None, "user-A", "reference-thumbs")

        keys = list(thumbnail_nodes._asset_cache.keys())
        assert keys[-1] == ("user-A", "reference-thumbs")


@pytest.mark.asyncio
async def test_expired_entry_is_dropped_on_access():
    """A cache entry past its TTL is dropped and refetched."""
    with _patch_storage():
        await thumbnail_nodes._fetch_all_assets(None, "user-X", "reference-thumbs")
        # Manually backdate the entry past TTL
        key = ("user-X", "reference-thumbs")
        _, data = thumbnail_nodes._asset_cache[key]
        thumbnail_nodes._asset_cache[key] = (
            time.time() - thumbnail_nodes._CACHE_TTL - 1,
            data,
        )

        await thumbnail_nodes._fetch_all_assets(None, "user-X", "reference-thumbs")
        # Entry should still be present (refetched), and timestamp should be fresh
        ts, _ = thumbnail_nodes._asset_cache[key]
        assert time.time() - ts < 5
