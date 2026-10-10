"""Worker pools and the scaling policy (PF6 Scope 7; numbers from GD3).

    pool = get_pool()
    pool.list(db, "gpu-std")      # machines of a class
    pool.desired(db, "gpu-std", 2)
    pool.start(db, machine_id); pool.stop(db, machine_id)

`static` is the only adapter until GD3 names a cloud provider: its machines
are the registered workers (the owner's RTX PC included). The platform cannot
power a hand-run machine, so `start` and `stop` record what the pool wants
(the admin page shows it) and a stopped static machine that claims anyway is
taken as running again. A cloud adapter implements the same four calls with
the provider's API.

`render.autoscale` (every 30 s), per class: desired = clamp(ceil(queued / 4)
+ running, min, max), one more while the oldest queued job has waited over
30 s; a running machine idle 10 minutes is stopped while more run than are
wanted. min, max, the business-hours warm pool and the idle time are
settings (GD3 placeholders).
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..licence import clock
from . import quotas
from .models import RenderJob, Worker

JOBS_PER_MACHINE = 4
WAIT_SCALE_S = 30
# What the last autoscale wanted, per class (the admin page shows it).
DESIRED: dict[str, int] = {}


@dataclass(frozen=True)
class Machine:
    machine_id: str
    worker_class: str
    state: str  # running | stopped
    busy: bool
    idle_since: datetime | None
    last_heartbeat_at: datetime | None


class WorkerPool(Protocol):
    name: str

    def list(self, db: Session, worker_class: str) -> list[Machine]: ...

    def desired(self, db: Session, worker_class: str, n: int) -> None: ...

    def start(self, db: Session, machine_id: str) -> None: ...

    def stop(self, db: Session, machine_id: str) -> None: ...


class StaticPool:
    """Machines registered by hand: one per worker token."""

    name = "static"

    def list(self, db: Session, worker_class: str) -> list[Machine]:
        rows = db.scalars(
            select(Worker).where(
                Worker.pool == self.name, Worker.worker_class == worker_class, Worker.revoked_at.is_(None)
            ).order_by(Worker.worker_id)
        ).all()
        busy = set(
            db.scalars(
                select(RenderJob.worker_id).where(
                    RenderJob.state.in_(("claimed", "running")), RenderJob.worker_id.is_not(None)
                )
            )
        )
        return [
            Machine(
                machine_id=w.worker_id,
                worker_class=w.worker_class,
                state=w.pool_state,
                busy=w.worker_id in busy,
                idle_since=clock.aware(w.idle_since) if w.idle_since else None,
                last_heartbeat_at=clock.aware(w.last_heartbeat_at) if w.last_heartbeat_at else None,
            )
            for w in rows
        ]

    def desired(self, db: Session, worker_class: str, n: int) -> None:
        DESIRED[worker_class] = n

    def _set(self, db: Session, machine_id: str, state: str) -> None:
        row = db.get(Worker, machine_id)
        if row is not None and row.pool == self.name and row.pool_state != state:
            row.pool_state = state
            if state == "running":
                row.idle_since = clock.now()

    def start(self, db: Session, machine_id: str) -> None:
        self._set(db, machine_id, "running")

    def stop(self, db: Session, machine_id: str) -> None:
        self._set(db, machine_id, "stopped")


_POOLS: dict[str, WorkerPool] = {"static": StaticPool()}


def get_pool(name: str | None = None) -> WorkerPool:
    name = name or get_settings().render_pool
    pool = _POOLS.get(name)
    if pool is None:
        raise RuntimeError(f"Unknown RENDER_POOL {name!r} (GD3 has not named a cloud provider yet)")
    return pool


def _classes() -> list[str]:
    return sorted({k.worker_class for k in quotas.KINDS.values()})


def _bounds(now: datetime) -> tuple[int, int]:
    s = get_settings()
    low, high = max(0, s.render_pool_min), max(0, s.render_pool_max)
    hours = (s.render_pool_warm_hours or "").strip()
    if hours and "-" in hours:
        first, _, last = hours.partition("-")
        if first.strip().isdigit() and last.strip().isdigit():
            hour = now.astimezone(timezone.utc).hour
            if int(first) <= hour < int(last):
                low = max(low, s.render_pool_warm_min)
    return low, max(low, high)


def want(queued: int, running: int, oldest_wait_s: float, low: int, high: int) -> int:
    n = math.ceil(queued / JOBS_PER_MACHINE) + running
    if queued and oldest_wait_s > WAIT_SCALE_S:
        n += 1
    return max(low, min(high, n))


def queue_stats(db: Session, worker_class: str, now: datetime) -> dict:
    kinds = [k.name for k in quotas.KINDS.values() if k.worker_class == worker_class]
    queued, oldest = db.execute(
        select(func.count(), func.min(RenderJob.queued_at)).where(
            RenderJob.state == "queued", RenderJob.kind.in_(kinds)
        )
    ).one()
    running = db.scalar(
        select(func.count()).select_from(RenderJob).where(
            RenderJob.state.in_(("claimed", "running")), RenderJob.kind.in_(kinds)
        )
    ) or 0
    wait = (now - clock.aware(oldest)).total_seconds() if oldest is not None else 0.0
    return {"queued": int(queued or 0), "running": int(running), "oldest_wait_s": max(0.0, wait)}


def autoscale(db: Session, now: datetime, pool: WorkerPool | None = None) -> dict[str, int]:
    pool = pool or get_pool()
    idle_stop = timedelta(seconds=get_settings().render_pool_idle_stop_s)
    low, high = _bounds(now)
    out = {}
    for worker_class in _classes():
        stats = queue_stats(db, worker_class, now)
        n = want(stats["queued"], stats["running"], stats["oldest_wait_s"], low, high)
        pool.desired(db, worker_class, n)
        machines = pool.list(db, worker_class)
        running = [m for m in machines if m.state == "running"]
        for m in [m for m in machines if m.state != "running"][: max(0, n - len(running))]:
            pool.start(db, m.machine_id)
            running.append(m)
        for m in sorted(running, key=lambda m: m.idle_since or now):
            if len(running) <= n:
                break
            if not m.busy and m.idle_since is not None and now - m.idle_since >= idle_stop:
                pool.stop(db, m.machine_id)
                running.remove(m)
        out[worker_class] = n
    db.commit()
    return out
