"""Organisations, members, roles and invites (PF3).

Roles: `owner`, `admin`, `billing`, `member`. Route levels: *member* = any
role, *admin* = owner or admin, *owner* = owner. An organisation always keeps
at least one owner; only an owner grants or takes away the owner role.
Someone who is not a member gets 404 (an organisation's existence is not
disclosed); a member without the role gets 403. Every change writes an
audit event.
"""

import hashlib
import re
import secrets
import unicodedata
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import mail
from ..billing.service import is_live
from ..config import get_settings
from ..contract_http import ContractError
from ..licence import clock, devices
from ..licence.ids import uuid7_hex
from ..models import Subscription, User
from ..plans import get_plan, plan_rank
from . import audit
from .models import OrgInvite, OrgMember, Organisation, SeatAssignment

ROLES = ("owner", "admin", "billing", "member")
ROLE_NAMES = {"owner": "Owner", "admin": "Admin", "billing": "Billing", "member": "Member"}
LEVELS = {"member": set(ROLES), "admin": {"owner", "admin"}, "owner": {"owner"}}
INVITE_TTL = timedelta(days=7)
SEAT_NAMES = {"named": "named", "floating": "floating", "none": "no"}


# --- lookups --------------------------------------------------------------------


def _not_found() -> ContractError:
    return ContractError("not_found", 404, "There is no such organisation.")


def get_org(db: Session, org_id: str) -> Organisation:
    org = db.get(Organisation, org_id) if isinstance(org_id, str) and len(org_id) <= 32 else None
    if org is None or org.deleted_at is not None:
        raise _not_found()
    return org


def membership(db: Session, org_id: str, user_id: int) -> OrgMember | None:
    return db.get(OrgMember, (org_id, user_id))


def require(db: Session, org_id: str, user: User, level: str) -> tuple[Organisation, OrgMember]:
    """The organisation and the caller's membership, or 404 / 403."""
    org = get_org(db, org_id)
    member = membership(db, org.id, user.id)
    if member is None:
        raise _not_found()
    if member.role not in LEVELS[level]:
        needed = {"admin": "an owner or admin", "owner": "an owner"}.get(level, "a member")
        raise ContractError("forbidden", 403, f"Only {needed} of {org.name} can do this.")
    return org, member


def by_slug(db: Session, slug: str) -> Organisation | None:
    org = db.scalar(select(Organisation).where(Organisation.slug == slug))
    return org if org is not None and org.deleted_at is None else None


def org_subscription(db: Session, org_id: str, now: datetime | None = None) -> Subscription | None:
    """The organisation's best live subscription (its tier and seat count)."""
    best: Subscription | None = None
    for sub in db.scalars(select(Subscription).where(Subscription.organisation_id == org_id)):
        if is_live(sub, now) and (best is None or plan_rank(sub.plan) > plan_rank(best.plan)):
            best = sub
    return best


def owners_count(db: Session, org_id: str) -> int:
    return int(
        db.scalar(
            select(func.count()).select_from(OrgMember).where(
                OrgMember.org_id == org_id, OrgMember.role == "owner"
            )
        )
        or 0
    )


def _site(path: str) -> str:
    return f"{get_settings().site_url.rstrip('/')}{path}"


def _display(user: User | None) -> str:
    if user is None:
        return "Someone"
    return user.name or user.email


# --- organisations -----------------------------------------------------------------

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    slug = _SLUG_STRIP.sub("-", ascii_).strip("-")[:48].strip("-")
    return slug or "org"


def unique_slug(db: Session, name: str) -> str:
    base = slugify(name)
    slug, n = base, 1
    while db.scalar(select(Organisation.id).where(Organisation.slug == slug)) is not None:
        n += 1
        slug = f"{base}-{n}"
    return slug


def create(db: Session, user: User, name: str, now: datetime) -> tuple[Organisation, OrgMember]:
    org = Organisation(id=uuid7_hex(), name=name, slug=unique_slug(db, name), created_by=user.id, created_at=now)
    member = OrgMember(org_id=org.id, user_id=user.id, role="owner", joined_at=now)
    db.add_all([org, member])
    audit.record(db, org.id, "org.created", actor=user.id, target_kind="org", target_id=org.id, at=now, name=name)
    db.commit()
    return org, member


def rename(db: Session, org: Organisation, actor: User, name: str, now: datetime) -> Organisation:
    if name != org.name:
        audit.record(
            db, org.id, "org.renamed", actor=actor.id, target_kind="org", target_id=org.id, at=now,
            old=org.name, new=name,
        )
        org.name = name
        db.add(org)
        db.commit()
    return org


def delete_org(db: Session, org: Organisation, actor: User, now: datetime) -> None:
    sub = org_subscription(db, org.id, now)
    if sub is not None:
        raise ContractError(
            "live_subscription", 409,
            f"{org.name} has a live {get_plan(sub.plan).name} subscription. Cancel it before deleting the organisation.",
            {"plan": sub.plan},
        )
    from ..sso.models import SsoConnection
    from .models import FloatingLease, OrgDomain

    db.execute(delete(FloatingLease).where(FloatingLease.org_id == org.id))
    for model in (SeatAssignment, OrgInvite, OrgMember, OrgDomain):
        db.execute(delete(model).where(model.org_id == org.id))
    db.execute(delete(SsoConnection).where(SsoConnection.org_id == org.id))
    audit.record(db, org.id, "org.deleted", actor=actor.id, target_kind="org", target_id=org.id, at=now, name=org.name)
    org.deleted_at = now
    # Free the slug for someone else; the row stays for the audit trail.
    org.slug = f"{org.slug[:40]}--deleted-{org.id[-8:]}"
    org.sso_required = False
    db.add(org)
    db.commit()


def list_for_user(db: Session, user: User) -> list[dict]:
    rows = db.execute(
        select(Organisation, OrgMember)
        .join(OrgMember, OrgMember.org_id == Organisation.id)
        .where(OrgMember.user_id == user.id, Organisation.deleted_at.is_(None))
        .order_by(Organisation.name)
    ).all()
    seats = {
        a.org_id: a.kind
        for a in db.scalars(select(SeatAssignment).where(SeatAssignment.user_id == user.id))
    }
    return [
        {"id": org.id, "name": org.name, "slug": org.slug, "role": m.role, "seat_kind": seats.get(org.id, "none")}
        for org, m in rows
    ]


def org_json(db: Session, org: Organisation, member: OrgMember, now: datetime) -> dict:
    from . import seats as org_seats

    sub = org_subscription(db, org.id, now)
    pool = org_seats.pool(db, org, now)
    assignment = db.get(SeatAssignment, (org.id, member.user_id))
    count = int(db.scalar(select(func.count()).select_from(OrgMember).where(OrgMember.org_id == org.id)) or 0)
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "role": member.role,
        "seat_kind": assignment.kind if assignment else "none",
        "created_at": clock.rfc3339(org.created_at),
        "members": count,
        "sso_required": bool(org.sso_required),
        "subscription": None if sub is None else {
            "plan": sub.plan,
            "plan_name": get_plan(sub.plan).name,
            "seats": sub.seats or 1,
            "provider": sub.provider,
            "current_period_end": clock.rfc3339(sub.current_period_end),
        },
        "seats": {"total": pool.total, "named": pool.named_total, "floating": pool.floating_total},
        "billing_url": _site(f"/dashboard/billing/?org={org.id}"),
    }


# --- members ------------------------------------------------------------------------


def members_json(db: Session, org: Organisation) -> list[dict]:
    rows = db.execute(
        select(OrgMember, User)
        .join(User, User.id == OrgMember.user_id)
        .where(OrgMember.org_id == org.id)
        .order_by(OrgMember.joined_at)
    ).all()
    seats = {
        a.user_id: a.kind for a in db.scalars(select(SeatAssignment).where(SeatAssignment.org_id == org.id))
    }
    out = []
    for m, user in rows:
        active = devices.active(db, user.id)
        last = max((clock.aware(d.last_seen_at) for d in active), default=None)
        out.append(
            {
                "user_id": user.id,
                "email": user.email,
                "name": user.name,
                "role": m.role,
                "seat_kind": seats.get(user.id, "none"),
                "joined_at": clock.rfc3339(m.joined_at),
                "last_active_at": clock.rfc3339(last),
                "devices": len(active),
            }
        )
    return out


def _last_owner(org: Organisation) -> ContractError:
    return ContractError(
        "last_owner", 409, f"{org.name} needs at least one owner. Make someone else an owner first."
    )


def change_role(
    db: Session, org: Organisation, actor: OrgMember, user_id: int, role: str, now: datetime
) -> OrgMember:
    target = membership(db, org.id, user_id)
    if target is None:
        raise ContractError("not_found", 404, "That person is not a member of this organisation.")
    if (target.role == "owner" or role == "owner") and actor.role != "owner":
        raise ContractError("forbidden", 403, "Only an owner can give or take away the owner role.")
    if target.role == role:
        return target
    if target.role == "owner" and owners_count(db, org.id) <= 1:
        raise _last_owner(org)
    audit.record(
        db, org.id, "member.role_changed", actor=actor.user_id, target_kind="user", target_id=user_id, at=now,
        old=target.role, new=role,
    )
    target.role = role
    db.add(target)
    db.commit()
    return target


def remove_member(db: Session, org: Organisation, actor: OrgMember, user_id: int, now: datetime) -> None:
    """An admin removes someone, or a member leaves (actor == target)."""
    leaving = actor.user_id == user_id
    target = actor if leaving else membership(db, org.id, user_id)
    if target is None:
        raise ContractError("not_found", 404, "That person is not a member of this organisation.")
    if not leaving:
        if actor.role not in LEVELS["admin"]:
            raise ContractError("forbidden", 403, f"Only an owner or admin of {org.name} can remove members.")
        if target.role == "owner" and actor.role != "owner":
            raise ContractError("forbidden", 403, "Only an owner can remove an owner.")
    if target.role == "owner" and owners_count(db, org.id) <= 1:
        raise _last_owner(org)
    from .seats import end_leases

    end_leases(db, org_id=org.id, user_id=user_id, reason="member_removed", now=now)
    db.execute(delete(SeatAssignment).where(SeatAssignment.org_id == org.id, SeatAssignment.user_id == user_id))
    db.delete(target)
    audit.record(
        db, org.id, "member.left" if leaving else "member.removed", actor=actor.user_id,
        target_kind="user", target_id=user_id, at=now, role=target.role,
    )
    db.commit()
    if not leaving:
        removed = db.get(User, user_id)
        if removed is not None:
            mail.try_send(
                removed.email,
                "org_removed",
                {"org_name": org.name, "actor": _display(db.get(User, actor.user_id)), "link": _site("/dashboard/")},
            )


def add_member(
    db: Session, org: Organisation, user: User, role: str, now: datetime, *, actor: int | None, via: str
) -> OrgMember:
    """Join (invite accepted, SSO just-in-time); the caller commits."""
    member = membership(db, org.id, user.id)
    if member is not None:
        return member
    member = OrgMember(org_id=org.id, user_id=user.id, role=role, joined_at=now)
    db.add(member)
    audit.record(
        db, org.id, "member.joined", actor=actor or user.id, target_kind="user", target_id=user.id, at=now,
        role=role, via=via,
    )
    return member


# --- invites ------------------------------------------------------------------------


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def invite_status(inv: OrgInvite, now: datetime) -> str:
    if inv.accepted_at is not None:
        return "accepted"
    if inv.revoked_at is not None:
        return "revoked"
    if inv.expired_at is not None or now >= clock.aware(inv.expires_at):
        return "expired"
    return "pending"


def invite_json(db: Session, inv: OrgInvite, now: datetime) -> dict:
    inviter = db.get(User, inv.invited_by) if inv.invited_by else None
    return {
        "id": inv.id,
        "email": inv.email,
        "role": inv.role,
        "seat_kind": inv.seat_kind,
        "invited_by": inviter.email if inviter else None,
        "created_at": clock.rfc3339(inv.created_at),
        "expires_at": clock.rfc3339(inv.expires_at),
        "status": invite_status(inv, now),
    }


def list_invites(db: Session, org: Organisation, now: datetime) -> list[dict]:
    rows = db.scalars(
        select(OrgInvite).where(OrgInvite.org_id == org.id).order_by(OrgInvite.created_at.desc()).limit(200)
    )
    return [invite_json(db, inv, now) for inv in rows]


def _pending_for(db: Session, org_id: str, email: str, now: datetime) -> OrgInvite | None:
    for inv in db.scalars(select(OrgInvite).where(OrgInvite.org_id == org_id, OrgInvite.email == email)):
        if invite_status(inv, now) == "pending":
            return inv
    return None


def _send_invite(db: Session, org: Organisation, inv: OrgInvite, token: str, inviter: User) -> None:
    seat_line = {
        "named": "A named seat is waiting for you.",
        "floating": "You can use one of the organisation's shared (floating) seats.",
    }.get(inv.seat_kind, "")
    mail.try_send(
        inv.email,
        "org_invite",
        {
            "org_name": org.name,
            "inviter": _display(inviter),
            "role_name": ROLE_NAMES[inv.role],
            "seat_line": seat_line,
            "link": _site(f"/invite/?t={token}"),
            "expires": clock.rfc3339(inv.expires_at),
            "email": inv.email,
        },
    )


def create_invite(
    db: Session, org: Organisation, actor: OrgMember, *, email: str, role: str, seat: str, now: datetime
) -> OrgInvite:
    from . import seats as org_seats

    email = email.strip().lower()
    if role == "owner" and actor.role != "owner":
        raise ContractError("forbidden", 403, "Only an owner can invite another owner.")
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None and membership(db, org.id, existing.id) is not None:
        raise ContractError("already_member", 409, f"{email} is already a member of {org.name}.")
    pending = _pending_for(db, org.id, email, now)
    if pending is not None:
        raise ContractError(
            "already_invited", 409, f"{email} already has a pending invitation. Resend it instead.",
            {"invite_id": pending.id},
        )
    if seat != "none":
        org_seats.check_capacity(db, org, seat, now, pending_invites=True)
    token = secrets.token_urlsafe(32)
    inv = OrgInvite(
        id=uuid7_hex(),
        org_id=org.id,
        email=email,
        role=role,
        seat_kind=seat,
        token_hash=hash_token(token),
        invited_by=actor.user_id,
        created_at=now,
        expires_at=clock.floor_s(now) + INVITE_TTL,
    )
    db.add(inv)
    audit.record(
        db, org.id, "invite.created", actor=actor.user_id, target_kind="invite", target_id=email, at=now,
        role=role, seat=seat, invite_id=inv.id,
    )
    db.commit()
    _send_invite(db, org, inv, token, db.get(User, actor.user_id))
    return inv


def _invite_of(db: Session, org: Organisation, invite_id: str) -> OrgInvite:
    inv = db.get(OrgInvite, invite_id) if isinstance(invite_id, str) and len(invite_id) <= 32 else None
    if inv is None or inv.org_id != org.id:
        raise ContractError("not_found", 404, "There is no such invitation.")
    return inv


def revoke_invite(db: Session, org: Organisation, actor: OrgMember, invite_id: str, now: datetime) -> None:
    inv = _invite_of(db, org, invite_id)
    if inv.accepted_at is None and inv.revoked_at is None:
        inv.revoked_at = now
        db.add(inv)
        audit.record(
            db, org.id, "invite.revoked", actor=actor.user_id, target_kind="invite", target_id=inv.email, at=now,
            invite_id=inv.id,
        )
        db.commit()


def resend_invite(db: Session, org: Organisation, actor: OrgMember, invite_id: str, now: datetime) -> OrgInvite:
    """A fresh link (the old one stops working) and another 7 days."""
    inv = _invite_of(db, org, invite_id)
    if inv.accepted_at is not None or inv.revoked_at is not None:
        raise ContractError("conflict", 409, "This invitation was already accepted or revoked.")
    token = secrets.token_urlsafe(32)
    inv.token_hash = hash_token(token)
    inv.expires_at = clock.floor_s(now) + INVITE_TTL
    inv.expired_at = None
    db.add(inv)
    audit.record(
        db, org.id, "invite.resent", actor=actor.user_id, target_kind="invite", target_id=inv.email, at=now,
        invite_id=inv.id,
    )
    db.commit()
    _send_invite(db, org, inv, token, db.get(User, actor.user_id))
    return inv


def _invite_by_token(db: Session, token: str) -> OrgInvite:
    inv = db.scalar(select(OrgInvite).where(OrgInvite.token_hash == hash_token(token)))
    if inv is None:
        raise ContractError("not_found", 404, "This invitation link is not valid. Ask for a new one.")
    return inv


def _gone(detail: str) -> ContractError:
    return ContractError("invite_expired", 410, detail)


def preview_invite(db: Session, token: str, now: datetime) -> dict:
    inv = _invite_by_token(db, token)
    org = db.get(Organisation, inv.org_id)
    if org is None or org.deleted_at is not None:
        raise _gone("This organisation no longer exists.")
    return {
        "org_id": org.id,
        "org_name": org.name,
        "email": inv.email,
        "role": inv.role,
        "seat_kind": inv.seat_kind,
        "expires_at": clock.rfc3339(inv.expires_at),
        "status": invite_status(inv, now),
    }


def accept_invite(db: Session, user: User, token: str, now: datetime) -> dict:
    from . import seats as org_seats

    inv = _invite_by_token(db, token)
    org = db.get(Organisation, inv.org_id)
    if org is None or org.deleted_at is not None:
        raise _gone("This organisation no longer exists.")
    status = invite_status(inv, now)
    if status == "accepted":
        if inv.accepted_by == user.id and membership(db, org.id, user.id) is not None:
            member = membership(db, org.id, user.id)
            return {"org_id": org.id, "role": member.role, "seat_kind": org_seats.kind_of(db, org.id, user.id)}
        raise _gone("This invitation was already used.")
    if status == "revoked":
        raise _gone("This invitation was withdrawn. Ask for a new one.")
    if status == "expired":
        raise _gone("This invitation has expired (links work for 7 days). Ask for a new one.")
    if user.email.lower() != inv.email:
        raise ContractError(
            "email_mismatch", 403,
            f"This invitation is for {inv.email}. Sign in with that address to accept it.",
            {"email": inv.email},
        )
    member = add_member(db, org, user, inv.role, now, actor=inv.invited_by, via="invite")
    inv.accepted_at = now
    inv.accepted_by = user.id
    db.add(inv)
    audit.record(
        db, org.id, "invite.accepted", actor=user.id, target_kind="invite", target_id=inv.email, at=now,
        invite_id=inv.id,
    )
    db.commit()
    seat_kind = org_seats.kind_of(db, org.id, user.id)
    if inv.seat_kind != "none" and seat_kind == "none":
        try:
            seat_kind = org_seats.assign(db, org, inv.invited_by, user.id, inv.seat_kind, now)
        except ContractError:
            seat_kind = "none"  # no seat left by now: joined without one; an admin assigns later
    return {"org_id": org.id, "role": member.role, "seat_kind": seat_kind}


def expire_invites(db: Session, now: datetime) -> int:
    """The orgs.invites.expire job: mark pending invites past their 7 days."""
    rows = list(
        db.scalars(
            select(OrgInvite).where(
                OrgInvite.accepted_at.is_(None),
                OrgInvite.revoked_at.is_(None),
                OrgInvite.expired_at.is_(None),
                OrgInvite.expires_at <= now,
            )
        )
    )
    for inv in rows:
        inv.expired_at = now
        audit.record(db, inv.org_id, "invite.expired", target_kind="invite", target_id=inv.email, at=now, invite_id=inv.id)
    return len(rows)
