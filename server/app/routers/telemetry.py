"""Telemetry ingestion, contracts/telemetry.md §5 (`X-Truebex-Contract: telemetry/1.0`).

| #   | Endpoint                 | Auth                          |
| 5.1 | GET  /telemetry/config   | none                          |
| 5.2 | POST /telemetry/events   | none (install_id in the body) |
| 5.3 | POST /telemetry/crashes  | none (multipart)              |
| 5.4 | POST /telemetry/feedback | none, or the device token with `reply` |
| 5.5 | POST /telemetry/delete   | the install secret            |

Every endpoint: more than 60 requests an hour from one address or one
installation → 429 `rate_limited`. The address is used by the limiter in
memory only and never stored.
"""

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from ..contract_http import ContractError, contract
from ..database import get_db
from ..deps import device_for_token
from ..models import User
from ..ratelimit import client_address, limit
from ..telemetry import service

router = APIRouter(
    prefix="/telemetry",
    tags=["telemetry"],
    dependencies=[
        Depends(contract("telemetry", 1, 0)),
        Depends(limit(client_address, per_minute=service.PER_HOUR / 60, burst=service.PER_HOUR, scope="telemetry")),
    ],
)


async def read_body(request: Request, cap: int, what: str) -> bytes:
    """The request body, refusing more than `cap` bytes without reading them all."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > cap:
        raise service.too_large(what)
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > cap:
            raise service.too_large(what)
    # Cache it so request.form() can parse what was already read.
    request._body = bytes(body)  # noqa: SLF001 - Starlette's own cache attribute
    return request._body  # noqa: SLF001


async def _parts(request: Request, cap: int, what: str, names: tuple[str, ...]) -> dict[str, bytes | None]:
    await read_body(request, cap, what)
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("multipart/form-data"):
        raise service.invalid(f"The {what} must be sent as multipart/form-data.")
    try:
        form = await request.form(max_files=len(names), max_fields=len(names))
    except Exception as exc:  # noqa: BLE001 - malformed multipart
        raise service.invalid(f"The {what} could not be read.") from exc
    out: dict[str, bytes | None] = {}
    for name in names:
        value = form.get(name)
        if value is None:
            out[name] = None
        elif isinstance(value, UploadFile) or hasattr(value, "read"):
            out[name] = await value.read()
        else:
            out[name] = str(value).encode("utf-8")
    await form.close()
    return out


@router.get("/config")
def config(response: Response) -> dict:
    """5.1: the event allow-list, sampling and the kill switch (cache 24 h)."""
    cfg = service.public_config()
    response.headers["Cache-Control"] = "public, max-age=86400"
    return cfg


@router.post("/events", status_code=status.HTTP_202_ACCEPTED)
async def events(request: Request, db: Session = Depends(get_db)) -> dict:
    """5.2: a batch of usage events; unknown names and props are dropped."""
    raw = await read_body(request, service.EVENTS_MAX_BYTES, "event batch")
    return await run_in_threadpool(service.ingest_events, db, raw)


@router.post("/crashes", status_code=status.HTTP_202_ACCEPTED)
async def crashes(request: Request, db: Session = Depends(get_db)) -> dict:
    """5.3: report (JSON), minidump (≤ 20 MB) and the scrubbed log tail."""
    parts = await _parts(request, service.CRASH_MAX_BYTES, "crash report", ("report", "minidump", "log"))
    return await run_in_threadpool(
        service.ingest_crash, db, parts["report"], parts["minidump"], parts["log"]
    )


@router.post("/feedback", status_code=status.HTTP_202_ACCEPTED)
async def feedback(request: Request, db: Session = Depends(get_db)) -> dict:
    """5.4: text, an optional window screenshot and log tail. With `reply` and
    the device token the account's e-mail is attached; a revoked token → 401."""
    parts = await _parts(request, service.FEEDBACK_MAX_BYTES, "feedback", ("feedback", "screenshot", "log"))
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else None

    def reply_email() -> str | None:
        if not token:
            return None
        device = device_for_token(db, token)
        user = db.get(User, device.user_id) if device else None
        if user is None:
            raise ContractError(
                "unauthenticated",
                401,
                "This device is signed out. Send it without asking for a reply, or sign in again.",
            )
        return user.email

    return await run_in_threadpool(
        service.ingest_feedback, db, parts["feedback"], parts["screenshot"], parts["log"], reply_email
    )


@router.post("/delete", status_code=status.HTTP_202_ACCEPTED)
async def delete_installation(request: Request, db: Session = Depends(get_db)) -> dict:
    """5.5: delete everything this installation sent, within 30 days."""
    raw = await read_body(request, 4096, "request")
    return await run_in_threadpool(service.request_deletion, db, raw)
