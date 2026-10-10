"""Render background jobs (registered with app.tasks on import).

render.leases.reap      every 15 s   lapsed leases requeue (the fourth lapse fails)
render.jobs.expire      every 300 s  queued 24 h -> expired
render.autoscale        every 30 s   the worker pool follows queue depth and wait
render.tiles.gc         weekly       tiles no manifest of the last 90 days names
render.overage.charge   every 6 h    finished months' overage through PF2

Importing this module also subscribes the follow trigger to PF4's push hook
(`sets`) and the worker-token lookup to the upload protocol (`workers`).
"""

from datetime import datetime

from ..database import SessionLocal
from ..tasks import periodic
from . import overage, pools, queue, sets, tiles, workers  # noqa: F401  (sets, workers: hooks)


@periodic("render.leases.reap", 15)
def reap_leases(now: datetime) -> int:
    with SessionLocal() as db:
        return queue.reap(db, now)


@periodic("render.jobs.expire", 300)
def expire_jobs(now: datetime) -> int:
    with SessionLocal() as db:
        return queue.expire(db, now)


@periodic("render.autoscale", 30)
def autoscale(now: datetime) -> dict:
    with SessionLocal() as db:
        return pools.autoscale(db, now)


@periodic("render.tiles.gc", 7 * 24 * 3600)
def tiles_gc(now: datetime) -> int:
    with SessionLocal() as db:
        return tiles.gc(db, now)


@periodic("render.overage.charge", 6 * 3600)
def overage_charge(now: datetime) -> int:
    with SessionLocal() as db:
        return overage.run(db, now)
