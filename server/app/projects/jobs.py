"""Project service background jobs (registered with app.tasks on import).

* `projects.snapshots.prune` (1 h): the newest five snapshots plus every
  version's stay; other snapshots and the blobs nothing names go.
* `projects.purge_deleted` (24 h): projects deleted more than 30 days ago go
  with their rows and every blob under `projects/{pid}/`.
* `projects.presence.sweep` (10 s): presence older than 30 s goes.
"""

from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..storage import get_store
from ..tasks import periodic
from . import presence, snapshots
from .models import OpTouched, Project, ProjectMember, ProjectOp, ProjectSnapshot, ProjectVersion

PURGE_AFTER = timedelta(days=30)


@periodic("projects.snapshots.prune", 3600)
def prune_snapshots(now: datetime) -> int:
    with SessionLocal() as db:
        return snapshots.prune_all(db)


def purge_project(db: Session, project: Project) -> None:
    store = get_store()
    for info in store.list(f"projects/{project.project_id}/"):
        store.delete(info.key)
    pid = project.project_id
    presence.backend().drop_project(db, pid)
    for model in (OpTouched, ProjectOp, ProjectVersion, ProjectSnapshot, ProjectMember):
        db.execute(delete(model).where(model.project_id == pid))
    db.delete(project)
    db.commit()


@periodic("projects.purge_deleted", 86400)
def purge_deleted(now: datetime) -> int:
    with SessionLocal() as db:
        gone = db.scalars(
            select(Project).where(Project.deleted_at.is_not(None), Project.deleted_at <= now - PURGE_AFTER)
        ).all()
        for project in gone:
            purge_project(db, project)
        return len(gone)


@periodic("projects.presence.sweep", 10)
def sweep_presence(now: datetime) -> int:
    with SessionLocal() as db:
        return presence.backend().sweep(db, now)
