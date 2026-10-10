"""The supplier's team (PF8 Scope 8): members with roles by invitation, and
supplier-scoped API keys for feeds.

An invitation is an e-mailed link with a token (only its SHA-256 is kept),
valid 7 days, accepted by a signed-in account with the invited address. A
key made here carries `supplier_id`: it feeds that supplier's catalogue
(contract 5.11–5.13) and is refused by the developer API.
"""

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError
from ..market.catalogue import add_member
from ..market.common import aware, new_id, not_found, now, rfc3339
from ..market.models import Supplier, SupplierMember
from ..models import ApiKey, User
from ..security import generate_api_key
from . import notify
from .common import ROLE_NAMES, Member, conflict
from .models import SupplierMemberInvite

INVITE_TTL = timedelta(days=7)
MAX_KEYS = 5


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _owners(db: Session, supplier: Supplier) -> int:
    return db.scalar(
        select(func.count()).select_from(SupplierMember).where(
            SupplierMember.supplier_id == supplier.supplier_id, SupplierMember.role == "owner"
        )
    ) or 0


def key_json(k: ApiKey, email: str | None = None) -> dict:
    return {
        "id": k.id,
        "name": k.name,
        "prefix": k.prefix,
        "created_by": email,
        "created_at": rfc3339(k.created_at),
        "last_used_at": rfc3339(k.last_used_at),
        "revoked_at": rfc3339(k.revoked_at),
    }


def team_json(db: Session, supplier: Supplier) -> dict:
    members = db.execute(
        select(SupplierMember, User)
        .join(User, User.id == SupplierMember.user_id)
        .where(SupplierMember.supplier_id == supplier.supplier_id)
        .order_by(SupplierMember.id)
    ).tuples()
    invites = db.scalars(
        select(SupplierMemberInvite)
        .where(
            SupplierMemberInvite.supplier_id == supplier.supplier_id,
            SupplierMemberInvite.accepted_at.is_(None),
            SupplierMemberInvite.revoked_at.is_(None),
        )
        .order_by(SupplierMemberInvite.created_at.desc())
    )
    keys = db.execute(
        select(ApiKey, User.email)
        .join(User, User.id == ApiKey.user_id)
        .where(ApiKey.supplier_id == supplier.supplier_id)
        .order_by(ApiKey.revoked_at.is_not(None), ApiKey.created_at.desc())
    ).tuples()
    at = now()
    return {
        "members": [
            {"user_id": u.id, "email": u.email, "name": u.name, "role": m.role, "since": rfc3339(m.created_at)}
            for m, u in members
        ],
        "invites": [
            {
                "invite_id": i.invite_id,
                "email": i.email,
                "role": i.role,
                "expires_at": rfc3339(i.expires_at),
                "expired": aware(i.expires_at) < at,
            }
            for i in invites
        ],
        "keys": [key_json(k, email) for k, email in keys],
    }


def invite(db: Session, m: Member, email: str, role: str) -> dict:
    email = email.strip()
    existing = db.scalar(
        select(SupplierMember)
        .join(User, User.id == SupplierMember.user_id)
        .where(SupplierMember.supplier_id == m.supplier.supplier_id, func.lower(User.email) == email.lower())
    )
    if existing is not None:
        raise conflict(f"{email} is already a member.", "already_member")
    token = secrets.token_urlsafe(32)
    at = now()
    row = SupplierMemberInvite(
        invite_id=new_id(),
        supplier_id=m.supplier.supplier_id,
        email=email,
        role=role,
        token_hash=_hash(token),
        invited_by=m.user.id,
        expires_at=at + INVITE_TTL,
        created_at=at,
    )
    db.add(row)
    db.commit()
    link = f"{get_settings().site_url.rstrip('/')}/supplier/join/?token={token}"
    notify.send(
        email,
        "supplier_member_invite",
        {
            "inviter": m.user.name or m.user.email,
            "supplier_name": m.supplier.name,
            "role_name": ROLE_NAMES.get(role, role),
            "link": link,
            "expires": row.expires_at.strftime("%d %b %Y"),
            "email": email,
        },
    )
    return {"invite_id": row.invite_id, "email": email, "role": role, "expires_at": rfc3339(row.expires_at)}


def accept(db: Session, user: User, token: str) -> dict:
    row = db.scalar(select(SupplierMemberInvite).where(SupplierMemberInvite.token_hash == _hash(token)))
    if row is None or row.revoked_at is not None:
        raise not_found("That invitation")
    if row.accepted_at is not None:
        if row.accepted_by == user.id:
            return {"supplier_id": row.supplier_id, "role": row.role}
        raise ContractError("invite_used", 410, "This invitation was used already.")
    if aware(row.expires_at) < now():
        raise ContractError("invite_expired", 410, "This invitation has expired. Ask for a new one.")
    if row.email.lower() != user.email.lower():
        raise ContractError(
            "wrong_account", 403, f"This invitation is for {row.email}. Sign in with that address to accept it."
        )
    supplier = db.get(Supplier, row.supplier_id)
    if supplier is None:
        raise not_found("That supplier")
    current = db.scalar(
        select(SupplierMember).where(SupplierMember.supplier_id == supplier.supplier_id, SupplierMember.user_id == user.id)
    )
    if current is None or current.role != "owner":  # never demote an owner by an invitation
        add_member(db, supplier, user, row.role)
    row.accepted_at, row.accepted_by = now(), user.id
    db.add(row)
    db.commit()
    return {"supplier_id": supplier.supplier_id, "role": row.role, "name": supplier.name}


def revoke_invite(db: Session, m: Member, invite_id: str) -> None:
    row = db.get(SupplierMemberInvite, invite_id) if isinstance(invite_id, str) else None
    if row is None or row.supplier_id != m.supplier.supplier_id:
        raise not_found("That invitation")
    if row.revoked_at is None and row.accepted_at is None:
        row.revoked_at = now()
        db.add(row)
        db.commit()


def _membership(db: Session, m: Member, user_id: int) -> SupplierMember:
    row = db.scalar(
        select(SupplierMember).where(SupplierMember.supplier_id == m.supplier.supplier_id, SupplierMember.user_id == user_id)
    )
    if row is None:
        raise not_found("That member")
    return row


def set_role(db: Session, m: Member, user_id: int, role: str) -> None:
    row = _membership(db, m, user_id)
    if row.role == "owner" and role != "owner" and _owners(db, m.supplier) <= 1:
        raise conflict("A supplier keeps at least one owner.", "last_owner")
    row.role = role
    db.add(row)
    if role not in ("owner", "catalogue"):
        _revoke_keys(db, m.supplier, user_id)
    db.commit()


def remove(db: Session, m: Member, user_id: int) -> None:
    row = _membership(db, m, user_id)
    if row.role == "owner" and _owners(db, m.supplier) <= 1:
        raise conflict("A supplier keeps at least one owner.", "last_owner")
    db.delete(row)
    _revoke_keys(db, m.supplier, user_id)
    db.commit()


def _revoke_keys(db: Session, supplier: Supplier, user_id: int) -> None:
    """A member who leaves (or can no longer feed the catalogue) loses the
    supplier keys they made."""
    at = now()
    for k in db.scalars(
        select(ApiKey).where(ApiKey.supplier_id == supplier.supplier_id, ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None))
    ):
        k.revoked_at = at
        db.add(k)


def create_key(db: Session, m: Member, name: str) -> dict:
    active = db.scalar(
        select(func.count()).select_from(ApiKey).where(ApiKey.supplier_id == m.supplier.supplier_id, ApiKey.revoked_at.is_(None))
    ) or 0
    if active >= MAX_KEYS:
        raise conflict(f"A supplier has at most {MAX_KEYS} active keys. Revoke one first.", "too_many_keys")
    full, prefix, digest = generate_api_key()
    key = ApiKey(user_id=m.user.id, name=name.strip(), prefix=prefix, key_hash=digest, supplier_id=m.supplier.supplier_id)
    db.add(key)
    db.commit()
    db.refresh(key)
    return {**key_json(key, m.user.email), "key": full}


def revoke_key(db: Session, m: Member, key_id: int) -> dict:
    key = db.get(ApiKey, key_id)
    if key is None or key.supplier_id != m.supplier.supplier_id:
        raise not_found("That key")
    if key.revoked_at is None:
        key.revoked_at = now()
        db.add(key)
        db.commit()
    return key_json(key)
