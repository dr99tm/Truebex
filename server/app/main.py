"""Truebex API: accounts (email/password + Google), developer API keys,
usage metering, billing (Stripe + Wayl), licences for the desktop app
(devices, signed entitlements, trials), and the release feed and downloads.

Run locally with:
    uvicorn app.main:app --host 127.0.0.1 --port 8000

Production runs on :8001 behind a cloudflared tunnel (api.truebex.com);
see start-server.bat and start-tunnel.bat at the repo root.
"""

import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import contract_http, tasks
from .config import get_settings
from .database import init_db
from .licence import jobs as _licence_jobs  # noqa: F401  (registers the licence jobs)
from .market import jobs as _market_jobs  # noqa: F401  (PF7: registers the marketplace jobs)
from .supplier import jobs as _supplier_jobs  # noqa: F401  (PF8: supplier jobs, e-mails, analytics)
from .routers import admin, files, licence, releases
from .routers import market, market_admin
from .routers import supplier
from .routers import auth, billing, keys, usage, v1

settings = get_settings()


@asynccontextmanager
async def lifespan(app_: FastAPI):
    init_db()
    task = tasks.start_inline(app_) if settings.background_tasks == "inline" else None
    yield
    if task is not None:
        task.cancel()
        with contextlib.suppress(BaseException):
            await task


app = FastAPI(
    title="Truebex API",
    version="2.0.0",
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
        contract_http.CONTRACT_HEADER,
        contract_http.REQUEST_ID_HEADER,
        "ETag",
        "Idempotency-Replayed",
    ],
)
# X-Request-Id on every response; the shared error envelope on contract routes.
contract_http.install(app)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config", tags=["meta"])
def public_config() -> dict:
    """What the website needs to know about this server's features."""
    return {"google_client_id": settings.google_client_id or None}


# PF1: licence API, release feed, admin, signed file URLs
app.include_router(licence.router)
app.include_router(releases.router)
app.include_router(admin.router)
app.include_router(files.router)

# PF7: marketplace API, its platform routes and admin
app.include_router(market.router)
app.include_router(market.internal)
app.include_router(market_admin.router)

# PF8: the supplier portal, the feed endpoints 5.11-5.13, the admin's view of applications
app.include_router(supplier.router)
app.include_router(supplier.feeds_router)
app.include_router(supplier.admin)

app.include_router(auth.router)
app.include_router(keys.router)
app.include_router(usage.router)
app.include_router(billing.router)
app.include_router(v1.router)
