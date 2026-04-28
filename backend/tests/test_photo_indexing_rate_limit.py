"""Tests for photo indexing concurrency limiter."""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_indexing_semaphore_limits_concurrency():
    """Concurrent photo indexing tasks should be limited by the semaphore."""
    from routes.assets import _index_uploaded_photo, _INDEX_SEMAPHORE

    active_count = 0
    max_active = 0
    lock = asyncio.Lock()

    async def mock_index(sb, user_id, filename, image_bytes):
        nonlocal active_count, max_active
        async with lock:
            active_count += 1
            max_active = max(max_active, active_count)
        await asyncio.sleep(0.05)
        async with lock:
            active_count -= 1

    with (
        patch("routes.assets.get_async_client", new_callable=AsyncMock) as mock_sb,
        patch("services.photo_indexer.index_photo", side_effect=mock_index),
    ):
        mock_sb.return_value = MagicMock()

        # Launch 6 indexing tasks concurrently (semaphore should limit to 3)
        tasks = [
            asyncio.create_task(
                _index_uploaded_photo(f"user-{i}", f"photo-{i}.jpg", b"data")
            )
            for i in range(6)
        ]
        await asyncio.gather(*tasks)

    # Max concurrent should not exceed the semaphore value (3)
    assert max_active <= 3


@pytest.mark.asyncio
async def test_indexing_still_completes_all():
    """All photos should be indexed even with the semaphore."""
    from routes.assets import _index_uploaded_photo

    indexed = []

    async def mock_index(sb, user_id, filename, image_bytes):
        indexed.append(filename)

    with (
        patch("routes.assets.get_async_client", new_callable=AsyncMock) as mock_sb,
        patch("services.photo_indexer.index_photo", side_effect=mock_index),
    ):
        mock_sb.return_value = MagicMock()

        tasks = [
            asyncio.create_task(
                _index_uploaded_photo("user-1", f"photo-{i}.jpg", b"data")
            )
            for i in range(5)
        ]
        await asyncio.gather(*tasks)

    assert len(indexed) == 5
