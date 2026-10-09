"""Projects (contract 5.1-5.5): create, list, open, rename, delete; who may
do what (the §4 role matrix) and the project record every route returns.

Non-members get 404 for every project route, so a project's existence never
leaks. Deleting is soft: the project disappears at once and its rows and
blobs go 30 days later (`projects.purge_deleted`).
"""

import base64
import json
import re
import secrets
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..licence import clock
from ..licence.ids import uuid7_hex
from ..models import User
from . import quotas
from .caller import ProjectCaller
from .models import Project, ProjectMember, ProjectSnapshot

ROLES = ("viewer", "editor", "owner")
RANK = {role: i for i, role in enumerate(ROLES, start=1)}
NAME_MAX = 120
PAGE_DEFAULT = 50
PAGE_MAX = 100
_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_NEEDED_TEXT = {
    "editor": "Only editors and the owner can change this project.",
    "owner": "Only the project's owner can do this.",
}


def is_hex32(value: object) -> bool:
    return isinstance(value, str) and bool(_HEX32.match(value))


def not_found(what: str = "project") -> ContractError:
    return ContractError("not_found", 404, f"No such {what}.")


def clean_name(raw: str, field: str = "name", max_len: int = NAME_MAX) -> str:
    name = " ".join((raw or "").split())
    if not name or len(name) > max_len:
        raise ContractError(
            "validation_failed",
            422,
            f"{field}: give a name of 1 to {max_len} characters.",
            {"fields": [{"field": field, "in": "body", "message": f"1 to {max_len} characters"}]},
        )
    return name


def display_name(user: User) -> str:
    return user.name or user.email.split("@", 1)[0]


# --- access -------------------------------------------------------------------


def membership(db: Session, project_id: str, user_id: int) -> ProjectMember | None:
    return db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.state == "active",
        )
    )


def open_project(db: Session, caller: ProjectCaller, project_id: str, needed: str = "viewer") -> tuple[Project, ProjectMember]:
    """The live project and the caller's membership, or 404; 403 when the role is too low."""
    project = db.get(Project, project_id) if is_hex32(project_id) else None
    if project is None or project.deleted_at is not None:
        raise not_found()
    member = membership(db, project_id, caller.user.id)
    if member is None:
        raise not_found()
    require_role(member, needed)
    return project, member


def require_role(member: ProjectMember, needed: str) -> None:
    if RANK[member.role] < RANK[needed]:
        raise ContractError("forbidden", 403, _NEEDED_TEXT[needed], {"role": member.role, "needed": needed})


# --- the record -----------------------------------------------------------------


def snapshot_summary(snap: ProjectSnapshot | None) -> dict | None:
    if snap is None:
        return None
    return {
        "snapshot_id": snap.snapshot_id,
        "at_seq": snap.at_seq,
        "doc_version": snap.doc_version,
        "created_at": clock.rfc3339(snap.created_at),
    }


def latest_snapshot(db: Session, project_id: str) -> ProjectSnapshot | None:
    return db.scalar(
        select(ProjectSnapshot)
        .where(ProjectSnapshot.project_id == project_id)
        .order_by(ProjectSnapshot.at_seq.desc(), ProjectSnapshot.created_at.desc())
        .limit(1)
    )


def people_count(db: Session, project_id: str) -> int:
    """Active members (the owner included); 5.1-5.4's `members`."""
    return db.scalar(
        select(func.count())
        .select_from(ProjectMember)
        .where(ProjectMember.project_id == project_id, ProjectMember.state == "active")
    ) or 0


def record(
    db: Session,
    project: Project,
    role: str,
    *,
    owner: User | None = None,
    members: int | list | None = None,
    latest: ProjectSnapshot | None | bool = False,
) -> dict:
    owner = owner or db.get(User, project.owner_user_id)
    if latest is False:
        latest = latest_snapshot(db, project.project_id)
    return {
        "project_id": project.project_id,
        "name": project.name,
        "role": role,
        "owner": {"user_id": owner.id, "name": display_name(owner)} if owner else None,
        "org_id": project.org_id,
        "created_at": clock.rfc3339(project.created_at),
        "updated_at": clock.rfc3339(project.updated_at),
        "head_seq": project.head_seq,
        "latest_snapshot": snapshot_summary(latest),
        "doc_version": project.doc_version,
        "members": people_count(db, project.project_id) if members is None else members,
        "bytes": project.bytes,
    }


# --- 5.1 create -------------------------------------------------------------------


def create(db: Session, caller: ProjectCaller, name: str, doc_version: int) -> dict:
    name = clean_name(name)
    if doc_version < 1:
        raise ContractError(
            "validation_failed", 422, "doc_version must be 1 or more.",
            {"fields": [{"field": "doc_version", "in": "body", "message": "1 or more"}]},
        )
    plan = quotas.require_feature(db, caller.user)
    quotas.check_projects(db, caller.user, plan)
    now = clock.now()
    project = Project(
        project_id=uuid7_hex(),
        name=name,
        owner_user_id=caller.user.id,
        doc_version=doc_version,
        head_seq=0,
        bytes=0,
        server_replica_id=secrets.token_hex(16),
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    db.flush()
    db.add(
        ProjectMember(
            project_id=project.project_id,
            user_id=caller.user.id,
            email=caller.user.email,
            role="owner",
            state="active",
            invited_at=now,
            accepted_at=now,
        )
    )
    db.commit()
    return record(db, project, "owner", owner=caller.user, members=1, latest=None)


# --- 5.2 list ----------------------------------------------------------------------


def _encode_cursor(project: Project) -> str:
    raw = json.dumps({"u": clock.aware(project.updated_at).isoformat(), "p": project.project_id})
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        raw = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        at = datetime.fromisoformat(raw["u"])
        pid = raw["p"]
        if not is_hex32(pid):
            raise ValueError
        return at, pid
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise ContractError(
            "validation_failed", 422, "cursor is not one this server gave out.",
            {"fields": [{"field": "cursor", "in": "query", "message": "unknown cursor"}]},
        )


def list_projects(db: Session, caller: ProjectCaller, cursor: str | None, limit: int) -> dict:
    """Owned and shared with me, newest activity first."""
    q = (
        select(Project, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.project_id)
        .where(
            ProjectMember.user_id == caller.user.id,
            ProjectMember.state == "active",
            Project.deleted_at.is_(None),
        )
    )
    if cursor:
        at, pid = _decode_cursor(cursor)
        q = q.where(or_(Project.updated_at < at, and_(Project.updated_at == at, Project.project_id < pid)))
    rows = db.execute(q.order_by(Project.updated_at.desc(), Project.project_id.desc()).limit(limit + 1)).all()
    page = rows[:limit]
    ids = [p.project_id for p, _ in page]
    owners = {u.id: u for u in db.scalars(select(User).where(User.id.in_({p.owner_user_id for p, _ in page})))} if page else {}
    counts = dict(
        db.execute(
            select(ProjectMember.project_id, func.count())
            .where(ProjectMember.project_id.in_(ids), ProjectMember.state == "active")
            .group_by(ProjectMember.project_id)
        ).all()
    ) if ids else {}
    out = [
        record(db, p, role, owner=owners.get(p.owner_user_id), members=counts.get(p.project_id, 0))
        for p, role in page
    ]
    return {"projects": out, "next_cursor": _encode_cursor(page[-1][0]) if len(rows) > limit else None}


# --- 5.3 open, 5.4 rename, 5.5 delete ------------------------------------------------


def touch(project: Project) -> None:
    project.updated_at = clock.now()


def rename(db: Session, project: Project, name: str) -> None:
    project.name = clean_name(name)
    touch(project)
    db.commit()


def soft_delete(db: Session, project: Project) -> None:
    project.deleted_at = clock.now()
    db.commit()
