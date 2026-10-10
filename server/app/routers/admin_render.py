"""The render admin (admins only, `require_admin`; PF6).

GET    /admin/render                 queue depth and oldest wait by kind, workers, the pool, cost by kind this month
GET    /admin/workers                every worker token (never the token itself)
POST   /admin/workers                issue a `tbx_wrk_…` token for a name, kinds and class (shown once)
DELETE /admin/workers/{worker_id}    revoke: its next call gets 401 `worker_revoked`, its lease ends now
"""

from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..contract_http import enveloped
from ..database import get_db
from ..deps import require_admin
from ..licence import clock
from ..models import User
from ..render import pools, quotas, service, workers
from ..render.models import RenderJob, Worker

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[enveloped()])


class IssueIn(BaseModel):
    name: str = Field(max_length=40)
    kinds: list[str] = Field(min_length=1, max_length=5)
    worker_class: str = Field(default="gpu-std", alias="class", max_length=16)


@router.get("/render")
def overview(_admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    now = clock.now()
    queue = []
    for kind in quotas.CONTRACT_KINDS:
        queued, oldest = db.execute(
            select(func.count(), func.min(RenderJob.queued_at)).where(RenderJob.state == "queued", RenderJob.kind == kind)
        ).one()
        running = db.scalar(
            select(func.count()).select_from(RenderJob).where(
                RenderJob.state.in_(("claimed", "running")), RenderJob.kind == kind
            )
        ) or 0
        if kind not in quotas.KINDS and not queued and not running:
            continue
        queue.append(
            {
                "kind": kind,
                "queued": int(queued or 0),
                "running": int(running),
                "oldest_wait_s": int((now - clock.aware(oldest)).total_seconds()) if oldest is not None else None,
            }
        )
    start, _ = quotas.month_bounds(now)
    month_start = datetime.combine(start, time.min, tzinfo=timezone.utc)
    pool = pools.get_pool()
    classes = sorted({k.worker_class for k in quotas.KINDS.values()})
    rows = db.scalars(select(Worker).order_by(Worker.revoked_at.is_not(None), Worker.worker_id)).all()
    busy = {
        w: j
        for w, j in db.execute(
            select(RenderJob.worker_id, RenderJob.job_id).where(RenderJob.state.in_(("claimed", "running")))
        ).all()
    }
    failures = db.scalars(
        select(RenderJob).where(RenderJob.state == "failed").order_by(RenderJob.finished_at.desc()).limit(10)
    ).all()
    return {
        "now": clock.rfc3339(now),
        "queue": queue,
        "workers": [{**workers.worker_json(w), "job_id": busy.get(w.worker_id)} for w in rows],
        "pool": {
            "name": pool.name,
            "classes": [
                {
                    "class": c,
                    "desired": pools.DESIRED.get(c),
                    "running": sum(1 for m in pool.list(db, c) if m.state == "running"),
                    **pools.queue_stats(db, c, now),
                }
                for c in classes
            ],
        },
        "cost_by_kind": service.recent_cost_by_kind(db, month_start),
        "period_start": quotas.rfc3339_day(start),
        "recent_failures": [
            {"job_id": j.job_id, "kind": j.kind, "error": j.error, "finished_at": clock.rfc3339(j.finished_at)}
            for j in failures
        ],
    }


@router.get("/workers")
def list_workers(_admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(Worker).order_by(Worker.worker_id)).all()
    return {"workers": [workers.worker_json(w) for w in rows]}


@router.post("/workers", status_code=201)
def issue_worker(body: IssueIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    row, token = workers.issue(db, name=body.name, kinds=body.kinds, worker_class=body.worker_class, admin_id=admin.id)
    return {**workers.worker_json(row), "token": token}


@router.delete("/workers/{worker_id}")
def revoke_worker(worker_id: str, _admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    return workers.worker_json(workers.revoke(db, worker_id))
