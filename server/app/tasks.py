"""Periodic background jobs (PF14 Plumbing), run inline or by the worker process.

    @periodic("telemetry.rollup", seconds=600)
    def rollup(now: datetime) -> None: ...  # opens its own DB session

BACKGROUND_TASKS picks who runs them:
* `inline`: an asyncio loop inside the API process (`start_inline`, started
  from the app's lifespan); fine while the API runs one process.
* `worker`: the separate `python -m app.worker` process (PF14's Compose
  service); the API then runs none.
* `off`: nothing runs by itself; tests call `run_due(now)` or the job
  functions themselves.

A job runs once at start, then every `seconds`. A failing job is logged and
recorded in the crash store, retried at its next slot, and the others still
run. Users: PF14 (telemetry.*, crash.*, backup.*, worker.*, ratelimit.*),
PF1 (licence.*) and PF2 (billing.*).
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .config import get_settings

log = logging.getLogger("truebex.tasks")
settings = get_settings()

# How often the inline loop looks for due jobs.
TICK_S = 5.0


@dataclass
class Job:
    name: str
    seconds: float
    fn: Callable[[datetime], object]
    next_run: datetime | None = None


_JOBS: dict[str, Job] = {}


def periodic(name: str, seconds: float) -> Callable:
    """Register `fn(now)` to run every `seconds`."""

    def register(fn: Callable[[datetime], object]) -> Callable[[datetime], object]:
        _JOBS[name] = Job(name=name, seconds=seconds, fn=fn)
        return fn

    return register


def _load_jobs() -> None:
    # Importing the modules registers their jobs (the worker process imports
    # nothing else, so every module with jobs is listed here).
    from . import ops, ratelimit  # noqa: F401
    from .billing import jobs as _billing  # noqa: F401
    from .licence import jobs as _licence  # noqa: F401
    from .orgs import jobs as _orgs  # noqa: F401
    from .sso import jobs as _sso  # noqa: F401
    from .telemetry import jobs as _telemetry  # noqa: F401
    from .shares import jobs as _shares  # noqa: F401  (PF5)
    from .uploads import jobs as _uploads  # noqa: F401  (PF5)
    from .market import jobs as _market  # noqa: F401  (PF7)


def jobs() -> dict[str, Job]:
    return dict(_JOBS)


def registered() -> list[str]:
    _load_jobs()
    return list(_JOBS)


def unregister(name: str) -> None:
    _JOBS.pop(name, None)


def reset() -> None:
    """Forget when each job last ran (tests)."""
    for job in _JOBS.values():
        job.next_run = None


def run_due(
    now: datetime | None = None, *, only: list[str] | None = None, force: bool = False
) -> list[str]:
    """Run every job whose slot has come (every named one with `force`);
    returns the names that ran."""
    _load_jobs()
    now = now or datetime.now(timezone.utc)
    names = only if only is not None else list(_JOBS)
    ran = []
    for name in names:
        job = _JOBS.get(name)
        if job is None:
            continue
        if not force and job.next_run is not None and job.next_run > now:
            continue
        job.next_run = now + timedelta(seconds=job.seconds)
        ran.append(name)
        try:
            job.fn(now)
        except Exception as exc:  # noqa: BLE001 - one job must not stop the rest
            log.exception("job %s failed", name)
            _record_failure(name, exc)
    return ran


def _record_failure(name: str, exc: Exception) -> None:
    try:
        from .telemetry.service import record_server_exception

        record_server_exception(exc, route=f"job:{name}")
    except Exception:  # noqa: BLE001
        log.exception("could not record the failure of %s", name)


async def _loop(interval: float) -> None:
    while True:
        try:
            await asyncio.to_thread(run_due)
        except Exception:  # noqa: BLE001
            log.exception("background loop")
        await asyncio.sleep(interval)


def start_inline(app) -> "asyncio.Task[None] | None":
    """Start the in-process loop when BACKGROUND_TASKS=inline; cancel the
    returned task on shutdown."""
    if settings.background_tasks != "inline":
        return None
    task = asyncio.get_running_loop().create_task(_loop(TICK_S), name="truebex-tasks")
    app.state.background_tasks = task
    return task


def run_forever(interval: float = 1.0, stop: Callable[[], bool] = lambda: False) -> None:
    """The worker process's loop (blocking)."""
    while not stop():
        started = time.monotonic()
        run_due()
        time.sleep(max(0.0, interval - (time.monotonic() - started)))
