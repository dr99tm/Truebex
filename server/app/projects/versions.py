"""Named versions and restore (contract 5.10-5.12).

A version names a snapshot at exactly its `at_seq` (422
`snapshot_seq_mismatch` otherwise) and pins it against pruning. Restore
appends a `restore` operation with the project's own replica id and the
caller's author id; it conflicts with nothing and counts as touching every
id, so operations made before it are rejected with the restore as winner.
"""

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..licence import clock
from . import ops
from .models import Project, ProjectVersion
from .service import clean_name, is_hex32, not_found, touch
from .snapshots import get as get_snapshot

NOTE_MAX = 2000


def version_json(v: ProjectVersion) -> dict:
    return {
        "version_id": v.version_id,
        "name": v.name,
        "note": v.note,
        "at_seq": v.at_seq,
        "snapshot_id": v.snapshot_id,
        "created_by": v.created_by,
        "created_at": clock.rfc3339(v.created_at),
    }


def list_versions(db: Session, project: Project) -> dict:
    rows = db.scalars(
        select(ProjectVersion)
        .where(ProjectVersion.project_id == project.project_id)
        .order_by(ProjectVersion.at_seq.desc(), ProjectVersion.created_at.desc())
    ).all()
    return {"versions": [version_json(v) for v in rows]}


def create(db: Session, project: Project, *, user_id: int, name: str, note: str, at_seq: int, snapshot_id: str) -> dict:
    name = clean_name(name)
    note = (note or "").strip()
    if len(note) > NOTE_MAX:
        raise ContractError(
            "validation_failed", 422, f"note: at most {NOTE_MAX} characters.",
            {"fields": [{"field": "note", "in": "body", "message": f"at most {NOTE_MAX} characters"}]},
        )
    snap = get_snapshot(db, project, snapshot_id)
    if snap.at_seq != at_seq:
        raise ContractError(
            "snapshot_seq_mismatch",
            422,
            f"That snapshot is at {snap.at_seq}, not {at_seq}. Name the version at the snapshot's number.",
            {"snapshot_at_seq": snap.at_seq, "at_seq": at_seq},
        )
    version = ProjectVersion(
        version_id=secrets.token_hex(16),
        project_id=project.project_id,
        name=name,
        note=note,
        at_seq=at_seq,
        snapshot_id=snap.snapshot_id,
        created_by=user_id,
        created_at=clock.now(),
    )
    db.add(version)
    touch(project)
    db.commit()
    return version_json(version)


def restore(db: Session, project_id: str, version_id: str, *, author_id: str) -> dict:
    """Append the restore operation; returns it as it travels (5.12)."""
    version = db.get(ProjectVersion, version_id) if is_hex32(version_id) else None
    if version is None or version.project_id != project_id:
        raise not_found("version")
    project = ops.lock_project(db, project_id)
    try:
        op = ops.ParsedOp(
            op_id=secrets.token_hex(16),
            author=author_id,
            author_kind="person",
            at=ops.at_now(),
            touched=[],
            kind="restore",
            name=f"Restore {version.name}"[:80],
            base_seq=project.head_seq,
            delta_format=None,
            delta=None,
            action=None,
        )
        row = ops.append(
            db,
            project,
            op,
            project.server_replica_id,
            restore={"version_id": version.version_id, "at_seq": version.at_seq, "snapshot_id": version.snapshot_id},
        )
        touch(project)
        wire = ops.op_json(row)
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return wire
