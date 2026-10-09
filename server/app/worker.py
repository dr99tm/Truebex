"""The background worker: `python -m app.worker` (Compose service `worker`).

Runs every periodic job (app.tasks) in one process, so the API processes run
none (BACKGROUND_TASKS=worker). `python -m app.worker --check` is the
container's healthcheck: exit 0 when the heartbeat is under 120 s old.
"""

import argparse
import logging
import signal
import sys

from . import ops, tasks
from .database import init_db

log = logging.getLogger("truebex.worker")


def check(max_age_s: int = 120) -> int:
    try:
        age = ops.heartbeat_age_s()
    except Exception:  # noqa: BLE001 - database unreachable
        return 1
    return 0 if age is not None and age <= max_age_s else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.worker")
    parser.add_argument("--check", action="store_true", help="exit 0 when the heartbeat is fresh")
    args = parser.parse_args(argv)
    if args.check:
        return check()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    init_db()
    stopping = False

    def stop(_signum, _frame) -> None:
        nonlocal stopping
        stopping = True
        log.info("stopping after the current round")

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log.info("worker started with jobs: %s", ", ".join(tasks.registered()))
    tasks.run_forever(interval=1.0, stop=lambda: stopping)
    return 0


if __name__ == "__main__":
    sys.exit(main())
