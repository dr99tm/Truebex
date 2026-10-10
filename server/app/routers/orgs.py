"""Organisations, members, invites, seats, usage per member and the audit log
(PF3). Session auth; roles gate routes (*member* = any role, *admin* = owner
or admin, *owner* = owner). Errors use the shared envelope with a `code`
(`last_owner`, `no_seat_left`, `already_member`, `email_mismatch`, …).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from ..contract_http import enveloped
from ..database import get_db
from ..deps import get_current_user
from ..licence import clock
from ..models import User
from ..orgs import audit, seats, service, usage
from ..orgs.schemas import InviteCreate, InviteToken, OrgCreate, OrgRename, RoleChange, SeatChange, SeatSettings

router = APIRouter(tags=["organisations"], dependencies=[enveloped()])


def _now() -> datetime:
    return clock.now()


# --- organisations ------------------------------------------------------------------


@router.post("/orgs", status_code=status.HTTP_201_CREATED)
def create_org(body: OrgCreate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    org, member = service.create(db, current, body.name, _now())
    return {"id": org.id, "slug": org.slug, "name": org.name, "role": member.role}


@router.get("/orgs")
def list_orgs(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return service.list_for_user(db, current)


@router.get("/orgs/{org_id}")
def get_org(org_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    org, member = service.require(db, org_id, current, "member")
    return service.org_json(db, org, member, _now())


@router.patch("/orgs/{org_id}")
def rename_org(
    org_id: str, body: OrgRename, current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    org, member = service.require(db, org_id, current, "admin")
    service.rename(db, org, current, body.name, _now())
    return service.org_json(db, org, member, _now())


@router.delete("/orgs/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_org(org_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    org, _ = service.require(db, org_id, current, "owner")
    service.delete_org(db, org, current, _now())
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- members -------------------------------------------------------------------------


@router.get("/orgs/{org_id}/members")
def list_members(org_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    org, _ = service.require(db, org_id, current, "member")
    return service.members_json(db, org)


@router.patch("/orgs/{org_id}/members/{user_id}")
def change_role(
    org_id: str,
    user_id: int,
    body: RoleChange,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    org, actor = service.require(db, org_id, current, "admin")
    service.change_role(db, org, actor, user_id, body.role, _now())
    return next(m for m in service.members_json(db, org) if m["user_id"] == user_id)


@router.delete("/orgs/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    org_id: str, user_id: int, current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    """An admin removes a member; anyone removes themselves (leave)."""
    org, actor = service.require(db, org_id, current, "member")
    service.remove_member(db, org, actor, user_id, _now())
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- invites -------------------------------------------------------------------------


@router.post("/orgs/{org_id}/invites", status_code=status.HTTP_201_CREATED)
def create_invite(
    org_id: str, body: InviteCreate, current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    org, actor = service.require(db, org_id, current, "admin")
    inv = service.create_invite(db, org, actor, email=body.email, role=body.role, seat=body.seat, now=_now())
    return service.invite_json(db, inv, _now())


@router.get("/orgs/{org_id}/invites")
def list_invites(org_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    org, _ = service.require(db, org_id, current, "admin")
    return service.list_invites(db, org, _now())


@router.post("/orgs/{org_id}/invites/{invite_id}/resend")
def resend_invite(
    org_id: str, invite_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    org, actor = service.require(db, org_id, current, "admin")
    inv = service.resend_invite(db, org, actor, invite_id, _now())
    return service.invite_json(db, inv, _now())


@router.delete("/orgs/{org_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invite(
    org_id: str, invite_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    org, actor = service.require(db, org_id, current, "admin")
    service.revoke_invite(db, org, actor, invite_id, _now())
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/invites/preview")
def preview_invite(body: InviteToken, db: Session = Depends(get_db)) -> dict:
    """What /invite/ shows before signing in (the token is the credential)."""
    return service.preview_invite(db, body.token, _now())


@router.post("/invites/accept")
def accept_invite(body: InviteToken, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return service.accept_invite(db, current, body.token, _now())


# --- seats ---------------------------------------------------------------------------


@router.get("/orgs/{org_id}/seats")
def get_seats(org_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    org, _ = service.require(db, org_id, current, "admin")
    return seats.seats_json(db, org, _now())


# Declared before /seats/{user_id} so "settings" is never read as a user id.
@router.put("/orgs/{org_id}/seats/settings")
def seat_settings(
    org_id: str, body: SeatSettings, current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    org, _ = service.require(db, org_id, current, "admin")
    seats.set_floating(db, org, current.id, body.floating, _now())
    return seats.seats_json(db, org, _now())


@router.put("/orgs/{org_id}/seats/{user_id}")
def assign_seat(
    org_id: str,
    user_id: int,
    body: SeatChange,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    org, _ = service.require(db, org_id, current, "admin")
    kind = seats.assign(db, org, current.id, user_id, body.kind, _now())
    return {"user_id": user_id, "seat_kind": kind}


# --- usage and audit ----------------------------------------------------------------------


@router.get("/orgs/{org_id}/usage")
def org_usage(
    org_id: str,
    month: str | None = Query(default=None, max_length=7),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    org, _ = service.require(db, org_id, current, "admin")
    return usage.per_member(db, org, month, _now())["members"]


@router.get("/orgs/{org_id}/audit")
def org_audit(
    org_id: str,
    cursor: str | None = Query(default=None, max_length=512),
    kind: str | None = Query(default=None, max_length=48, pattern=r"^[a-z_.]+$"),
    format: str | None = Query(default=None, pattern=r"^(json|csv)$"),  # noqa: A002 - the query name
    limit: int = Query(default=audit.PAGE, ge=1, le=200),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org, _ = service.require(db, org_id, current, "admin")
    now = _now()
    if format == "csv":
        rows = audit.all_events(db, org.id, kind=kind, now=now)
        audit.record(db, org.id, "audit.exported", actor=current.id, target_kind="org", target_id=org.id, at=now,
                     rows=len(rows), filter=kind)
        db.commit()
        name = f"{org.slug}-audit-{now.strftime('%Y-%m-%d')}.csv"
        return Response(
            content=audit.to_csv(rows),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"},
        )
    events, nxt = audit.events(
        db, org.id, kind=kind, cursor=audit.Cursor.decode(cursor) if cursor else None, limit=limit, now=now
    )
    return {"events": events, "next": nxt}
