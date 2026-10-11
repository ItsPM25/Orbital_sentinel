"""The in-process event bus behind GET /api/stream.

Test isolation for the module-level _subscribers/_loop globals is handled by
the autouse _clean_event_bus fixture in conftest.py (shared with every other
test file, since the `client` fixture's lifespan startup binds a loop too).
"""

import asyncio

from app.services import events


def test_publish_with_no_subscribers_does_nothing():
    events.publish("detection", "SAT-001", {"x": 1})  # must not raise


def test_subscribe_and_publish_without_a_bound_loop_uses_same_thread_fallback():
    queue = events.subscribe()
    events.publish("detection", "SAT-001", {"anomalyScore": 1.5})
    payload = queue.get_nowait()
    assert payload["event"] == "detection"
    assert payload["satelliteId"] == "SAT-001"
    assert payload["anomalyScore"] == 1.5
    assert "timestamp" in payload


def test_unsubscribe_stops_delivery():
    queue = events.subscribe()
    events.unsubscribe(queue)
    events.publish("detection", "SAT-001", {})
    assert queue.empty()


def test_full_queue_drops_rather_than_blocks():
    queue = events.subscribe()
    for _ in range(200):  # far past the maxsize=100 cap
        events.publish("detection", "SAT-001", {})
    assert queue.full()


async def test_publish_from_a_worker_thread_is_delivered_via_the_bound_loop():
    loop = asyncio.get_running_loop()
    events.bind_loop(loop)
    queue = events.subscribe()
    await loop.run_in_executor(None, events.publish, "alert.created", "SAT-002", {"riskLevel": 9})
    payload = await asyncio.wait_for(queue.get(), timeout=2)
    assert payload["event"] == "alert.created"
    assert payload["riskLevel"] == 9


async def test_stream_yields_formatted_sse_chunks():
    queue = events.subscribe()
    queue.put_nowait({"event": "ranking", "satelliteId": "SAT-001", "timestamp": "2026-01-01T00:00:00Z"})
    gen = events.stream(queue)
    chunk = await anext(gen)
    assert chunk.startswith("event: ranking\n")
    assert "SAT-001" in chunk
    await gen.aclose()
