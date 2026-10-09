"""Browser sign-in for devices with a link code (contract 5.1-5.3, RFC 8628).

The app starts a link (5.1) and gets a single-use code plus a poll secret
(stored only as SHA-256). The person opens `verify_url`, signs in on the
website, sees the device name and presses Approve or Deny (5.3). The app
polls (5.2) no faster than `interval_s` and receives a session token once.
Codes live 600 s; expired and spent rows are purged by a job.
"""

import hashlib
import math
import re
import secrets
from datetime import datetime, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError
from ..models import LinkCode, User
from ..schemas import Token
from ..security import create_access_token
from ..users import user_out
from . import clock, events

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
LIFETIME = timedelta(seconds=600)
INTERVAL_S = 5
# A poll this much early still counts (network jitter on a 5 s timer).
_POLL_SLACK_S = 1.0
_CODE = re.compile(r"^[A-HJKMNP-Z2-9]{4}-[A-HJKMNP-Z2-9]{4}$")


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def normalise_code(raw: str) -> str | None:
    """`qx7d k9mp`, `QX7DK9MP` and `QX7D-K9MP` all read as `QX7D-K9MP`."""
    if not isinstance(raw, str):
        return None
    compact = re.sub(r"[\s-]", "", raw).upper()
    if len(compact) != 8:
        return None
    code = f"{compact[:4]}-{compact[4:]}"
    return code if _CODE.match(code) else None


def _new_code() -> str:
    chars = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return f"{chars[:4]}-{chars[4:]}"


def verify_url(code: str) -> str:
    return f"{get_settings().site_url.rstrip('/')}/dashboard/link/?code={code}"


def start(
    db: Session, *, device_name: str, fingerprint: str, app_version: str, now: datetime
) -> tuple[LinkCode, str]:
    secret = secrets.token_urlsafe(32)
    code = _new_code()
    while db.get(LinkCode, code) is not None:
        code = _new_code()
    row = LinkCode(
        link_code=code,
        poll_secret_hash=hash_secret(secret),
        device_name=device_name,
        fingerprint=fingerprint,
        app_version=app_version,
        status="pending",
        created_at=now,
        expires_at=now + LIFETIME,
    )
    db.add(row)
    db.commit()
    return row, secret


def _expired() -> ContractError:
    return ContractError(
        "link_expired", 410, "This sign-in code has expired or was already used. Start again."
    )


def poll(db: Session, poll_secret: str, now: datetime) -> dict:
    row = db.scalar(select(LinkCode).where(LinkCode.poll_secret_hash == hash_secret(poll_secret)))
    if row is None or row.status == "spent" or now >= clock.aware(row.expires_at):
        raise _expired()
    if row.status == "denied":
        raise ContractError("link_denied", 403, "Sign-in was denied in the browser.")
    last = clock.aware(row.last_poll_at)
    if last is not None:
        waited = (now - last).total_seconds()
        if waited < INTERVAL_S - _POLL_SLACK_S:
            raise ContractError(
                "rate_limited",
                429,
                f"Poll every {INTERVAL_S} seconds.",
                retry_after_s=max(1, math.ceil(INTERVAL_S - waited)),
            )
    row.last_poll_at = now
    if row.status == "pending":
        db.commit()
        return {"status": "pending"}
    # Approved: hand the session over exactly once.
    user = db.get(User, row.user_id)
    row.status = "spent"
    db.commit()
    if user is None:
        raise _expired()
    token = Token(access_token=create_access_token(str(user.id)), user=user_out(user))
    return {"status": "approved", "token": token.model_dump(mode="json")}


def lookup(db: Session, code: str, now: datetime) -> LinkCode:
    row = db.get(LinkCode, code)
    if row is None or now >= clock.aware(row.expires_at):
        raise ContractError("not_found", 404, "This code is unknown or has expired.")
    return row


def decide(db: Session, code: str, user: User, approve: bool, now: datetime) -> LinkCode:
    """5.3: the signed-in website approves or denies a pending code."""
    row = lookup(db, code, now)
    wanted = "approved" if approve else "denied"
    if row.status == "pending":
        row.status = wanted
        row.user_id = user.id
        events.record(
            db,
            "link.approved" if approve else "link.denied",
            user_id=user.id,
            at=now,
            device_name=row.device_name,
            app_version=row.app_version,
        )
        db.commit()
        return row
    if row.user_id == user.id and row.status in (wanted, "spent" if approve else wanted):
        return row  # a repeated press is harmless
    raise ContractError("not_found", 404, "This code is unknown or has expired.")


def purge(db: Session, now: datetime) -> int:
    """The licence.links.purge job: drop expired and spent codes."""
    result = db.execute(
        delete(LinkCode).where(or_(LinkCode.expires_at < now, LinkCode.status == "spent"))
    )
    return result.rowcount or 0
