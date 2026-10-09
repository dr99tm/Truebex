"""Background jobs (PF14 Plumbing): `@periodic(name, seconds)`, `run_due(now)`,
`start_inline(app)`. First users: PF1 (licence.*) and PF2 (billing.*).

    @periodic("licence.links.purge", 600)
    def purge(now): ...  # opens its own DB session

BACKGROUND_TASKS=inline runs due jobs from an asyncio loop started in the
app's lifespan; `worker` leaves them to `python -m app.worker` (PF14); `off`
runs nothing (tests call `run_due` or the job functions themselves). A job
runs once at start, then every `seconds`; a failing job is logged and retried
at its next slot.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

log = logging.getLogger("truebex.tasks")

# How often the inline loop looks for due jobs.
TICK_S = 30


@dataclass
class Job:
    name: str
    seconds: int
    fn: Callable[[datetime], object]
    next_run: datetime | None = None


_JOBS: dict[str, Job] = {}


def periodic(name: str, seconds: int) -> Callable:
    """Register `fn(now)` to run every `seconds`."""

    def register(fn: Callable[[datetime], object]) -> Callable[[datetime], object]:
        _JOBS[name] = Job(name=name, seconds=seconds, fn=fn)
        return fn

    return register


def jobs() -> dict[str, Job]:
    return dict(_JOBS)


def run_due(now: datetime | None = None, *, force: bool = False) -> list[str]:
    """Run every job whose slot has come (every job with `force`). Returns the
    names that ran."""
    now = now or datetime.now(timezone.utc)
    ran = []
    for job in list(_JOBS.values()):
        if not force and job.next_run is not None and job.next_run > now:
            continue
        try:
            job.fn(now)
        except Exception:  # one job's failure never stops the others
            log.exception("job %s failed", job.name)
        job.next_run = now + timedelta(seconds=job.seconds)
        ran.append(job.name)
    return ran


def start_inline(app: object) -> "asyncio.Task[None]":
    """Start the inline loop; cancel the returned task on shutdown."""

    async def loop() -> None:
        while True:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(run_due)
            await asyncio.sleep(TICK_S)

    return asyncio.get_running_loop().create_task(loop(), name="truebex-tasks")
