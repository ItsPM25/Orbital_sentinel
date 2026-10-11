import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import (
    admin,
    alerts,
    auth,
    detections,
    dev,
    evaluation,
    ranking,
    satellites,
    sessions,
    stream,
    tle,
)
from app.core.settings import settings
from app.services import events


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    events.bind_loop(asyncio.get_running_loop())
    yield


app = FastAPI(title="Orbital Sentinel API", version="0.1.0", lifespan=lifespan)

app.include_router(auth.router, prefix="/api")
app.include_router(satellites.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(detections.router, prefix="/api")
app.include_router(ranking.router, prefix="/api")
app.include_router(stream.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(evaluation.router, prefix="/api")
app.include_router(tle.router, prefix="/api")
if settings.enable_test_reset:
    app.include_router(dev.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.middleware("http")
async def no_store(request: Request, call_next):
    # API responses are live state; never let the browser cache them.
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    return JSONResponse({"error": "Invalid request", "detail": exc.errors()}, status_code=422)
