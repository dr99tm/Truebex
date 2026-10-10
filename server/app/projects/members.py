"""Members and invitations (contract 5.13-5.16; acceptance on the website).

An invitation is a member row in state `invited` with `user_id` null and a
256-bit token, stored hashed, e-mailed as `/invite/project/?t=…`. It attaches
to whoever accepts it signed in with the token: password accounts have no
e-mail verification (server/app/routers/auth.py), so a matching address alone
never grants access. Until then the owner names it by `invite_id` (a
member's `user_id` in the path of 5.15 and 5.16 may be either).
"""

import hashlib
import logging
import re
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError
from ..licence import clock
from ..mail import send_mail
from ..models import User
from . import quotas
from .models import Project, ProjectMember
from .service import display_name, is_hex32, not_found, record

log = logging.getLogger("truebex.projects.members")

INVITE_ROLES = ("editor", "viewer")
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
ROLE_WORDS = {"editor": "an editor", "viewer": "a viewer", "owner": "the owner"}


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def member_json(db: Session, m: ProjectMember, users: dict[int, User] | None = None) -> dict:
    user = None
    if m.user_id is not None:
        user = (users or {}).get(m.user_id) or db.get(User, m.user_id)
    return {
        "user_id": m.user_id,
        "invite_id": m.invite_id if m.state == "invited" else None,
        "email": user.email if user else m.email,
        "name": display_name(user) if user else None,
        "role": m.role,
        "state": m.state,
        "invited_at": clock.rfc3339(m.invited_at),
        "accepted_at": clock.rfc3339(m.accepted_at),
    }


def rows(db: Session, project_id: str) -> list[ProjectMember]:
    order = {"owner": 0, "editor": 1, "viewer": 2}
    found = db.scalars(select(ProjectMember).where(ProjectMember.project_id == project_id)).all()
    return sorted(found, key=lambda m: (m.state != "active", order.get(m.role, 3), m.email))


def list_json(db: Session, project_id: str) -> list[dict]:
    found = rows(db, project_id)
    ids = {m.user_id for m in found if m.user_id is not None}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}
    return [member_json(db, m, users) for m in found]


def _role(value: str, field: str = "role") -> str:
    if value not in INVITE_ROLES:
        raise ContractError(
            "validation_failed", 422, f"{field}: editor or viewer.",
            {"fields": [{"field": field, "in": "body", "message": "editor or viewer"}]},
        )
    return value


def invite(db: Session, project: Project, inviter: User, email: str, role: str) -> dict:
    email = (email or "").strip().lower()
    if not _EMAIL.match(email) or len(email) > 320:
        raise ContractError(
            "validation_failed", 422, "email: an e-mail address.",
            {"fields": [{"field": "email", "in": "body", "message": "an e-mail address"}]},
        )
    role = _role(role)
    quotas.require_feature(db, db.get(User, project.owner_user_id))
    existing = db.scalars(select(ProjectMember).where(ProjectMember.project_id == project.project_id)).all()
    account = db.scalar(select(User).where(User.email == email))
    for m in existing:
        if m.email.lower() == email or (account is not None and m.user_id == account.id):
            raise ContractError(
                "already_member", 409, f"{email} is already on this project.", {"state": m.state, "role": m.role}
            )
    quotas.check_members(db, db.get(User, project.owner_user_id), len(existing))
    token = secrets.token_urlsafe(32)
    now = clock.now()
    member = ProjectMember(
        project_id=project.project_id,
        user_id=None,
        email=email,
        role=role,
        state="invited",
        invite_id=secrets.token_hex(16),
        invite_token_hash=token_hash(token),
        invited_by=inviter.id,
        invited_at=now,
    )
    link = f"{get_settings().site_url.rstrip('/')}/invite/project/?t={token}"
    # Mail first: if it cannot leave, nothing is stored and a retry (same
    # Idempotency-Key) invites afresh instead of meeting 409 already_member.
    try:
        send_mail(
            email,
            "project_invite",
            {
                "inviter": display_name(inviter),
                "inviter_email": inviter.email,
                "project": project.name,
                "role": role,
                "role_words": ROLE_WORDS[role],
                "link": link,
            },
            reply_to=inviter.email,
        )
    except Exception as exc:  # noqa: BLE001 - the relay's own errors vary
        log.exception("project invitation mail to %s failed", email)
        raise ContractError(
            "unavailable", 503, "The invitation email could not be sent. Try again in a minute.", retry_after_s=60
        ) from exc
    db.add(member)
    db.commit()
    return member_json(db, member)


def find(db: Session, project_id: str, ref: str) -> ProjectMember:
    """A member by user id, or a pending invitation by invite id."""
    member = None
    if ref.isascii() and ref.isdigit() and len(ref) < 20:
        member = db.scalar(
            select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == int(ref))
        )
    elif is_hex32(ref):
        member = db.scalar(
            select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.invite_id == ref)
        )
    if member is None:
        raise not_found("member")
    return member


def change_role(db: Session, member: ProjectMember, role: str) -> dict:
    role = _role(role)
    if member.role == "owner":
        raise ContractError(
            "validation_failed", 422, "The owner's role cannot change.",
            {"fields": [{"field": "role", "in": "body", "message": "the owner stays the owner"}]},
        )
    member.role = role
    db.commit()
    return member_json(db, member)


def remove(db: Session, member: ProjectMember) -> None:
    if member.role == "owner":
        raise ContractError(
            "owner_cannot_leave", 409, "The owner cannot leave the project. Delete it on truebex.com instead."
        )
    db.delete(member)
    db.commit()


def accept(db: Session, user: User, token: str) -> dict:
    member = db.scalar(select(ProjectMember).where(ProjectMember.invite_token_hash == token_hash(token or "")))
    project = db.get(Project, member.project_id) if member is not None else None
    if member is None or member.state != "invited" or project is None or project.deleted_at is not None:
        raise ContractError("not_found", 404, "This invitation is unknown or was already used.")
    mine = db.scalar(
        select(ProjectMember).where(ProjectMember.project_id == project.project_id, ProjectMember.user_id == user.id)
    )
    if mine is not None:
        raise ContractError(
            "already_member", 409, "You are already on this project.", {"role": mine.role, "project_id": project.project_id}
        )
    member.user_id = user.id
    member.email = user.email
    member.state = "active"
    member.invite_token_hash = None
    member.accepted_at = clock.now()
    db.commit()
    return {"project": record(db, project, member.role), "member": member_json(db, member)}
