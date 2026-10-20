"""`/v1/projects…`: the project-log contract (5.1-5.22; comments 5.19-5.22
since PF4b, project-log 1.2.0) for API keys (PF12), and a project's followed
panorama sets (PF12a).

Every route hands the call to the contract router's own handler
(`app/routers/projects.py`; for the panorama sets PF9's `app/routers/mobile.py`)
with the key as an `api_key` caller, so shapes, roles, quotas, idempotency and
errors are the contract's. What the key adds:
its scope (`projects:read` / `projects:write`), metering and the burst limit
(`deps.api_key_auth`). Deleting stays the website's (403 `session_required`),
and operations a key pushes are `author_kind: "agent"` with the key's own
author id (`GET /v1/account` → `key.author`). A comment a key writes is the
key's owner's (their user id and name), with that member's role.
"""

import json

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ...contract_http import ContractError, contract
from ...database import get_db
from ...deps import ApiCaller
from ...idempotency import Idempotency, idempotent
from ...projects import comments, ops, service
from ...scopes import author_for_key
from .. import mobile
from .. import projects as c
from . import models as m
from .common import AnyKey, carry, doc, project_caller, scope

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[contract("project-log", 1, 2)])

Read = scope("projects:read")
Write = scope("projects:write")


# --- 5.1-5.5 ------------------------------------------------------------------------------


@router.post("", status_code=201, operation_id="projects_create", **doc("projects:write", m.Project, 201, errors=(401, 403, 409, 422, 429)))
def create_project(
    body: m.ProjectCreate,
    response: Response,
    api: ApiCaller = Write,
    idem: Idempotency = idempotent("v1.projects.create"),
    db: Session = Depends(get_db),
):
    """Create a project (5.1). The plan needs cloud projects (403 `plan_required`)."""
    return carry(c.create_project(body=body, caller=project_caller(api), idem=idem, db=db), response)


@router.get("", operation_id="projects_list", **doc("projects:read", m.ProjectList))
def list_projects(
    cursor: str | None = Query(default=None, max_length=300),
    limit: int = Query(default=service.PAGE_DEFAULT, ge=1, le=service.PAGE_MAX),
    api: ApiCaller = Read,
    db: Session = Depends(get_db),
) -> dict:
    """Projects the key's account owns or is a member of (5.2)."""
    return c.list_projects(cursor=cursor, limit=limit, caller=project_caller(api), db=db)


@router.get("/{project_id}", operation_id="projects_get", **doc("projects:read", m.ProjectDetail))
def open_project(project_id: str, api: ApiCaller = Read, db: Session = Depends(get_db)) -> dict:
    """Open a project: its record, members and the owner's storage quota (5.3)."""
    return c.open_project(project_id=project_id, caller=project_caller(api), db=db)


@router.patch("/{project_id}", operation_id="projects_update", **doc("projects:write", m.Project))
def rename_project(project_id: str, body: m.ProjectRename, api: ApiCaller = Write, db: Session = Depends(get_db)) -> dict:
    """Rename a project (5.4; owner)."""
    return c.rename_project(project_id=project_id, body=body, caller=project_caller(api), db=db)


@router.delete("/{project_id}", status_code=204, operation_id="projects_delete", **doc(None, errors=(401, 403, 429)))
def delete_project(project_id: str, api: ApiCaller = AnyKey, db: Session = Depends(get_db)) -> Response:
    """Always 403 `session_required`: projects are deleted on truebex.com only (5.5)."""
    return c.delete_project(project_id=project_id, caller=project_caller(api), db=db)


# --- 5.6, 5.7 the log ---------------------------------------------------------------------------


def _as_agent(raw: bytes, author: str) -> bytes:
    """Operations from a key are the key's: `author_kind` agent, `author` its
    id. Missing fields are filled in; different ones answer 422."""
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return raw  # parse_push answers the contract's 422
    if not isinstance(data, dict) or not isinstance(data.get("ops"), list):
        return raw
    for i, op in enumerate(data["ops"]):
        if not isinstance(op, dict):
            continue
        kind = op.setdefault("author_kind", "agent")
        who = op.setdefault("author", author)
        if kind != "agent" or not isinstance(who, str) or who.lower() != author:
            field = f"ops[{i}].author_kind" if kind != "agent" else f"ops[{i}].author"
            raise ContractError(
                "validation_failed",
                422,
                f"{field}: an API key pushes as an agent with its own author id ({author}); leave both out.",
                {"fields": [{"field": field, "in": "body", "message": "author_kind agent, author the key's id"}], "author": author},
            )
    return json.dumps(data, separators=(",", ":")).encode()


@router.post(
    "/{project_id}/ops",
    operation_id="projects_push_ops",
    openapi_extra={
        "x-truebex-scope": "projects:write",
        "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/PushRequest"}}}},
    },
    responses=doc(None, m.PushResult, errors=(401, 403, 404, 413, 422, 429))["responses"],
)
async def push_ops(project_id: str, request: Request, api: ApiCaller = Write, db: Session = Depends(get_db)) -> dict:
    """Push operations (5.6): ≤ 200 a request, ≤ 16 MiB. A conflict is a per-operation result, not an error."""
    caller = project_caller(api)
    author = author_for_key(api.key.id)
    await run_in_threadpool(db.rollback)
    raw = _as_agent(await c._read_body(request, ops.MAX_PUSH_BYTES), author)
    answer, accepted = await run_in_threadpool(c._push, db, caller, project_id, raw)
    await run_in_threadpool(c._after_append, project_id, accepted)
    return answer


@router.get("/{project_id}/ops", operation_id="projects_pull_ops", **doc("projects:read", m.PullResult))
async def pull_ops(
    project_id: str,
    after: int = 0,
    limit: int = ops.PULL_LIMIT_DEFAULT,
    wait_s: float = 0,
    api: ApiCaller = Read,
    db: Session = Depends(get_db),
) -> dict:
    """Operations after a sequence number (5.7); `wait_s` ≤ 25 long-polls until the next push."""
    return await c.pull_ops(project_id=project_id, after=after, limit=limit, wait_s=wait_s, caller=project_caller(api), db=db)


# --- 5.8, 5.9 snapshots ---------------------------------------------------------------------------


@router.post("/{project_id}/snapshots", status_code=201, operation_id="projects_create_snapshot", **doc("projects:write", m.Snapshot, 201, errors=(401, 403, 404, 409, 422, 429)))
def register_snapshot(
    project_id: str,
    body: m.SnapshotRequest,
    response: Response,
    api: ApiCaller = Write,
    idem: Idempotency = idempotent("v1.projects.snapshots"),
    db: Session = Depends(get_db),
):
    """Register a snapshot uploaded through /v1/uploads (purpose `snapshot`) at a sequence number (5.8)."""
    return carry(c.register_snapshot(project_id=project_id, body=body, caller=project_caller(api), idem=idem, db=db), response)


@router.get("/{project_id}/snapshots/latest", operation_id="projects_latest_snapshot", **doc("projects:read", m.Snapshot))
def latest_snapshot(
    project_id: str,
    snapshot_id: str | None = Query(default=None, alias="id", description="A snapshot id: that snapshot instead of the newest (1.1.0)"),
    api: ApiCaller = Read,
    db: Session = Depends(get_db),
) -> dict:
    """The newest snapshot with download URLs valid 15 minutes (5.9); 404 before the first.
    With `id`, that snapshot (a restore operation's `restore.snapshot_id`), or 404."""
    return c.latest_snapshot(project_id=project_id, snapshot_id=snapshot_id, caller=project_caller(api), db=db)


# --- 5.10-5.12 versions ----------------------------------------------------------------------------


@router.get("/{project_id}/versions", operation_id="projects_list_versions", **doc("projects:read", m.VersionList))
def list_versions(project_id: str, api: ApiCaller = Read, db: Session = Depends(get_db)) -> dict:
    """Named versions (5.10)."""
    return c.list_versions(project_id=project_id, caller=project_caller(api), db=db)


@router.post("/{project_id}/versions", status_code=201, operation_id="projects_create_version", **doc("projects:write", m.Version, 201))
def create_version(
    project_id: str,
    body: m.VersionRequest,
    response: Response,
    api: ApiCaller = Write,
    idem: Idempotency = idempotent("v1.projects.versions"),
    db: Session = Depends(get_db),
):
    """Name a version at a snapshot that sits exactly at `at_seq` (5.11)."""
    return carry(c.create_version(project_id=project_id, body=body, caller=project_caller(api), idem=idem, db=db), response)


@router.post("/{project_id}/versions/{version_id}/restore", status_code=201, operation_id="projects_restore_version", **doc("projects:write", m.RestoreResult, 201))
def restore_version(
    project_id: str,
    version_id: str,
    response: Response,
    idem: Idempotency = idempotent("v1.projects.restore"),
    api: ApiCaller = Write,
    db: Session = Depends(get_db),
):
    """Append a restore operation: every replica then loads the version (5.12)."""
    return carry(c.restore_version(project_id=project_id, version_id=version_id, idem=idem, caller=project_caller(api), db=db), response)


# --- 5.13-5.16 members ---------------------------------------------------------------------------


@router.get("/{project_id}/members", operation_id="projects_list_members", **doc("projects:read", m.MemberList))
def list_members(project_id: str, api: ApiCaller = Read, db: Session = Depends(get_db)) -> dict:
    """Members and invitations (5.13)."""
    return c.list_members(project_id=project_id, caller=project_caller(api), db=db)


@router.post("/{project_id}/members", status_code=201, operation_id="projects_invite_member", **doc("projects:write", m.Member, 201, errors=(401, 403, 404, 409, 422, 429)))
def invite_member(
    project_id: str,
    body: m.MemberInvite,
    response: Response,
    api: ApiCaller = Write,
    idem: Idempotency = idempotent("v1.projects.members"),
    db: Session = Depends(get_db),
):
    """Invite someone by e-mail with a role (5.14; owner). Truebex sends the e-mail."""
    return carry(c.invite_member(project_id=project_id, body=body, caller=project_caller(api), idem=idem, db=db), response)


@router.patch("/{project_id}/members/{member_ref}", operation_id="projects_update_member", **doc("projects:write", m.Member))
def change_member_role(project_id: str, member_ref: str, body: m.MemberRole, api: ApiCaller = Write, db: Session = Depends(get_db)) -> dict:
    """Change a member's role (5.15; owner). `member_ref` is a user id or an invitation id."""
    return c.change_member_role(project_id=project_id, member_ref=member_ref, body=body, caller=project_caller(api), db=db)


@router.delete("/{project_id}/members/{member_ref}", status_code=204, operation_id="projects_remove_member", **doc("projects:write"))
def remove_member(project_id: str, member_ref: str, api: ApiCaller = Write, db: Session = Depends(get_db)) -> Response:
    """Remove a member (owner), or leave (the key's own account) (5.16)."""
    return c.remove_member(project_id=project_id, member_ref=member_ref, caller=project_caller(api), db=db)


# --- 5.17, 5.18 presence ---------------------------------------------------------------------------


@router.put("/{project_id}/presence", operation_id="projects_heartbeat", **doc("projects:write", m.HeartbeatResult))
def heartbeat(project_id: str, body: m.PresenceHeartbeat, api: ApiCaller = Write, db: Session = Depends(get_db)) -> dict:
    """Presence heartbeat (5.17): every 10-30 s while open; `leaving` removes it. `comments_rev` says when to fetch comments."""
    return c.heartbeat(project_id=project_id, body=body, caller=project_caller(api), db=db)


@router.get("/{project_id}/presence", operation_id="projects_presence", **doc("projects:read", m.PresenceList))
def who_is_here(project_id: str, api: ApiCaller = Read, db: Session = Depends(get_db)) -> dict:
    """Who is in the project now (5.18), and the comment revision."""
    return c.who_is_here(project_id=project_id, caller=project_caller(api), db=db)


# --- 5.19-5.22 comments (project-log 1.2.0, PF4b) -------------------------------------------------


@router.get("/{project_id}/comments", operation_id="projects_list_comments", **doc("projects:read", m.CommentList))
def list_comments(
    project_id: str,
    after_rev: int = Query(default=0, ge=0, description="The `rev` (or `comments_rev`) last read; 0 for every comment"),
    state: comments.Filter = Query(default="all", description="open, resolved or all; deleted comments come back with every filter"),
    api: ApiCaller = Read,
    db: Session = Depends(get_db),
) -> dict:
    """Comments created, edited, resolved, reopened or deleted after `after_rev`, oldest change first (5.19).
    A deleted comment comes back once, with state `deleted` and empty text."""
    return c.list_comments(project_id=project_id, after_rev=after_rev, state=state, caller=project_caller(api), db=db)


@router.post("/{project_id}/comments", status_code=201, operation_id="projects_create_comment", **doc("projects:write", m.Comment, 201, errors=(401, 403, 404, 409, 422, 429)))
def create_comment(
    project_id: str,
    body: m.CommentCreate,
    response: Response,
    api: ApiCaller = Write,
    idem: Idempotency = idempotent("v1.projects.comments"),
    db: Session = Depends(get_db),
):
    """Pin a comment on an entity or a view, or reply to one (5.20); any member, a viewer included.
    The comment is the key owner's."""
    return carry(c.create_comment(project_id=project_id, body=body, caller=project_caller(api), idem=idem, db=db), response)


@router.patch("/{project_id}/comments/{comment_id}", operation_id="projects_update_comment", **doc("projects:write", m.Comment, errors=(401, 403, 404, 422, 429)))
def update_comment(project_id: str, comment_id: str, body: m.CommentUpdate, api: ApiCaller = Write, db: Session = Depends(get_db)) -> dict:
    """Edit a comment's text (its author), or resolve or reopen it (its author, an editor or the owner) (5.21)."""
    return c.update_comment(project_id=project_id, comment_id=comment_id, body=body, caller=project_caller(api), db=db)


@router.delete("/{project_id}/comments/{comment_id}", status_code=204, operation_id="projects_delete_comment", **doc("projects:write", errors=(401, 403, 404, 429)))
def delete_comment(project_id: str, comment_id: str, api: ApiCaller = Write, db: Session = Depends(get_db)) -> Response:
    """Delete a comment (its author or the owner) (5.22)."""
    return c.delete_comment(project_id=project_id, comment_id=comment_id, caller=project_caller(api), db=db)


# --- followed panorama sets (PF12a: PF9's member reads, a render-jobs §5 MINOR proposal) -------------


@router.get("/{project_id}/panoramas", operation_id="projects_panoramas_list", **doc("projects:read", m.PanoramaSetList, errors=(401, 403, 404, 429)))
def list_panoramas(project_id: str, response: Response, api: ApiCaller = Read, db: Session = Depends(get_db)) -> dict:
    """The project's followed panorama sets, kept current by its members' accounts (any role); never cached."""
    return mobile.list_panoramas(project_id=project_id, response=response, caller=project_caller(api), db=db)


@router.get("/{project_id}/panoramas/{set_id}", operation_id="projects_panoramas_get", **doc("projects:read", m.PanoramaSetState))
async def panorama_set(
    project_id: str,
    set_id: str,
    response: Response,
    rev: int | None = None,
    wait_s: float = 0,
    api: ApiCaller = Read,
    db: Session = Depends(get_db),
) -> dict:
    """A followed set's newest tile manifest; with `rev` and `wait_s` ≤ 25 it waits until the set's `rev` passes `rev`."""
    return await mobile.panorama_set(
        project_id=project_id, set_id=set_id, response=response, rev=rev, wait_s=wait_s, caller=project_caller(api), db=db
    )
