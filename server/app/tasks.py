"""Background jobs (PF14 §Design Plumbing; first user PF1).

    @periodic("licence.links.purge", 600)
    def purge(db, now): ...

`run_due(now)` runs every job whose interval has passed, each in its own DB
session. BACKGROUND_TASKS picks who calls it: `inline` (an asyncio loop in
the API process, started by `start_inline` from the lifespan), `worker`
(PF14's separate process) or `off` (tests call `run_due` themselves).
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

log = logging.getLogger("truebex.tasks")

JobFn = Callable[[Session, datetime], object]


@dataclass
class Job:
    name: str
    seconds: int
    fn: JobFn
    last_run: datetime | None = None


JOBS: dict[str, Job] = {}


def periodic(name: str, seconds: int) -> Callable[[JobFn], JobFn]:
    def register(fn: JobFn) -> JobFn:
        JOBS[name] = Job(name=name, seconds=seconds, fn=fn)
        return fn

    return register


def run_due(now: datetime | None = None, *, force: bool = False) -> list[str]:
    """Run the jobs that are due at `now`. Returns the names that ran."""
    from .database import SessionLocal

    now = now or datetime.now(timezone.utc)
    ran: list[str] = []
    for job in list(JOBS.values()):
        due = force or job.last_run is None or (now - job.last_run).total_seconds() >= job.seconds
        if not due:
            continue
        with SessionLocal() as db:
            try:
                job.fn(db, now)
                db.commit()
            except Exception:  # one failing job must not stop the others
                db.rollback()
                log.exception("job %s failed", job.name)
                continue
        job.last_run = now
        ran.append(job.name)
    return ran


def start_inline(app, tick_seconds: float = 30.0) -> asyncio.Task:
    """Start the inline scheduler; the returned task is cancelled at shutdown."""

    async def loop() -> None:
        while True:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(run_due)
            await asyncio.sleep(tick_seconds)

    task = asyncio.create_task(loop(), name="truebex-tasks")
    app.state.tasks = task
    return task
