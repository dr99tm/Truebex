"""SSO tables (PF3): one identity-provider connection per organisation, the
pending sign-ins (10 minutes, single use) and the SAML replay cache.
Registered with `Base` by `database.init_db`.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SsoConnection(Base):
    __tablename__ = "sso_connections"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), primary_key=True
    )
    # oidc | saml
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    # OIDC
    issuer: Mapped[str | None] = mapped_column(String(512), nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # Sealed with Fernet (SSO_SECRET_KEY); never returned by the API.
    client_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    # SAML (from the IdP metadata)
    idp_entity_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    idp_sso_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    idp_cert_pem: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class SsoRequest(Base):
    """A sign-in started at /auth/sso/start, finished once at the callback or ACS."""

    __tablename__ = "sso_requests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # SHA-256 of the OIDC `state` (or the SAML RelayState).
    state: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    nonce: Mapped[str | None] = mapped_column(String(64), nullable=True)
    code_verifier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # The AuthnRequest ID a SAML response must answer (InResponseTo).
    saml_request_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    next: Mapped[str] = mapped_column(String(512), default="/dashboard/", nullable=False)
    login_hint: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SsoAssertionSeen(Base):
    """SAML assertion ids already accepted (each is good for one sign-in)."""

    __tablename__ = "sso_assertions_seen"

    assertion_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
