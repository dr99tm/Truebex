"""Render jobs as their owner sees them (contract render-jobs v1.2, 5.1-5.6; a
1.0 or 1.1 client is served the same: 1.1.0 and 1.2.0 are additive).

Auth: a device token (the app), a session (the website, PF9) or an API key
(PF12, metered like every developer call). 5.2 is `async`: it long-polls on
`rev` without holding a worker thread or a database connection. Every error
uses the shared envelope. `PUT /jobs/usage/overage` (the Cloud page's
overage cap) is an addition outside the contract's numbering.
"""

import asyncio
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..contract_http import ContractError, contract
from ..database import SessionLocal, get_db
from ..deps import api_key_auth, get_session_or_device
from ..idempotency import Idempotency, idempotent
from ..projects import waiters
from ..projects.caller import ProjectCaller, require_session
from ..render import queue, quotas, service
from ..security import API_KEY_PREFIX
from ..uploads.credentials import WORKER_TOKEN_PREFIX

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[contract("render-jobs", 1, 2)])
_bearer = HTTPBearer(auto_error=False)
MAX_BODY_BYTES = 2 * 1024 * 1024
PRIVATE = {"Cache-Control": "private, no-store"}


def get_job_caller(
    request: Request,
    response: Response,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ProjectCaller:
    """Contract §4: device, session or API key (metered, as /v1 is)."""
    raw = x_api_key or (creds.credentials if creds else "")
    if raw.startswith(API_KEY_PREFIX):
        found = api_key_auth(request, response, creds, x_api_key, db)
        # PF12: scopes are checked on every route (writes jobs:write, reads projects:read).
        needed = "jobs:write" if request.method != "GET" else "projects:read"
        if needed not in found.scopes:
            raise ContractError(
                "forbidden", 403, f"This API key does not have the {needed} scope.",
                {"needed": needed, "scopes": list(found.scopes)},
            )
        return ProjectCaller(user=found.user, kind="api_key", key_id=found.key.id)
    if not raw:
        raise ContractError("unauthenticated", 401, "Sign in to use cloud rendering.", headers={"WWW-Authenticate": "Bearer"})
    if raw.startswith(WORKER_TOKEN_PREFIX):
        raise ContractError("unauthenticated", 401, "Worker tokens are for /workers.", headers={"WWW-Authenticate": "Bearer"})
    found = get_session_or_device(creds, db)
    return ProjectCaller(user=found.user, kind="device" if found.device is not None else "session", device=found.device)


def _small_body(request: Request) -> None:
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
        raise ContractError("too_large", 413, "A job request is at most 2 MiB.", {"limit": MAX_BODY_BYTES})


# --- 5.1 -----------------------------------------------------------------------------------


def _with_rate_headers(out: Response, response: Response) -> Response:
    """An API key's X-RateLimit-* headers survive the JSONResponse idempotency builds."""
    for name in ("X-RateLimit-Limit", "X-RateLimit-Remaining"):
        if name in response.headers:
            out.headers[name] = response.headers[name]
    return out


@router.post("", status_code=201, dependencies=[Depends(_small_body)])
def submit(
    response: Response,
    body: dict[str, Any] = Body(...),
    caller: ProjectCaller = Depends(get_job_caller),
    idem: Idempotency = idempotent("jobs.submit"),
    db: Session = Depends(get_db),
):
    replay = idem.start(db, account=f"user:{caller.user.id}")
    if replay is not None:
        return _with_rate_headers(replay, response)
    try:
        job, joined = service.submit(db, caller, body)
        answer = {**service.record_json(job), "coalesced": joined}
    except BaseException:
        idem.abandon()
        raise
    return _with_rate_headers(idem.save(db, 201, answer), response)


# --- 5.6 (declared before /{job_id}) ----------------------------------------------------------


@router.get("/usage")
def usage(caller: ProjectCaller = Depends(get_job_caller), db: Session = Depends(get_db)) -> dict:
    return service.usage(db, caller.user)


class OverageIn(BaseModel):
    cap_cu: float


@router.put("/usage/overage")
def set_overage(body: OverageIn, caller: ProjectCaller = Depends(get_job_caller), db: Session = Depends(get_db)) -> dict:
    require_session(caller, "change the overage cap")
    try:
        cap = Decimal(str(body.cap_cu))
    except InvalidOperation:
        cap = Decimal(-1)
    if not cap.is_finite() or cap < 0 or cap > 100_000:
        raise ContractError(
            "validation_failed", 422, "cap_cu: 0 to 100000 cost units.",
            {"fields": [{"field": "cap_cu", "in": "body", "message": "0 to 100000"}]},
        )
    quotas.set_overage_cap(db, caller.user, cap)
    return service.usage(db, caller.user)


# --- 5.3 -----------------------------------------------------------------------------------


@router.get("")
def list_jobs(
    project_id: str | None = None,
    kind: str | None = None,
    state: str | None = None,
    cursor: str | None = None,
    limit: int = service.PAGE_DEFAULT,
    caller: ProjectCaller = Depends(get_job_caller),
    db: Session = Depends(get_db),
) -> dict:
    return service.list_jobs(db, caller.user, project_id=project_id, kind=kind, state=state, cursor=cursor, limit=limit)


# --- 5.2 -----------------------------------------------------------------------------------


def _read(user_id: int, job_id: str) -> dict:
    from ..models import User

    with SessionLocal() as db:
        user = db.get(User, user_id)
        return service.record_json(service.own_job(db, user, job_id))


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    rev: int | None = None,
    wait_s: float = 0,
    caller: ProjectCaller = Depends(get_job_caller),
    db: Session = Depends(get_db),
) -> dict:
    if not 0 <= wait_s <= queue.STATUS_WAIT_MAX_S:
        raise ContractError(
            "validation_failed", 422, f"wait_s: 0 to {queue.STATUS_WAIT_MAX_S}.",
            {"fields": [{"field": "wait_s", "in": "query", "message": f"0 to {queue.STATUS_WAIT_MAX_S}"}]},
        )
    user_id = caller.user.id
    await run_in_threadpool(db.close)  # hold no connection while waiting
    record = await run_in_threadpool(_read, user_id, job_id)
    if wait_s <= 0 or rev is None or record["rev"] > rev:
        return record
    waiter = waiters.Waiter(queue.job_key(job_id))
    loop = asyncio.get_running_loop()
    deadline = loop.time() + wait_s
    try:
        while True:
            # Registered before this read: a change after it wakes the wait below.
            record = await run_in_threadpool(_read, user_id, job_id)
            remaining = deadline - loop.time()
            if record["rev"] > rev or remaining <= 0:
                return record
            await waiter.wait(min(waiters.RECHECK_S, remaining))
    finally:
        waiter.close()


# --- 5.4, 5.5 ------------------------------------------------------------------------------


@router.post("/{job_id}/cancel")
def cancel(job_id: str, caller: ProjectCaller = Depends(get_job_caller), db: Session = Depends(get_db)) -> dict:
    return service.record_json(service.cancel(db, caller.user, job_id))


@router.get("/{job_id}/output")
def output(job_id: str, response: Response, caller: ProjectCaller = Depends(get_job_caller), db: Session = Depends(get_db)) -> dict:
    response.headers.update(PRIVATE)
    return service.output(db, caller.user, job_id)
