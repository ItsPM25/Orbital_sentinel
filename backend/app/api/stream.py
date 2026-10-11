from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user
from app.models import User
from app.services import events

router = APIRouter(tags=["stream"])


@router.get("/stream")
async def stream(request: Request, _user: User = Depends(get_current_user)):
    """SSE: detection, alert.created, alert.updated, ranking (ARCHITECTURE.md 7)."""
    queue = events.subscribe()

    async def generator():
        try:
            async for chunk in events.stream(queue):
                if await request.is_disconnected():
                    break
                yield chunk
        finally:
            events.unsubscribe(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
