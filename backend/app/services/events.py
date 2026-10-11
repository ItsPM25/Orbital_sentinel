"""In-process pub/sub for GET /api/stream (SSE): detection, alert.created,
alert.updated, ranking events, each carrying a timestamp and satelliteId
(SRS 3.4). One FastAPI process is enough at this project's scale
(ARCHITECTURE.md 6.2), so this is a plain asyncio broadcaster, not a broker.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

_subscribers: set[asyncio.Queue] = set()
_loop: asyncio.AbstractEventLoop | None = None


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Called once at FastAPI startup. publish() is called from MonitoringSession's
    worker thread (run_in_executor), not the event loop thread, so touching an
    asyncio.Queue from there needs call_soon_threadsafe, not a direct put_nowait."""
    global _loop
    _loop = loop


def subscribe() -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.add(queue)
    return queue


def unsubscribe(queue: asyncio.Queue) -> None:
    _subscribers.discard(queue)


def _enqueue(queue: asyncio.Queue, payload: dict) -> None:
    try:
        queue.put_nowait(payload)
    except asyncio.QueueFull:
        pass  # a slow subscriber drops events rather than blocking a write


def publish(event: str, satellite_id: str, data: dict[str, Any]) -> None:
    """Safe to call from any thread. Fire-and-forget: no subscribers is a normal, cheap no-op."""
    if not _subscribers:
        return
    payload = {"event": event, "satelliteId": satellite_id, "timestamp": _now_iso(), **data}
    for queue in list(_subscribers):
        if _loop is not None:
            _loop.call_soon_threadsafe(_enqueue, queue, payload)
        else:
            _enqueue(queue, payload)  # no loop bound (e.g. a sync test): same-thread fallback


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def stream(queue: asyncio.Queue) -> AsyncIterator[str]:
    """SSE wire format for one subscriber's queue. A `: keep-alive` comment is
    sent periodically so idle proxies/browsers don't time out the connection."""
    try:
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=15)
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield f"event: {payload['event']}\ndata: {json.dumps(payload)}\n\n"
    finally:
        unsubscribe(queue)
