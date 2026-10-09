"""Truebex API: accounts (email/password + Google), developer API keys,
usage metering, and billing (Paddle, Stripe; Wayl dormant).

Run locally with:
    uvicorn app.main:app --host 127.0.0.1 --port 8000

Production runs on :8001 behind a cloudflared tunnel (api.truebex.com);
see start-server.bat and start-tunnel.bat at the repo root.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import tasks
from .billing import jobs as _billing_jobs  # noqa: F401  (registers billing.* jobs)
from .config import get_settings
from .database import init_db
from .routers import auth, billing, keys, usage, v1

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    runner = tasks.start_inline(_app) if settings.background_tasks == "inline" else None
    yield
    if runner is not None:
        runner.cancel()


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
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining"],
)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
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


app.include_router(auth.router)
app.include_router(keys.router)
app.include_router(usage.router)
app.include_router(billing.router)
app.include_router(v1.router)
