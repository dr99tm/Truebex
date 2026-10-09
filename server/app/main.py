"""Truebex API: accounts (email/password + Google), developer API keys,
usage metering, billing (Stripe + Wayl) and telemetry ingestion.

Run locally with:
    uvicorn app.main:app --host 127.0.0.1 --port 8000

Production runs on a Linux VM in Docker Compose behind Caddy and Cloudflare
(infra/, PF14). start-server.bat and start-tunnel.bat are for local use only.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from . import __version__, contract_http, health, tasks
from .config import get_settings
from .database import init_db
from .routers import admin_telemetry, auth, billing, files, keys, telemetry, usage, v1
from .telemetry.service import record_server_exception

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    loop = tasks.start_inline(app)
    yield
    if loop is not None:
        loop.cancel()


app = FastAPI(
    title="Truebex API",
    version=__version__,
    lifespan=lifespan,
    description=(
        "Developer API for Truebex. Authenticate with an API key from "
        "https://truebex.com/dashboard/keys/ as `Authorization: Bearer tbx_live_…`."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-Request-Id",
        "X-Truebex-Contract",
        "Retry-After",
        "Content-Disposition",
    ],
)
contract_http.install(app)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    """API exceptions land in the crash store (kind "server") beside the
    app's crashes, so one inbox covers both."""
    route = getattr(request.scope.get("route"), "path", None)
    await run_in_threadpool(record_server_exception, exc, route)
    return contract_http.envelope(
        request,
        status=500,
        code="internal_error",
        detail="Something went wrong on our side. It has been reported.",
    )


@app.get("/health", tags=["meta"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config", tags=["meta"])
def public_config() -> dict:
    """What the website needs to know about this server's features."""
    return {"google_client_id": settings.google_client_id or None}


app.include_router(auth.router)
app.include_router(keys.router)
app.include_router(usage.router)
app.include_router(billing.router)
app.include_router(v1.router)
app.include_router(health.router)
app.include_router(files.router)
app.include_router(telemetry.router)
app.include_router(admin_telemetry.router)
