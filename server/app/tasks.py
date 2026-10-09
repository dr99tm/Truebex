"""Periodic background jobs, run inline or by the worker process.

    @periodic("telemetry.rollup", seconds=3600)
    def rollup(now: datetime) -> None: ...

BACKGROUND_TASKS picks who runs them:
* `inline`: an asyncio loop inside the API process (`start_inline`, started
  from the app's lifespan); fine while the API runs one process.
* `worker`: the separate `python -m app.worker` process (PF14's Compose
  service); the API then runs none.
* `off`: nothing runs by itself; tests call `run_due(now)`.

A job runs when it never ran in this process or `seconds` have passed since
its last run. A failing job is logged and recorded in the crash store; the
others still run.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from .config import get_settings

log = logging.getLogger("truebex.tasks")
settings = get_settings()


@dataclass
class Task:
    name: str
    seconds: float
    fn: Callable[[datetime], object]
    last_run: datetime | None = None


_REGISTRY: dict[str, Task] = {}


def periodic(name: str, seconds: float):
    def register(fn: Callable[[datetime], object]):
        _REGISTRY[name] = Task(name=name, seconds=seconds, fn=fn)
        return fn

    return register


def registered() -> list[str]:
    _load_jobs()
    return list(_REGISTRY)


def unregister(name: str) -> None:
    _REGISTRY.pop(name, None)


def reset() -> None:
    """Forget when each job last ran (tests)."""
    for task in _REGISTRY.values():
        task.last_run = None


def _load_jobs() -> None:
    # Importing the modules registers their jobs.
    from . import ops, ratelimit  # noqa: F401
    from .telemetry import jobs  # noqa: F401


def run_due(
    now: datetime | None = None, *, only: list[str] | None = None, force: bool = False
) -> list[str]:
    """Run every job that is due at `now` (every named one with `force`);
    returns the names that ran."""
    _load_jobs()
    now = now or datetime.now(timezone.utc)
    names = only if only is not None else list(_REGISTRY)
    ran = []
    for name in names:
        task = _REGISTRY.get(name)
        if task is None:
            continue
        if not force and task.last_run is not None and (now - task.last_run).total_seconds() < task.seconds:
            continue
        task.last_run = now
        ran.append(name)
        try:
            task.fn(now)
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


def start_inline(app) -> asyncio.Task | None:
    """Start the in-process loop when BACKGROUND_TASKS=inline."""
    if settings.background_tasks != "inline":
        return None
    task = asyncio.get_running_loop().create_task(_loop(5.0))
    app.state.background_tasks = task
    return task


def run_forever(interval: float = 1.0, stop: Callable[[], bool] = lambda: False) -> None:
    """The worker process's loop (blocking)."""
    while not stop():
        started = time.monotonic()
        run_due()
        time.sleep(max(0.0, interval - (time.monotonic() - started)))
