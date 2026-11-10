"""One-time e-mail codes and the verifications they buy (the Desk's sign-in and
sign-up gates), on the pattern of `licence/links.py`: a hashed secret, a
lifetime, a purge job.

* `send_code`: always makes a code and mails it, whether or not the address has
  an account, so the answer never tells. A new code replaces the address's
  earlier ones.
* `check_code`: 5 tries per code (`secrets.compare_digest`, as SSO's
  break-glass codes); the right code is spent and buys a verification id
  (single use, 15 minutes).
* `find_verification` / `spend_verification`: what /register takes.
* `purge`: the support.codes.purge job drops spent and expired rows.

Neither the code nor the verification id is ever logged.
"""

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from .. import mail
from ..config import get_settings
from ..contract_http import ContractError
from ..licence import clock
from ..licence.ids import uuid7_hex
from ..models import User
from .models import SupportEmailCode, SupportVerification

CODE_LIFETIME = timedelta(minutes=10)
MAX_ATTEMPTS = 5
VERIFICATION_LIFETIME = timedelta(minutes=15)
_DIGITS = re.compile(r"^\d{6}$")


def _key() -> bytes:
    return hmac.new(get_settings().secret_key.encode("utf-8"), b"truebex-support-codes/1", hashlib.sha256).digest()


def code_hash(row_id: str, code: str) -> str:
    """HMAC-SHA256 under a key derived from SECRET_KEY, bound to the row: a
    copy of the table alone cannot be searched for six-digit codes."""
    return hmac.new(_key(), f"{row_id}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def normalise_code(raw: str) -> str | None:
    """`123 456`, `123-456` and `123456` all read as `123456`."""
    compact = re.sub(r"[\s-]", "", raw or "")
    return compact if _DIGITS.match(compact) else None


def send_code(db: Session, email: str, contact_hash: str | None, now: datetime) -> None:
    """Make, store (hashed) and mail a code for `email`. A mail outage is
    logged by `mail.try_send`, never raised: the answer is the same either way."""
    db.execute(
        update(SupportEmailCode)
        .where(SupportEmailCode.email == email, SupportEmailCode.used_at.is_(None))
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    code = new_code()
    row_id = uuid7_hex()
    expires = now + CODE_LIFETIME
    db.add(
        SupportEmailCode(
            id=row_id,
            email=email,
            code_hash=code_hash(row_id, code),
            contact_hash=contact_hash,
            attempts=0,
            created_at=now,
            expires_at=expires,
        )
    )
    db.commit()
    mail.try_send(
        email,
        "support_code",
        {
            "code": code,
            "minutes": int(CODE_LIFETIME.total_seconds() // 60),
            "expires": clock.floor_s(expires).strftime("%H:%M UTC"),
            "email": email,
        },
    )


def _code_expired() -> ContractError:
    return ContractError(
        "code_expired", 410, "This code has expired or was already used. Ask for a new one."
    )


def check_code(db: Session, email: str, code: str, contact_hash: str | None, now: datetime) -> str:
    """Spend the address's current code when `code` matches; returns a new
    verification id. A wrong code costs one of its 5 tries (401 `invalid_code`
    with `data.attempts_left`); a spent, replaced, exhausted or expired code is
    410 `code_expired`."""
    row = db.scalar(
        select(SupportEmailCode)
        .where(SupportEmailCode.email == email, SupportEmailCode.used_at.is_(None))
        .order_by(SupportEmailCode.created_at.desc(), SupportEmailCode.id.desc())
        .limit(1)
    )
    if row is None or now >= clock.aware(row.expires_at) or row.attempts >= MAX_ATTEMPTS:
        raise _code_expired()
    given = normalise_code(code)
    if given is None or not secrets.compare_digest(code_hash(row.id, given), row.code_hash):
        db.execute(
            update(SupportEmailCode)
            .where(SupportEmailCode.id == row.id, SupportEmailCode.used_at.is_(None))
            .values(attempts=SupportEmailCode.attempts + 1)
            .execution_options(synchronize_session=False)
        )
        db.commit()
        db.refresh(row)
        left = max(0, MAX_ATTEMPTS - row.attempts)
        if left == 0 and row.used_at is None:
            row.used_at = now  # out of tries: the code is dead
            db.add(row)
            db.commit()
        raise ContractError(
            "invalid_code", 401, "That code is not right. Check the latest e-mail and try again.",
            {"attempts_left": left},
        )
    # Spend it exactly once, even against a parallel request with the same code.
    spent = db.execute(
        update(SupportEmailCode)
        .where(SupportEmailCode.id == row.id, SupportEmailCode.used_at.is_(None))
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    if spent.rowcount != 1:
        db.rollback()
        raise _code_expired()
    verification_id = secrets.token_urlsafe(32)
    db.add(
        SupportVerification(
            id_hash=hash_secret(verification_id),
            email=email,
            contact_hash=contact_hash,
            created_at=now,
            expires_at=now + VERIFICATION_LIFETIME,
        )
    )
    db.commit()
    return verification_id


def mark_verified(db: Session, user: User, now: datetime) -> None:
    if user.email_verified_at is None:
        user.email_verified_at = now
        db.add(user)
        db.commit()


def _verification_expired() -> ContractError:
    return ContractError(
        "verification_expired",
        410,
        "This e-mail verification has expired or was already used. Verify the address again.",
    )


def find_verification(db: Session, verification_id: str, now: datetime) -> SupportVerification:
    row = db.get(SupportVerification, hash_secret(verification_id or ""))
    if row is None or row.used_at is not None or now >= clock.aware(row.expires_at):
        raise _verification_expired()
    return row


def spend_verification(db: Session, row: SupportVerification, now: datetime) -> None:
    spent = db.execute(
        update(SupportVerification)
        .where(SupportVerification.id_hash == row.id_hash, SupportVerification.used_at.is_(None))
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    if spent.rowcount != 1:
        db.rollback()
        raise _verification_expired()
    db.commit()


def purge(db: Session, now: datetime) -> int:
    """The support.codes.purge job: spent and expired codes and verifications."""
    gone = db.execute(
        delete(SupportEmailCode).where(
            or_(SupportEmailCode.used_at.is_not(None), SupportEmailCode.expires_at < now)
        )
    ).rowcount or 0
    gone += db.execute(
        delete(SupportVerification).where(
            or_(SupportVerification.used_at.is_not(None), SupportVerification.expires_at < now)
        )
    ).rowcount or 0
    return gone
