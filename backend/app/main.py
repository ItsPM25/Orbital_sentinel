from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import alerts, auth, dev
from app.core.settings import settings

app = FastAPI(title="Orbital Sentinel API", version="0.1.0")

app.include_router(auth.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
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
