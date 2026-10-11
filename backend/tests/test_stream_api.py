"""GET /api/stream (SSE).

A real SSE connection never closes on its own, so it isn't exercised through a
live HTTP round-trip here (that hangs a synchronous TestClient). Instead the
route function is called directly with a fake Request whose is_disconnected()
flips to True after the first chunk, which is enough to check the response
shape and that the generator terminates and cleans up its subscription.
"""

from app.api.stream import stream
from app.services import events


def test_stream_requires_login(client):
    assert client.get("/api/stream").status_code == 401


async def test_stream_response_has_sse_headers_and_cleans_up_its_subscription():
    class FakeRequest:
        def __init__(self):
            self.calls = 0

        async def is_disconnected(self):
            self.calls += 1
            return self.calls > 1  # connected for the first chunk, then "disconnects"

    assert len(events._subscribers) == 0
    response = await stream(FakeRequest(), _user=None)
    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-store"

    events.publish("detection", "SAT-001", {"anomalyScore": 1.0})
    chunks = [chunk async for chunk in response.body_iterator]
    assert any("detection" in c for c in chunks)
    assert len(events._subscribers) == 0  # unsubscribed once the (fake) client disconnected
