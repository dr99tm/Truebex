"""Routes the mobile web client adds (PF9), beside PF4's project routes.

GET /projects/{pid}/panoramas            the project's followed sets (viewer role)
GET /projects/{pid}/panoramas/{set_id}   one set's newest manifest; long-poll with
                                         `rev` and `wait_s` (≤ 25), as 5.2 does

Auth as every project route (contract project-log §4): a session (the web
client) or a device token; 404 for non-members. Answers are never cached.
"""

import asyncio

from fastapi import APIRouter, Depends, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..contract_http import ContractError, contract
from ..database import SessionLocal, get_db
from ..mobile import panoramas
from ..projects import service, waiters
from ..projects.caller import ProjectCaller, get_project_caller
from ..render import queue
from ..render.models import RenderSet

router = APIRouter(prefix="/projects", tags=["mobile"], dependencies=[contract("project-log", 1, 0)])
PRIVATE = {"Cache-Control": "private, no-store"}


@router.get("/{project_id}/panoramas")
def list_panoramas(
    project_id: str,
    response: Response,
    caller: ProjectCaller = Depends(get_project_caller),
    db: Session = Depends(get_db),
) -> dict:
    project, _ = service.open_project(db, caller, project_id)
    response.headers.update(PRIVATE)
    return panoramas.list_json(db, project.project_id, caller.user.id)


def _rev(set_id: str) -> int:
    with SessionLocal() as db:
        return db.scalar(select(RenderSet.rev).where(RenderSet.follow_job_id == set_id)) or 0


def _state(project_id: str, set_id: str) -> dict:
    with SessionLocal() as db:
        return panoramas.state(db, panoramas.find(db, project_id, set_id))


@router.get("/{project_id}/panoramas/{set_id}")
async def panorama_set(
    project_id: str,
    set_id: str,
    response: Response,
    rev: int | None = None,
    wait_s: float = 0,
    caller: ProjectCaller = Depends(get_project_caller),
    db: Session = Depends(get_db),
) -> dict:
    if not 0 <= wait_s <= queue.STATUS_WAIT_MAX_S:
        raise ContractError(
            "validation_failed", 422, f"wait_s: 0 to {queue.STATUS_WAIT_MAX_S}.",
            {"fields": [{"field": "wait_s", "in": "query", "message": f"0 to {queue.STATUS_WAIT_MAX_S}"}]},
        )

    def resolve() -> tuple[str, str, int]:
        project, _ = service.open_project(db, caller, project_id)
        row = panoramas.find(db, project.project_id, set_id)
        return project.project_id, row.follow_job_id, row.rev

    pid, sid, current = await run_in_threadpool(resolve)
    response.headers.update(PRIVATE)
    await run_in_threadpool(db.close)  # no connection held while waiting
    if wait_s <= 0 or rev is None or current > rev:
        return await run_in_threadpool(_state, pid, sid)
    waiter = waiters.Waiter(queue.job_key(sid))
    loop = asyncio.get_running_loop()
    deadline = loop.time() + wait_s
    try:
        while True:
            current = await run_in_threadpool(_rev, sid)
            remaining = deadline - loop.time()
            if current > rev or remaining <= 0:
                return await run_in_threadpool(_state, pid, sid)
            await waiter.wait(min(waiters.RECHECK_S, remaining))
    finally:
        waiter.close()
