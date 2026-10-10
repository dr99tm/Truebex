"""`python -m app.render.depth`: print how many render jobs are queued.

infra/host/bin/queue-depth runs this in the worker container for
host-check.sh, which alerts when the number passes QUEUE_DEPTH_MAX.
"""

import sys

from sqlalchemy import func, select

from ..database import SessionLocal, init_db
from .models import RenderJob


def queued() -> int:
    with SessionLocal() as db:
        return int(db.scalar(select(func.count()).select_from(RenderJob).where(RenderJob.state == "queued")) or 0)


def main() -> int:
    init_db()
    print(queued())
    return 0


if __name__ == "__main__":
    sys.exit(main())
