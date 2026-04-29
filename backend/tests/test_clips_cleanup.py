from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.clips.cleanup import sweep_expired


@pytest.mark.asyncio
async def test_sweep_deletes_source_and_previews_marks_expired():
    sb = MagicMock()
    expired_jobs = [
        {"id": "j1", "user_id": "u1", "source_storage_key": "u1/j1/source.mp4"},
    ]
    candidates = [
        {"id": "c1", "preview_storage_key": "u1/j1/previews/c1.mp4",
         "preview_poster_key": "u1/j1/previews/c1.jpg",
         "final_storage_key": None},
    ]
    sb.table.return_value.select.return_value.lt.return_value.neq.return_value.execute = AsyncMock(
        return_value=MagicMock(data=expired_jobs)
    )
    sb.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
        return_value=MagicMock(data=candidates)
    )
    sb.table.return_value.update.return_value.in_.return_value.execute = AsyncMock(
        return_value=MagicMock(data=expired_jobs)
    )
    sb.table.return_value.delete.return_value.in_.return_value.is_.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[{"id": "c1"}])
    )

    with patch("services.clips.cleanup.get_async_client", new=AsyncMock(return_value=sb)), \
         patch("services.clips.cleanup.remove_keys", new=AsyncMock()) as remove:
        result = await sweep_expired()

    # Should remove 3 keys: source + preview mp4 + preview jpg
    remove_call_keys = remove.await_args.args[0]
    assert "u1/j1/source.mp4" in remove_call_keys
    assert "u1/j1/previews/c1.mp4" in remove_call_keys
    assert "u1/j1/previews/c1.jpg" in remove_call_keys
    assert result["jobs_expired"] == 1
