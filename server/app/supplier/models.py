"""Supplier portal tables (PF8). Kept out of the shared models.py like PF1's
and PF7's; registered with `Base` by `database.init_db`.

`api_keys.supplier_id` (the one column PF8 adds to an existing table) is in
`database._ADDED_COLUMNS` and on `models.ApiKey`.
"""

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ts(nullable: bool = False, **kw) -> Mapped:
    if nullable:
        return mapped_column(DateTime(timezone=True), nullable=True, **kw)
    return mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, **kw)


class SupplierApplication(Base):
    """The verification trail: what the company sent and the decision."""

    __tablename__ = "supplier_applications"

    application_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="CASCADE"), index=True, nullable=False
    )
    submitted_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # {name, legal_name, country, company_number, vat_id, website,
    #  address {line1, line2, city, postcode, country}, regions [], contact {name, email, phone}}
    fields: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # [{"key", "sha256", "bytes", "name", "uploaded_at"}]: PDFs under
    # market/suppliers/<supplier_id>/docs/<sha256>.pdf, read by admins only.
    document_keys: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # applied | verified | declined
    state: Mapped[str] = mapped_column(String(10), default="applied", index=True, nullable=False)
    decided_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decided_at: Mapped[datetime | None] = _ts(nullable=True)
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = _ts()


class FeedSource(Base):
    """A URL the platform pulls daily (contract 5.12)."""

    __tablename__ = "feed_sources"

    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="CASCADE"), primary_key=True
    )
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    # csv | json
    format: Mapped[str] = mapped_column(String(8), nullable=False)
    # upsert | replace
    mode: Mapped[str] = mapped_column(String(8), nullable=False)
    next_pull_at: Mapped[datetime] = _ts()
    last_pull_at: Mapped[datetime | None] = _ts(nullable=True)
    # queued (a run was queued) | not_modified (304) | failed
    last_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    last_feed_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    etag: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class SupplierImport(Base):
    """A portal upload: its dry run (kept 24 h) and, once applied, its run."""

    __tablename__ = "supplier_imports"

    import_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="CASCADE"), index=True, nullable=False
    )
    filename: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    # The upload as §6.4 CSV rows (an XLSX is converted at upload).
    source_key: Mapped[str] = mapped_column(String(200), nullable=False)
    # xlsx | csv | json (what was uploaded)
    format: Mapped[str] = mapped_column(String(8), nullable=False)
    mode: Mapped[str] = mapped_column(String(8), nullable=False)
    dry_run: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    feed_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = _ts()


class MarketEventDaily(Base):
    """Counts per product, region and UTC day (no people: PF8 analytics).
    `order_value` is in minor units of the region's currency."""

    __tablename__ = "market_events_daily"
    __table_args__ = (UniqueConstraint("product_id", "region", "day", name="uq_market_event_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # "" when the read named no region.
    region: Mapped[str] = mapped_column(String(8), default="", nullable=False)
    day: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    geometry_downloads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quotes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    orders: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    order_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class SupplierMemberInvite(Base):
    """An invitation by e-mail with a role (7 days); only a hash of the token."""

    __tablename__ = "supplier_member_invites"

    invite_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="CASCADE"), index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    invited_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime] = _ts()
    accepted_at: Mapped[datetime | None] = _ts(nullable=True)
    accepted_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revoked_at: Mapped[datetime | None] = _ts(nullable=True)
    created_at: Mapped[datetime] = _ts()


class ListingSubscription(Base):
    """A supplier's listing plan as paid through PF2's billing interface; the
    `supplier.listing.sync` job keeps it in step with PF2's subscription."""

    __tablename__ = "listing_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="CASCADE"), index=True, nullable=False
    )
    plan: Mapped[str] = mapped_column(String(32), nullable=False)
    # stripe | none (a plan without a fee)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    # pending (PF2 absent or no synced price) | checkout | active | past_due |
    # canceled | expired (a checkout never paid)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    current_period_end: Mapped[datetime | None] = _ts(nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The PF2 `payments.reference` of the checkout.
    payment_ref: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    detail: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
