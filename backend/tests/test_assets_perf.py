"""Verify list_assets dispatches public_url calls concurrently."""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest

from routes.assets import list_assets


class _Bucket:
    def __init__(self):
        self.list = AsyncMock(
            return_value=[{"name": f"file{i}.jpg"} for i in range(20)]
        )
        self.dispatch_log: list[float] = []

        async def get_url(path):
            self.dispatch_log.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.05)  # simulate per-call latency
            return f"https://cdn/{path}"

        self.get_public_url = get_url


class _Storage:
    def __init__(self):
        self.bucket = _Bucket()

    def from_(self, _):
        return self.bucket


class _Client:
    def __init__(self):
        self.storage = _Storage()


@pytest.mark.asyncio
async def test_list_assets_dispatches_urls_concurrently():
    fake_client = _Client()
    with patch(
        "routes.assets.get_async_client", new=AsyncMock(return_value=fake_client)
    ):
        result = await list_assets(bucket="personal-photos", user_id="user1")

    assert len(result) == 20
    assert all("public_url" in r for r in result)

    log = fake_client.storage.bucket.dispatch_log
    span = max(log) - min(log)
    assert span < 0.04, f"dispatches not concurrent — span={span}s"
