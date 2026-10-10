"""The project service (contract project-log v1.0, PF4): projects, the
operation log, snapshots, versions and restore, members, presence.

Auth: a device token or a session (contract §4); roles per the §4 matrix on
every route, 404 for non-members. 5.5 needs a session (403
`session_required`). Pushes from a device need `cloud.sync`. 5.6 and 5.7 are
`async`: a pull long-polls on the event loop without holding a worker thread
or a database connection while it waits. Every error uses the shared envelope.
"""

import asyncio

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError, contract
from ..database import SessionLocal, get_db
from ..idempotency import Idempotency, idempotent
from ..licence.service import ensure_author_id
from ..models import User
from ..projects import hooks, members, ops, presence, quotas, service, snapshots, versions, waiters
from ..projects.caller import ProjectCaller, get_any_caller, get_project_caller, require_session

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[contract("project-log", 1, 0)])


class CreateIn(BaseModel):
    name: str = Field(max_length=500)
    doc_version: int


class RenameIn(BaseModel):
    name: str = Field(max_length=500)


class SnapshotFilesIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tbxp: str = Field(max_length=64)
    tbxpack: str | None = Field(default=None, max_length=64)


class SnapshotIn(BaseModel):
    at_seq: int
    doc_version: int
    upload_id: str = Field(max_length=32)
    files: SnapshotFilesIn


class VersionIn(BaseModel):
    name: str = Field(max_length=500)
    note: str = Field(default="", max_length=10_000)
    at_seq: int
    snapshot_id: str = Field(max_length=32)


class InviteIn(BaseModel):
    email: str = Field(max_length=320)
    role: str = Field(max_length=16)


class RoleIn(BaseModel):
    role: str = Field(max_length=16)


class AcceptIn(BaseModel):
    token: str = Field(min_length=1, max_length=200)


def _idempotent_call(idem: Idempotency, db: Session, user: User, status: int, fn):
    replay = idem.start(db, account=f"user:{user.id}")
    if replay is not None:
        return replay
    try:
        body = fn()
    except BaseException:
        idem.abandon()
        raise
    return idem.save(db, status, body)


def _after_append(project_id: str, accepted: list[dict]) -> None:
    """Wake the project's waiting pulls, then run the push hooks."""
    if accepted:
        waiters.notify(project_id)
        hooks.emit(project_id, accepted)


# --- invitations (website) -----------------------------------------------------------


@router.post("/invites/accept")
def accept_invite(
    body: AcceptIn, caller: ProjectCaller = Depends(get_any_caller), db: Session = Depends(get_db)
) -> dict:
    """Attach an invitation to the signed-in account (session + the e-mailed token)."""
    require_session(caller, "accept an invitation")
    return members.accept(db, caller.user, body.token.strip())


# --- 5.1-5.5 projects ---------------------------------------------------------------------


@router.post("", status_code=201)
def create_project(
    body: CreateIn,
    caller: ProjectCaller = Depends(get_project_caller),
    idem: Idempotency = idempotent("projects.create"),
    db: Session = Depends(get_db),
):
    return _idempotent_call(idem, db, caller.user, 201, lambda: service.create(db, caller, body.name, body.doc_version))


@router.get("")
def list_projects(
    cursor: str | None = Query(default=None, max_length=300),
    limit: int = Query(default=service.PAGE_DEFAULT, ge=1, le=service.PAGE_MAX),
    caller: ProjectCaller = Depends(get_project_caller),
    db: Session = Depends(get_db),
) -> dict:
    return service.list_projects(db, caller, cursor, limit)


@router.get("/{project_id}")
def open_project(
    project_id: str, caller: ProjectCaller = Depends(get_project_caller), db: Session = Depends(get_db)
) -> dict:
    project, member = service.open_project(db, caller, project_id)
    owner = db.get(User, project.owner_user_id)
    out = service.record(db, project, member.role, owner=owner, members=members.list_json(db, project_id))
    out["quota"] = quotas.bytes_quota(db, owner)
    return out


@router.patch("/{project_id}")
def rename_project(
    project_id: str,
    body: RenameIn,
    caller: ProjectCaller = Depends(get_project_caller),
    db: Session = Depends(get_db),
) -> dict:
    project, member = service.open_project(db, caller, project_id, "owner")
    service.rename(db, project, body.name)
    return service.record(db, project, member.role)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: str, caller: ProjectCaller = Depends(get_any_caller), db: Session = Depends(get_db)
) -> Response:
    require_session(caller)
    project, _ = service.open_project(db, caller, project_id, "owner")
    service.soft_delete(db, project)
    presence.backend().drop_project(db, project_id)
    return Response(status_code=204)


# --- 5.6, 5.7 the log ------------------------------------------------------------------------


async def _read_body(request: Request, cap: int) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > cap:
            raise ContractError("too_large", 413, "A push carries at most 16 MiB.", {"limit": cap})
    return bytes(body)


def _push(db: Session, caller: ProjectCaller, project_id: str, raw: bytes) -> tuple[dict, list[dict]]:
    project, _ = service.open_project(db, caller, project_id, "editor")
    if caller.is_device:
        quotas.require_feature(db, caller.user)
    author_id = ensure_author_id(db, caller.user)
    replica_id, parsed = ops.parse_push(raw, author_id)
    owner = db.get(User, project.owner_user_id)
    cap = quotas.limit(quotas.plan_of(db, owner), "cloud_bytes")
    return ops.push(db, project_id, replica_id, parsed, owner_id=owner.id, bytes_cap=cap)


@router.post("/{project_id}/ops")
async def push_ops(
    project_id: str,
    request: Request,
    caller: ProjectCaller = Depends(get_project_caller),
    db: Session = Depends(get_db),
) -> dict:
    # Auth ran on this session: give its connection back to the pool while a
    # slow client sends up to 16 MiB.
    await run_in_threadpool(db.rollback)
    raw = await _read_body(request, ops.MAX_PUSH_BYTES)
    answer, accepted = await run_in_threadpool(_push, db, caller, project_id, raw)
    await run_in_threadpool(_after_append, project_id, accepted)
    return answer


def _read(project_id: str, after: int, limit: int) -> dict:
    with SessionLocal() as db:
        return ops.read_after(db, project_id, after, limit)


@router.get("/{project_id}/ops")
async def pull_ops(
    project_id: str,
    after: int = 0,
    limit: int = ops.PULL_LIMIT_DEFAULT,
    wait_s: float = 0,
    caller: ProjectCaller = Depends(get_project_caller),
    db: Session = Depends(get_db),
) -> dict:
    ops.check_pull_args(after, limit, wait_s)
    await run_in_threadpool(service.open_project, db, caller, project_id)
    user_id = caller.user.id
    # Hold no connection while waiting.
    await run_in_threadpool(db.close)
    result = await run_in_threadpool(_read, project_id, after, limit)
    if result["ops"] or wait_s <= 0:
        return result
    slot = waiters.AccountSlot(user_id, get_settings().projects_max_waiting_pulls)
    waiter = waiters.Waiter(project_id)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + wait_s
    try:
        while True:
            # Registered before this read: a push after it wakes the wait below.
            result = await run_in_threadpool(_read, project_id, after, limit)
            remaining = deadline - loop.time()
            if result["ops"] or remaining <= 0:
                return result
            await waiter.wait(min(waiters.RECHECK_S, remaining))
    finally:
        waiter.close()
        slot.release()


# --- 5.8, 5.9 snapshots ----------------------------------------------------------------------


@router.post("/{project_id}/snapshots", status_code=201)
def register_snapshot(
    project_id: str,
    body: SnapshotIn,
    caller: ProjectCaller = Depends(get_project_caller),
    idem: Idempotency = idempotent("projects.snapshots"),
    db: Session = Depends(get_db),
):
    project, _ = service.open_project(db, caller, project_id, "editor")
    if caller.is_device:
        quotas.require_feature(db, caller.user)
    owner = db.get(User, project.owner_user_id)
    cap = quotas.limit(quotas.plan_of(db, owner), "cloud_bytes")

    def run() -> dict:
        return snapshots.register(
            db,
            project,
            user_id=caller.user.id,
            upload_caller=caller.upload_caller(),
            at_seq=body.at_seq,
            doc_version=body.doc_version,
            upload_id=body.upload_id.lower(),
            files=body.files.model_dump(),
            bytes_cap=cap,
        )

    return _idempotent_call(idem, db, caller.user, 201, run)


@router.get("/{project_id}/snapshots/latest")
def latest_snapshot(
    project_id: str, caller: ProjectCaller = Depends(get_project_caller), db: Session = Depends(get_db)
) -> dict:
    project, _ = service.open_project(db, caller, project_id)
    return snapshots.latest(db, project)


# --- 5.10-5.12 versions -----------------------------------------------------------------------


@router.get("/{project_id}/versions")
def list_versions(
    project_id: str, caller: ProjectCaller = Depends(get_project_caller), db: Session = Depends(get_db)
) -> dict:
    project, _ = service.open_project(db, caller, project_id)
    return versions.list_versions(db, project)


@router.post("/{project_id}/versions", status_code=201)
def create_version(
    project_id: str,
    body: VersionIn,
    caller: ProjectCaller = Depends(get_project_caller),
    idem: Idempotency = idempotent("projects.versions"),
    db: Session = Depends(get_db),
):
    project, _ = service.open_project(db, caller, project_id, "editor")
    return _idempotent_call(
        idem,
        db,
        caller.user,
        201,
        lambda: versions.create(
            db, project, user_id=caller.user.id, name=body.name, note=body.note, at_seq=body.at_seq,
            snapshot_id=body.snapshot_id.lower(),
        ),
    )


@router.post("/{project_id}/versions/{version_id}/restore", status_code=201)
def restore_version(
    project_id: str,
    version_id: str,
    # Before the caller: the body is read before auth takes a connection.
    idem: Idempotency = idempotent("projects.restore"),
    caller: ProjectCaller = Depends(get_project_caller),
    db: Session = Depends(get_db),
):
    service.open_project(db, caller, project_id, "editor")
    author_id = ensure_author_id(db, caller.user)

    def run() -> dict:
        op = versions.restore(db, project_id, version_id.lower(), author_id=author_id)
        _after_append(project_id, [op])
        return {"op": op}

    return _idempotent_call(idem, db, caller.user, 201, run)


# --- 5.13-5.16 members ------------------------------------------------------------------------


@router.get("/{project_id}/members")
def list_members(
    project_id: str, caller: ProjectCaller = Depends(get_project_caller), db: Session = Depends(get_db)
) -> dict:
    service.open_project(db, caller, project_id)
    return {"members": members.list_json(db, project_id)}


@router.post("/{project_id}/members", status_code=201)
def invite_member(
    project_id: str,
    body: InviteIn,
    caller: ProjectCaller = Depends(get_project_caller),
    idem: Idempotency = idempotent("projects.members"),
    db: Session = Depends(get_db),
):
    project, _ = service.open_project(db, caller, project_id, "owner")
    return _idempotent_call(
        idem, db, caller.user, 201, lambda: members.invite(db, project, caller.user, body.email, body.role)
    )


@router.patch("/{project_id}/members/{member_ref}")
def change_member_role(
    project_id: str,
    member_ref: str,
    body: RoleIn,
    caller: ProjectCaller = Depends(get_project_caller),
    db: Session = Depends(get_db),
) -> dict:
    service.open_project(db, caller, project_id, "owner")
    return members.change_role(db, members.find(db, project_id, member_ref.lower()), body.role)


@router.delete("/{project_id}/members/{member_ref}", status_code=204)
def remove_member(
    project_id: str,
    member_ref: str,
    caller: ProjectCaller = Depends(get_project_caller),
    db: Session = Depends(get_db),
) -> Response:
    """The owner removes anyone else; a member removes themselves (leaves)."""
    _, mine = service.open_project(db, caller, project_id)
    target = members.find(db, project_id, member_ref.lower())
    if target.user_id != caller.user.id:
        service.require_role(mine, "owner")
    members.remove(db, target)
    return Response(status_code=204)


# --- 5.17, 5.18 presence -------------------------------------------------------------------------


@router.put("/{project_id}/presence")
def heartbeat(
    project_id: str,
    body: presence.PresenceIn,
    caller: ProjectCaller = Depends(get_project_caller),
    db: Session = Depends(get_db),
) -> dict:
    service.open_project(db, caller, project_id)
    return presence.heartbeat(db, project_id, caller.user, body)


@router.get("/{project_id}/presence")
def who_is_here(
    project_id: str, caller: ProjectCaller = Depends(get_project_caller), db: Session = Depends(get_db)
) -> dict:
    service.open_project(db, caller, project_id)
    return presence.present(db, project_id)
