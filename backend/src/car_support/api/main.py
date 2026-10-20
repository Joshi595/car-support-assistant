"""The HTTP API. Run with `car-support serve` (or `uvicorn car_support.api.main:app`)."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from car_support.api import admin, chat
from car_support.api.limits import limiter
from car_support.config import get_settings
from car_support.db.session import get_engine
from car_support.observability import request_id, setup_logging, setup_tracing

settings = get_settings()
setup_logging(settings.log_level)
if settings.tracing_endpoint:
    setup_tracing(settings.tracing_endpoint)

_UNTRACED = {"/metrics", "/healthz", "/readyz"}  # scraped every few seconds: noise, not customer traffic

app = FastAPI(
    title="Car Support Assistant API",
    version="0.1.0",
    description="Grounded answers with citations, live recall and charger lookups, and handoff to agents.",
    # FastAPI's built-in OpenTelemetry spans join the pipeline traces. Its "logs" record validation errors
    # with the raw input, which could contain a customer's personal data, so they stay off.
    telemetry={"logs": False, "exclude": lambda scope: scope.get("path") in _UNTRACED},
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def tag_request(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Every request carries an ID in the logs and in the X-Request-ID response header."""
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    token = request_id.set(rid)
    try:
        response = await call_next(request)
    finally:
        request_id.reset(token)
    response.headers["X-Request-ID"] = rid
    return response


app.include_router(chat.router)
app.include_router(admin.router)


@app.get("/metrics", tags=["ops"], include_in_schema=False)
def metrics() -> Response:
    """Prometheus scrape endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/healthz", tags=["ops"])
def healthz() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok"}


@app.get("/readyz", tags=["ops"])
def readyz() -> JSONResponse:
    """Readiness: the database and the embedding service answer (both are needed for every question)."""
    checks: dict[str, Any] = {}
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc.__class__.__name__}"
    try:
        httpx.get(f"{settings.ollama_url}/api/version", timeout=3).raise_for_status()
        checks["ollama"] = "ok"
    except httpx.HTTPError as exc:
        checks["ollama"] = f"error: {exc.__class__.__name__}"
    ready = all(v == "ok" for v in checks.values())
    return JSONResponse(checks, status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE)
