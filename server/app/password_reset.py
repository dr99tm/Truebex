"""Password reset by e-mail: POST /auth/password/forgot and /auth/password/reset
(routers/auth.py).

* `request_reset`: for an address with an account, outside a domain whose
  organisation requires SSO, a one-time link
  `{SITE_URL}/reset-password/#token=<43 characters>`. The token rides in the
  fragment, which browsers never send to a server, a log or an analytics
  beacon. Stored only as SHA-256, valid 30 minutes, single use. The route
  answers 202 whatever happens, and mails in the background, so neither the
  answer nor its timing tells whether the address has an account.
* `reset`: an unused, unexpired token of the same account and address sets the
  password (Google-only accounts may set one this way: the link went to their
  own inbox), marks the address verified (`users.email_verified_at`) and spends
  every open link of the account. A domain that requires SSO is refused with
  `sso_required`, also when it started requiring it after the mail was sent.
* Sessions: a session token (JWT) issued before the reset stays valid until it
  expires (ACCESS_TOKEN_EXPIRE_MINUTES, 24 hours). Tokens are stateless and
  cannot be revoked one by one; rotating SECRET_KEY signs everyone out.
* `purge`: the auth.password_resets.purge job drops spent and expired links.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import status
from sqlalchemy import DateTime, ForeignKey, String, delete, or_, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from .config import get_settings
from .contract_http import ContractError
from .database import Base, SessionLocal
from .licence import clock
from .models import User
from .security import hash_password
from .sso import service as sso
from .tasks import periodic

LIFETIME = timedelta(minutes=30)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    # The address the link was mailed to: a reset is refused if it changed since.
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def reset_url(token: str) -> str:
    return f"{get_settings().site_url.rstrip('/')}/reset-password/#token={token}"


def request_reset(db: Session, email: str, now: datetime) -> dict | None:
    """Store a link for `email`'s account and return the mail's values, or None
    when there is nothing to send (no account, or SSO is required)."""
    user = db.scalar(select(User).where(User.email == email))
    if user is None or sso.required_org(db, email) is not None:
        return None
    token = secrets.token_urlsafe(32)
    expires = now + LIFETIME
    db.add(
        PasswordResetToken(
            token_hash=hash_token(token), user_id=user.id, email=email, created_at=now, expires_at=expires
        )
    )
    db.commit()
    return {
        "link": reset_url(token),
        "minutes": int(LIFETIME.total_seconds() // 60),
        "expires": clock.floor_s(expires).strftime("%H:%M UTC"),
        "email": email,
        "action": "set a new password" if user.hashed_password else "set a password",
    }


def _invalid() -> ContractError:
    return ContractError(
        "reset_link_invalid", 410, "This reset link has expired or was already used. Ask for a new one."
    )


def reset(db: Session, token: str, password: str, now: datetime) -> User:
    row = db.get(PasswordResetToken, hash_token(token or ""))
    if row is None or row.used_at is not None or now >= clock.aware(row.expires_at):
        raise _invalid()
    user = db.get(User, row.user_id)
    if user is None or user.email != row.email:
        raise _invalid()
    required = sso.required_org(db, user.email)
    if required is not None:
        raise sso.use_sso(required, status.HTTP_403_FORBIDDEN)
    # Spend it exactly once, even against a parallel request with the same link.
    spent = db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.token_hash == row.token_hash, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    if spent.rowcount != 1:
        db.rollback()
        raise _invalid()
    # Every other open link of the account goes too.
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    user.hashed_password = hash_password(password)
    user.email_verified_at = now
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def purge(db: Session, now: datetime) -> int:
    return db.execute(
        delete(PasswordResetToken).where(
            or_(PasswordResetToken.used_at.is_not(None), PasswordResetToken.expires_at < now)
        )
    ).rowcount or 0


@periodic("auth.password_resets.purge", 600)
def purge_job(now: datetime) -> int:
    with SessionLocal() as db:
        n = purge(db, now)
        db.commit()
        return n
