"""In-process per-job SSE event broker.

A single FastAPI process hosts the asyncio task that runs the clip pipeline.
Each connected SSE client subscribes via `subscribe(job_id)`, getting back an
asyncio.Queue. The pipeline calls `publish(job_id, event)` after each stage.
On disconnect the client calls `unsubscribe(job_id, queue)`.
"""
import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class _Broker:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, job_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers[job_id].append(q)
        return q

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        if job_id in self._subscribers and queue in self._subscribers[job_id]:
            self._subscribers[job_id].remove(queue)
            if not self._subscribers[job_id]:
                del self._subscribers[job_id]

    async def publish(self, job_id: str, event: dict) -> None:
        for q in list(self._subscribers.get(job_id, [])):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("SSE queue full for job %s, dropping event", job_id)


broker = _Broker()
