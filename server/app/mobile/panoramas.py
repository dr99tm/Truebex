"""A project's followed panorama sets, for its members (PF9; a MINOR proposal
for render-jobs §5).

Render jobs belong to the account that submitted them (5.2, 5.3 and 5.5 are
owner-only), but a followed set renders a shared project for everyone in it:
the phone of an editor or viewer opens the set the owner (or any member)
keeps current. Members read the sets of the project's active members — the
same state the live share page reads (`render.live.state`) — and long-poll
its `rev`. A set of someone who left the project is not served (PF6 stops it
at the next push or claim anyway).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..licence import clock
from ..projects.models import ProjectMember
from ..render import live
from ..render.models import RenderSet
from ..render.quotas import ACCOUNT_KIND


def _member_ids(db: Session, project_id: str) -> set[int]:
    return set(
        db.scalars(
            select(ProjectMember.user_id).where(
                ProjectMember.project_id == project_id,
                ProjectMember.state == "active",
                ProjectMember.user_id.is_not(None),
            )
        )
    )


def visible(db: Session, project_id: str) -> list[RenderSet]:
    """Sets with a render, of the project's active members, newest first."""
    members = _member_ids(db, project_id)
    rows = db.scalars(
        select(RenderSet)
        .where(RenderSet.project_id == project_id, RenderSet.latest_job_id.is_not(None))
        .order_by(RenderSet.active.desc(), RenderSet.updated_at.desc())
    ).all()
    return [r for r in rows if r.account_kind == ACCOUNT_KIND and r.account_id in members]


def list_json(db: Session, project_id: str, user_id: int) -> dict:
    return {
        "sets": [
            {
                "set_id": r.follow_job_id,
                "rev": r.rev,
                "at_seq": r.at_seq,
                "views": list(r.views or []),
                "following": bool(r.active),
                "mine": r.account_id == user_id,
                "updated_at": clock.rfc3339(r.updated_at),
            }
            for r in visible(db, project_id)
        ]
    }


def find(db: Session, project_id: str, set_id: str) -> RenderSet:
    row = db.get(RenderSet, set_id.lower()) if len(set_id) == 32 else None
    if row is None or row.follow_job_id not in {r.follow_job_id for r in visible(db, project_id)}:
        raise ContractError("not_found", 404, "This project has no such panorama set.")
    return row


def state(db: Session, row: RenderSet) -> dict:
    """`{rev, job_id, follow_job_id, at_seq, following, manifest}` (tiles_base filled)."""
    return live.state(db, row)
