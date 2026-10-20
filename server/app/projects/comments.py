"""Comments (contract project-log 1.2.0: 5.19-5.22, §6.6; PF4b, the server
side of CL2's comment pins and threads).

The people in a project pin a comment on an entity or a view, reply, edit,
resolve, reopen and delete. Roles (§5): every member reads and comments, a
viewer included (a review role needs it); the text is the author's alone; the
state (`open` / `resolved`) the author's, an editor's or the owner's; deleting
the author's or the owner's. Non-members get the project's 404.

Every 5.20, 5.21 and 5.22 bumps the project's comment revision
(`projects.comments_rev`) by exactly one, in the same transaction as the change
and under the project row's lock (the UPDATE-first pattern of
`ops.lock_project`): two people commenting at once on Postgres queue on that
row, so revisions are contiguous and never repeat (`uq_project_comments_rev`
backs it). A comment row holds the revision of its latest change, so 5.19
(`after_rev`) returns each changed comment once, in its latest state, oldest
change first. A deleted comment stays as a tombstone (state `deleted`, its text
erased): it goes out once, whatever the `state` filter, and never again after
its revision.

Where the contract is silent this follows the app's stub (`SyncStub.cpp`,
"5.19 - 5.22 comments"): the text is trimmed and must then hold 1-4000
characters; a reply takes its parent's anchor and hangs under the thread's
root; a deleted or unknown parent is 422; a deleted comment answers 404 to
5.21 and 5.22; resolving sets `resolved_by` / `resolved_at` and reopening
clears them; a text edit sets `edited_at`.

Comments are platform data: never part of a document, a snapshot or the log.
A member who leaves keeps their comments (shown with their name); a deleted
project takes its comments with it (`jobs.purge_project`).
"""

import copy
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..licence import clock
from ..licence.ids import uuid7_hex
from ..models import User
from . import quotas
from .models import Project, ProjectComment, ProjectMember
from .service import RANK, display_name, is_hex32, not_found

TEXT_MAX = 4000
STATES = ("open", "resolved")
FEATURE = "collab.live"
# 5.19's `state`: a filter; tombstones go out with every one of them.
Filter = Literal["open", "resolved", "all"]
ANCHOR_TEXT = (
    "§6.6: {entity, point_mm, view}. A root comment pins an entity (32 hex) or a view "
    "({storey, eye_mm, yaw_deg, pitch_deg}); a reply takes its parent's anchor."
)


class CommentIn(BaseModel):
    """5.20: a comment pinned on an entity or a view, or a reply (`parent_id`)."""

    model_config = ConfigDict(extra="ignore")

    parent_id: str | None = Field(default=None, description="32 hex: reply to this comment (the reply hangs under its thread's root)")
    text: str = Field(description="1-4000 characters once trimmed")
    anchor: dict[str, Any] | None = Field(default=None, description=ANCHOR_TEXT)


class CommentPatchIn(BaseModel):
    """5.21: new text (the author only) and/or a new state (the author, an editor or the owner)."""

    model_config = ConfigDict(extra="ignore")

    text: str | None = Field(default=None, description="1-4000 characters once trimmed; the author only")
    state: str | None = Field(default=None, description="open or resolved; the author, an editor or the owner")


def _invalid(field: str, message: str) -> ContractError:
    return ContractError(
        "validation_failed",
        422,
        f"{field}: {message}",
        {"fields": [{"field": field, "in": "body", "message": message}]},
    )


def _forbidden(detail: str, role: str, needed: str) -> ContractError:
    return ContractError("forbidden", 403, detail, {"role": role, "needed": needed})


def require_collab(db: Session, user: User) -> None:
    """5.20 from the app: the caller's plan needs live collaboration (§7, 1.2.0)."""
    plan = quotas.plan_of(db, user)
    if FEATURE not in plan.features:
        raise ContractError(
            "plan_required",
            403,
            "Comments in the app come with live collaboration, part of a paid plan or the trial. "
            "Upgrade to comment; you can still read every comment.",
            {"feature": FEATURE, "plan": plan.id},
        )


# --- validation -----------------------------------------------------------------------------


def clean_text(raw: str | None) -> str:
    text = (raw or "").strip()
    if not text or len(text) > TEXT_MAX:
        raise _invalid("text", f"1 to {TEXT_MAX} characters")
    return text


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _vec3(value: object, field: str) -> list:
    if not (isinstance(value, list) and len(value) == 3 and all(_number(v) for v in value)):
        raise _invalid(field, "three finite numbers (doc millimetres)")
    return list(value)


def _angle(value: object, field: str) -> int | float:
    if value is None:
        return 0
    if not _number(value):
        raise _invalid(field, "a finite number of degrees")
    return value


def _id_or_null(value: object, field: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and is_hex32(value.lower()):
        return value.lower()
    raise _invalid(field, "32 hex characters or null")


def parse_anchor(raw: object) -> dict:
    """§6.6's anchor, every key present: an entity pin (with an optional point)
    or a view pin (the camera when the comment was made). Numbers stay as sent."""
    if not isinstance(raw, dict):
        raise _invalid("anchor", "pin the comment on an entity or a view")
    entity = _id_or_null(raw.get("entity"), "anchor.entity")
    point = raw.get("point_mm")
    point = None if point is None else _vec3(point, "anchor.point_mm")
    view = raw.get("view")
    if view is not None:
        if not isinstance(view, dict):
            raise _invalid("anchor.view", "an object: storey, eye_mm, yaw_deg, pitch_deg")
        view = {
            "storey": _id_or_null(view.get("storey"), "anchor.view.storey"),
            "eye_mm": _vec3(view.get("eye_mm"), "anchor.view.eye_mm"),
            "yaw_deg": _angle(view.get("yaw_deg"), "anchor.view.yaw_deg"),
            "pitch_deg": _angle(view.get("pitch_deg"), "anchor.view.pitch_deg"),
        }
    if entity is None and view is None:
        raise _invalid("anchor", "pin the comment on an entity (anchor.entity) or a view (anchor.view)")
    return {"entity": entity, "point_mm": point, "view": view}


# --- the revision ------------------------------------------------------------------------------


def current_rev(db: Session, project_id: str) -> int:
    """The project's comment revision: 5.19's `rev`, 5.17 / 5.18's `comments_rev`."""
    return int(db.scalar(select(Project.comments_rev).where(Project.project_id == project_id)) or 0)


def _next_rev(db: Session, project_id: str) -> int:
    """Begin the write with the project row locked and take the next revision.

    The UPDATE comes first (as in `ops.lock_project`): it takes SQLite's write
    lock or the Postgres row lock until the caller commits or rolls back, and a
    second writer's UPDATE waits, then adds one to the committed value. So only
    the holder numbers, and a revision is visible only with its change."""
    res = db.execute(
        update(Project)
        .where(Project.project_id == project_id, Project.deleted_at.is_(None))
        .values(comments_rev=func.coalesce(Project.comments_rev, 0) + 1)
        .execution_options(synchronize_session=False)
    )
    if res.rowcount != 1:
        raise not_found()
    return int(db.scalar(select(Project.comments_rev).where(Project.project_id == project_id)))


def _live(db: Session, project_id: str, comment_id: str) -> ProjectComment | None:
    """A comment of this project that is not deleted, read fresh (under the lock)."""
    if not is_hex32(comment_id):
        return None
    return db.scalar(
        select(ProjectComment)
        .where(
            ProjectComment.project_id == project_id,
            ProjectComment.comment_id == comment_id,
            ProjectComment.state != "deleted",
        )
        .execution_options(populate_existing=True)
    )


# --- the comment ----------------------------------------------------------------------------------


def comment_json(row: ProjectComment, users: dict[int, User]) -> dict:
    """§6.6, field for field, in the app's order."""
    author = users.get(row.author_user_id)
    return {
        "comment_id": row.comment_id,
        "parent_id": row.parent_id,
        "author": {"user_id": row.author_user_id, "name": display_name(author) if author else row.author_name},
        "created_at": clock.rfc3339(row.created_at),
        "edited_at": clock.rfc3339(row.edited_at),
        "text": "" if row.state == "deleted" else row.text,
        "state": row.state,
        "resolved_by": row.resolved_by,
        "resolved_at": clock.rfc3339(row.resolved_at),
        "anchor": row.anchor,
    }


def _authors(db: Session, rows: list[ProjectComment]) -> dict[int, User]:
    ids = {r.author_user_id for r in rows}
    return {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}


# --- 5.19 -------------------------------------------------------------------------------------------


def list_after(db: Session, project_id: str, after_rev: int, state: str = "all") -> dict:
    """Every comment changed after `after_rev`, oldest change first."""
    # The revision first: a change is committed with its revision, so every
    # change at or below it is visible to the read below; a later one waits for
    # the next fetch instead of being skipped by a `rev` that already counts it.
    rev = current_rev(db, project_id)
    q = select(ProjectComment).where(
        ProjectComment.project_id == project_id, ProjectComment.rev > after_rev, ProjectComment.rev <= rev
    )
    if state != "all":
        q = q.where(or_(ProjectComment.state == state, ProjectComment.state == "deleted"))
    rows = list(db.scalars(q.order_by(ProjectComment.rev)))
    users = _authors(db, rows)
    return {"comments": [comment_json(r, users) for r in rows], "rev": rev}


# --- 5.20 -------------------------------------------------------------------------------------------


def create(db: Session, project: Project, user: User, body: CommentIn) -> dict:
    text = clean_text(body.text)
    parent_ref = (body.parent_id or "").strip().lower()
    # A reply's own anchor is ignored (it takes its parent's); a root needs one.
    anchor = None if parent_ref else parse_anchor(body.anchor)
    if parent_ref and not is_hex32(parent_ref):
        raise _invalid("parent_id", "no such comment")
    try:
        rev = _next_rev(db, project.project_id)
        parent_id = None
        if parent_ref:
            parent = _live(db, project.project_id, parent_ref)
            if parent is None:
                raise _invalid("parent_id", "no such comment")
            anchor = copy.deepcopy(parent.anchor)
            parent_id = parent.parent_id or parent.comment_id
        row = ProjectComment(
            comment_id=uuid7_hex(),
            project_id=project.project_id,
            parent_id=parent_id,
            author_user_id=user.id,
            author_name=display_name(user),
            created_at=clock.now(),
            text=text,
            state="open",
            anchor=anchor,
            rev=rev,
        )
        db.add(row)
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return comment_json(row, {user.id: user})


# --- 5.21, 5.22 -------------------------------------------------------------------------------------


def update_comment(db: Session, project: Project, member: ProjectMember, comment_id: str, body: CommentPatchIn) -> dict:
    """Edit the text (the author), resolve or reopen (the author, an editor or the owner)."""
    ref = (comment_id or "").lower()
    has_text, has_state = body.text is not None, body.state is not None
    try:
        rev = _next_rev(db, project.project_id)  # the lock first: the comment is read under it
        row = _live(db, project.project_id, ref)
        if row is None:
            raise not_found("comment")
        mine = row.author_user_id == member.user_id
        if has_text and not mine:
            raise _forbidden("Only the comment's author can change its text.", member.role, "author")
        if has_state and not mine and RANK[member.role] < RANK["editor"]:
            raise _forbidden("A viewer resolves or reopens only their own comments.", member.role, "editor")
        if not has_text and not has_state:
            raise _invalid("text", "send text, state or both")
        text = clean_text(body.text) if has_text else None
        if has_state and body.state not in STATES:
            raise _invalid("state", "open or resolved")
        now = clock.now()
        if has_text:
            row.text = text
            row.edited_at = now
        if has_state:
            row.state = body.state
            row.resolved_by = member.user_id if body.state == "resolved" else None
            row.resolved_at = now if body.state == "resolved" else None
        row.rev = rev
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return comment_json(row, _authors(db, [row]))


def delete_comment(db: Session, project: Project, member: ProjectMember, comment_id: str) -> None:
    """Leave a tombstone (state `deleted`, the text erased): the author or the owner."""
    ref = (comment_id or "").lower()
    try:
        rev = _next_rev(db, project.project_id)
        row = _live(db, project.project_id, ref)
        if row is None:
            raise not_found("comment")
        if row.author_user_id != member.user_id and member.role != "owner":
            raise _forbidden("Only the comment's author or the project's owner can delete it.", member.role, "owner")
        row.state = "deleted"
        row.text = ""
        row.rev = rev
        db.commit()
    except BaseException:
        db.rollback()
        raise
