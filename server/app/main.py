"""Truebex API: accounts (email/password + Google), developer API keys,
usage metering, billing (Paddle, Stripe; Wayl dormant), licences for the
desktop app (devices, signed entitlements, trials), the release feed and
downloads, organisations with seats and SSO, and telemetry ingestion.

Run locally with:
    uvicorn app.main:app --host 127.0.0.1 --port 8000

Production runs on a Linux VM in Docker Compose behind Caddy and Cloudflare
(infra/, PF14). start-server.bat and start-tunnel.bat are for local use only.
"""

import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from . import __version__, contract_http, health, tasks
from .billing import jobs as _billing_jobs  # noqa: F401  (registers billing.* jobs)
from .config import get_settings
from .database import init_db
from .licence import jobs as _licence_jobs  # noqa: F401  (registers the licence jobs)
from .orgs import jobs as _org_jobs  # noqa: F401  (PF3: registers the organisation jobs)
from .routers import admin, admin_telemetry, files, licence, releases, telemetry
from .routers import orgs, sso
from .sso import jobs as _sso_jobs  # noqa: F401  (PF3: registers the SSO jobs)
from .routers import auth, billing, keys, usage, v1
from .routers import growth as growth_router
from .telemetry.service import record_server_exception

settings = get_settings()


@asynccontextmanager
async def lifespan(app_: FastAPI):
    init_db()
    # None unless BACKGROUND_TASKS=inline.
    runner = tasks.start_inline(app_)
    yield
    if runner is not None:
        runner.cancel()
        with contextlib.suppress(BaseException):
            await runner


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
        "Retry-After",
        "Content-Disposition",
        contract_http.CONTRACT_HEADER,
        contract_http.REQUEST_ID_HEADER,
    ],
)
# X-Request-Id on every response; the shared error envelope on contract routes
# and for every 422.
contract_http.install(app)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    """API exceptions land in the crash store (kind "server") beside the
    app's crashes, so one inbox covers both."""
    route = getattr(request.scope.get("route"), "path", None)
    await run_in_threadpool(record_server_exception, exc, route)
    return contract_http.envelope_response(
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
    return {
        "google_client_id": settings.google_client_id or None,
        # Paddle.js on /checkout/ (the client token is public by design).
        "paddle_client_token": settings.paddle_client_token or None,
        "paddle_env": settings.paddle_env,
    }


# PF1: licence API, release feed, admin, signed file URLs
app.include_router(licence.router)
app.include_router(releases.router)
app.include_router(admin.router)
app.include_router(files.router)

# PF3: organisations, seats, audit log and SSO
app.include_router(orgs.router)
app.include_router(sso.router)

app.include_router(auth.router)
app.include_router(keys.router)
app.include_router(usage.router)
app.include_router(billing.router)
app.include_router(v1.router)
app.include_router(growth_router.router)
# PF14: deep health, telemetry ingestion and its admin
app.include_router(health.router)
app.include_router(telemetry.router)
app.include_router(admin_telemetry.router)
