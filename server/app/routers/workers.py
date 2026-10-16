"""The worker protocol (contract render-jobs v1.1, 5.7-5.10).

Auth: a worker token (`tbx_wrk_…`), scoped to kinds; a revoked one answers
401 `worker_revoked`. 5.7 is an `async` long-poll (`wait_s` ≤ 20, inside
Cloudflare's 100 s idle limit): 200 with a job and its lease, or 204 when
nothing is queued for this worker. 5.8-5.10 need the claim's `lease_id`
(409 `lease_lost` otherwise); 5.9 and 5.10 are safe to repeat per lease.

PF6b: the claim long poll checks that its worker is still connected before
every try, so a worker stopped while its claim waits takes no job, and a job
claimed for a worker that went away in between goes back to the queue with
no attempt spent (`queue.unclaim`). A worker that vanished without closing
its connection (a machine powered off, a cut network) is still caught by
§6.4's lease: `release_held` at its next claim, or the 120 s lapse.
"""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..contract_http import ContractError, contract
from ..database import SessionLocal, get_db
from ..licence import clock
from ..projects import waiters
from ..render import queue, service
from ..render.models import Worker
from ..render.workers import get_worker

log = logging.getLogger("truebex.render.claim")
router = APIRouter(prefix="/workers", tags=["workers"], dependencies=[contract("render-jobs", 1, 1)])
# 5.7 answers with its own Response, which the dependency's echo does not reach.
ECHO = {"X-Truebex-Contract": "render-jobs/1.1"}
COMPLETE_MAX_BYTES = 8 * 1024 * 1024


class ClaimIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    worker_id: str = Field(max_length=40)
    kinds: list[str] = Field(min_length=1, max_length=10)
    app_version: str = Field(default="", max_length=32)
    doc_version_max: int = Field(ge=0, le=1_000_000)
    wait_s: float = Field(default=0, ge=0, le=queue.CLAIM_WAIT_MAX_S)


class HeartbeatIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lease_id: str = Field(max_length=32)
    progress: float = Field(default=0, ge=0, le=1)
    message: str = Field(default="", max_length=200)


class UsageIn(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    wall_s: float = Field(ge=0, le=7 * 24 * 3600)
    worker_class: str = Field(alias="class", max_length=16)


class CompleteIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lease_id: str = Field(max_length=32)
    output: Any
    usage: UsageIn
    render_log: Any = None


class FailIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lease_id: str = Field(max_length=32)
    code: str = Field(max_length=32)
    message: str = Field(default="", max_length=2000)
    retryable: bool = True
    # The contract's 64 KiB; a longer tail is cut to its last 64 KiB.
    log_tail: str = Field(default="", max_length=1024 * 1024)


def _claim_once(worker_id: str, kinds: list[str], doc_version_max: int) -> dict | None:
    with SessionLocal() as db:
        worker = db.get(Worker, worker_id)
        if worker is None or worker.revoked_at is not None:
            return None
        while True:
            now = clock.now()
            job_id = queue.try_claim(db, worker, kinds, doc_version_max, now)
            if job_id is None:
                return None
            payload = queue.prepare_claim(db, job_id, worker, now)
            if payload is not None:
                return payload


def _unclaim(job_id: str, lease_id: str) -> bool:
    with SessionLocal() as db:
        return queue.unclaim(db, job_id, lease_id, clock.now())


@router.post("/claim")
async def claim(
    request: Request, body: ClaimIn, worker: Worker = Depends(get_worker), db: Session = Depends(get_db)
):
    worker_id, scope = worker.worker_id, list(worker.kinds or [])
    if body.worker_id.strip().lower() != worker_id:
        raise ContractError(
            "validation_failed", 422, "worker_id: this token belongs to another worker.",
            {"fields": [{"field": "worker_id", "in": "body", "message": f"this token is {worker_id}'s"}]},
        )
    kinds = sorted(k for k in set(body.kinds) if k in scope)
    if not kinds:
        raise ContractError("forbidden", 403, "This worker's token covers none of these kinds.", {"allowed": scope})

    def checked_in() -> None:
        now = clock.now()
        row = db.get(Worker, worker_id)
        row.app_version = body.app_version or row.app_version
        row.doc_version_max = body.doc_version_max
        row.last_heartbeat_at = now
        if row.pool == "static":
            row.pool_state = "running"  # a hand-run machine that claims is up
        db.commit()
        queue.release_held(db, row, now)
        db.close()

    await run_in_threadpool(checked_in)
    waiter = waiters.Waiter(queue.CLAIM_KEY)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + body.wait_s
    try:
        while True:
            # A worker gone while its claim waited (Ctrl+C, a stopping machine)
            # takes no job. Nobody reads this answer.
            if await request.is_disconnected():
                log.info("worker %s went away while its claim waited; no job taken", worker_id)
                return Response(status_code=204, headers=ECHO)
            # Registered before this try: a job queued after it wakes the wait.
            payload = await run_in_threadpool(_claim_once, worker_id, kinds, body.doc_version_max)
            if payload is not None:
                if await request.is_disconnected():
                    # It went while the job was being claimed for it: the job goes
                    # back as it was, with no attempt spent.
                    job_id = payload["job"]["job_id"]
                    back = await run_in_threadpool(_unclaim, job_id, payload["lease_id"])
                    log.info(
                        "worker %s went away as job %s was claimed for it; %s", worker_id, job_id,
                        "given back, no attempt spent" if back else "it had already moved on",
                    )
                    return Response(status_code=204, headers=ECHO)
                return JSONResponse(payload, headers=ECHO)
            remaining = deadline - loop.time()
            if remaining <= 0:
                return Response(status_code=204, headers=ECHO)
            await waiter.wait(min(waiters.RECHECK_S, remaining))
    finally:
        waiter.close()


@router.post("/jobs/{job_id}/heartbeat")
def heartbeat(job_id: str, body: HeartbeatIn, worker: Worker = Depends(get_worker), db: Session = Depends(get_db)) -> dict:
    return queue.heartbeat(db, worker, job_id, body.lease_id, body.progress, body.message, clock.now())


def _complete_size(request: Request) -> None:
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > COMPLETE_MAX_BYTES:
        raise ContractError("too_large", 413, "A completion is at most 8 MiB.", {"limit": COMPLETE_MAX_BYTES})


@router.post("/jobs/{job_id}/complete", dependencies=[Depends(_complete_size)])
def complete(job_id: str, body: CompleteIn, worker: Worker = Depends(get_worker), db: Session = Depends(get_db)) -> dict:
    job = queue.complete(
        db, worker, job_id, body.lease_id, body.output, body.usage.wall_s, body.usage.worker_class, body.render_log,
        clock.now(),
    )
    return service.record_json(job)


@router.post("/jobs/{job_id}/fail")
def fail(job_id: str, body: FailIn, worker: Worker = Depends(get_worker), db: Session = Depends(get_db)) -> dict:
    if body.code not in queue.FAIL_CODES:
        raise ContractError(
            "validation_failed", 422, f"code: one of {', '.join(queue.FAIL_CODES)}.",
            {"fields": [{"field": "code", "in": "body", "message": "a 5.10 code"}]},
        )
    job = queue.fail(
        db, worker, job_id, body.lease_id, body.code, body.message, body.retryable, body.log_tail, clock.now()
    )
    return service.record_json(job)
