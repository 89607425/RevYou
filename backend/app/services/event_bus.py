"""Event bus — in-memory pub/sub for SSE events per job."""
import asyncio
from typing import Any


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, job_id: str) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=200)
        if job_id not in self._subscribers:
            self._subscribers[job_id] = []
        self._subscribers[job_id].append(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue):
        if job_id in self._subscribers:
            try:
                self._subscribers[job_id].remove(q)
            except ValueError:
                pass
            if not self._subscribers[job_id]:
                del self._subscribers[job_id]

    async def publish(self, job_id: str, event: dict[str, Any]):
        """Publish an event to all subscribers of a job."""
        for q in self._subscribers.get(job_id, []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Drop if subscriber is too slow


event_bus = EventBus()
