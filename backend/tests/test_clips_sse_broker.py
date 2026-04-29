import asyncio

import pytest

from services.clips.sse_broker import broker


@pytest.mark.asyncio
async def test_publish_then_subscribe_receives():
    job_id = "job-A"
    queue = broker.subscribe(job_id)
    await broker.publish(job_id, {"type": "progress", "pct": 10})
    evt = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert evt["pct"] == 10
    broker.unsubscribe(job_id, queue)


@pytest.mark.asyncio
async def test_multiple_subscribers_each_receive():
    job_id = "job-B"
    q1 = broker.subscribe(job_id)
    q2 = broker.subscribe(job_id)
    await broker.publish(job_id, {"type": "ready"})
    e1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    e2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert e1["type"] == "ready"
    assert e2["type"] == "ready"
    broker.unsubscribe(job_id, q1)
    broker.unsubscribe(job_id, q2)


@pytest.mark.asyncio
async def test_publish_with_no_subscribers_no_error():
    await broker.publish("nobody", {"type": "x"})  # should not raise
