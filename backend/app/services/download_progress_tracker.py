"""
DownloadProgressTracker — SSE-based real-time download progress streaming.

Uses asyncio queues to push progress events to connected SSE clients.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator

from app.core.logging import get_logger
from app.schemas.download import DownloadProgressEvent

logger = get_logger("app.download.tracker")


class DownloadProgressTracker:
    """
    Manages SSE subscriptions for model download progress.

    Each model_name gets a queue. Clients subscribe via SSE and receive
    real-time progress events (percent, speed, ETA, status).
    """

    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, model_name: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        if model_name not in self._queues:
            self._queues[model_name] = []
        self._queues[model_name].append(q)
        return q

    def unsubscribe(self, model_name: str, queue: asyncio.Queue) -> None:
        queues = self._queues.get(model_name, [])
        if queue in queues:
            queues.remove(queue)
        if not queues:
            self._queues.pop(model_name, None)

    def broadcast(self, model_name: str, event: DownloadProgressEvent) -> None:
        for q in self._queues.get(model_name, []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "SSE queue full for model %s, dropping event", model_name
                )

    async def stream(
        self, model_name: str, heartbeat_interval: float = 15.0
    ) -> AsyncIterator[str]:
        """
        Async generator yielding SSE-formatted strings.

        Usage in FastAPI:
            return StreamingResponse(
                tracker.stream(model_name),
                media_type="text/event-stream",
            )
        """
        q = self.subscribe(model_name)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        q.get(), timeout=heartbeat_interval
                    )
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield f": heartbeat\n\n"
                    continue

                data = event.model_dump_json()
                yield f"data: {data}\n\n"

                # Cleanup on terminal events
                if event.status in ("completed", "failed"):
                    logger.info(
                        "Download terminal event for %s: %s",
                        model_name, event.status,
                    )
                    yield f"event: {event.status}\ndata: {data}\n\n"
                    break
        finally:
            self.unsubscribe(model_name, q)
