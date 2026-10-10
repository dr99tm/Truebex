"""Marketplace tables (PF7, contract marketplace-api). Kept out of the shared
models.py like PF1's; registered with `Base` by `database.init_db`.

Money is always an integer of minor units with its ISO 4217 code and the
currency's exponent (contract §6.3); no column holds a float amount.

The text index `market_search_fts` (SQLite FTS5) is not a mapped table: it is
created and dropped with the metadata by the DDL events at the bottom, so
`create_all` / `drop_all` keep it in step with the products.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DDL,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ts(nullable: bool = False, **kw) -> Mapped:
    if nullable:
        return mapped_column(DateTime(timezone=True), nullable=True, **kw)
    return mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, **kw)


# --- Suppliers ---------------------------------------------------------------------


class Supplier(Base):
    """A company that sells through the marketplace (verified by an admin)."""

    __tablename__ = "suppliers"

    supplier_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # ISO 3166-1 alpha-2 of the business.
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    company_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    vat_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    website: Mapped[str | None] = mapped_column(String(300), nullable=True)
    logo_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Where leads and orders go (PF8 sends the e-mails).
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # applied | verified | suspended
    status: Mapped[str] = mapped_column(String(16), default="applied", index=True, nullable=False)
    status_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    verified_at: Mapped[datetime | None] = _ts(nullable=True)
    # None = the listing plan's rate (listing_plans.json).
    commission_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    listing_plan: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Stripe Connect Express account; payouts_ready once Stripe says it can
    # receive transfers. Without both the supplier is quote-only.
    connect_account_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    connect_ready: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # The supplier's Stripe customer for commission and listing-fee invoices (PF2).
    billing_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class SupplierMember(Base):
    """A person who works for a supplier. API keys of `owner` and `catalogue`
    members feed the catalogue (PF8's feed endpoints)."""

    __tablename__ = "supplier_members"
    __table_args__ = (UniqueConstraint("supplier_id", "user_id", name="uq_supplier_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # owner | catalogue | orders | viewer
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = _ts()


class SupplierRegion(Base):
    """The header of a supplier's regional price list."""

    __tablename__ = "supplier_regions"
    __table_args__ = (UniqueConstraint("supplier_id", "region", name="uq_supplier_region"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="CASCADE"), index=True, nullable=False
    )
    region: Mapped[str] = mapped_column(String(8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    default_delivery_fee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_days_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_days_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# --- Reference data ------------------------------------------------------------------


class MarketCategory(Base):
    """A category rooted on the app's taxonomy (contract §6.2)."""

    __tablename__ = "market_categories"

    path: Mapped[str] = mapped_column(String(160), primary_key=True)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    # The deepest prefix the app's taxonomy knows.
    app_path: Mapped[str] = mapped_column(String(160), nullable=False)
    parent_path: Mapped[str | None] = mapped_column(String(160), nullable=True)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MarketRegion(Base):
    __tablename__ = "market_regions"

    # ISO 3166-1 alpha-2, optionally with a subdivision (US-CA).
    region: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exponent: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_name: Mapped[str] = mapped_column(String(16), nullable=False)
    tax_rate_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    prices_include_tax: Mapped[bool] = mapped_column(Boolean, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


# --- Products --------------------------------------------------------------------------


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("supplier_id", "sku", name="uq_product_supplier_sku"),)

    product_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="CASCADE"), index=True, nullable=False
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # object | material | finish | theme
    kind: Mapped[str] = mapped_column(String(16), default="object", nullable=False)
    category: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    brand: Mapped[str | None] = mapped_column(String(70), nullable=True)
    # ["uniclass:Pr_40_50_12_81", …] or None when the feed sent none.
    classification: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # SHA-256 of each stored image (market/images/<sha>.jpg), the first is
    # the thumbnail; in the order the feed listed them.
    images: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # A theme's products: [{"supplier_id", "sku", "variant_id"}].
    includes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # draft | pending_review | approved | rejected | hidden | withdrawn
    status: Mapped[str] = mapped_column(String(20), default="pending_review", index=True, nullable=False)
    # What `hidden` replaced (a later feed that lists the product restores it).
    prev_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rating_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    approved_at: Mapped[datetime | None] = _ts(nullable=True)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (UniqueConstraint("product_id", "variant_id", name="uq_variant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.product_id", ondelete="CASCADE"), index=True, nullable=False
    )
    variant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gtin: Mapped[str | None] = mapped_column(String(14), nullable=True)
    options: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # [X width, Y height, Z depth] in whole millimetres, or None.
    dims_mm: Mapped[list | None] = mapped_column(JSON, nullable=True)
    materials: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # {"asset": {id, name, rev, kind}, "format", "sha256", "bytes", "storage_key"}
    geometry: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Where the geometry and images came from (a feed that repeats the same
    # URLs does not fetch them again).
    geometry_src: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    images: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    images_src: Mapped[str | None] = mapped_column(Text, nullable=True)
    # active | discontinued | hidden
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class VariantPrice(Base):
    """A variant's price in a region. Integers only (contract §6.3)."""

    __tablename__ = "variant_prices"
    __table_args__ = (UniqueConstraint("product_id", "variant_id", "region", name="uq_variant_price"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.product_id", ondelete="CASCADE"), index=True, nullable=False
    )
    variant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    region: Mapped[str] = mapped_column(String(8), index=True, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exponent: Mapped[int] = mapped_column(Integer, nullable=False)
    includes_tax: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tax_rate_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_fee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_days_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_days_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # feed | manual
    source: Mapped[str] = mapped_column(String(8), default="feed", nullable=False)
    feed_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    updated_at: Mapped[datetime] = _ts()


class VariantAvailability(Base):
    __tablename__ = "variant_availability"
    __table_args__ = (
        UniqueConstraint("product_id", "variant_id", "region", name="uq_variant_availability"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.product_id", ondelete="CASCADE"), index=True, nullable=False
    )
    variant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    region: Mapped[str] = mapped_column(String(8), nullable=False)
    # in_stock | low_stock | made_to_order | out_of_stock | discontinued
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(8), default="feed", nullable=False)
    # Not updated for 7 days (market.availability.stale): unknown in ranking.
    stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = _ts()


class ProductEmbedding(Base):
    """An image embedding for the picture search (float32 little-endian)."""

    __tablename__ = "product_embeddings"
    __table_args__ = (UniqueConstraint("product_id", "model", name="uq_product_embedding"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.product_id", ondelete="CASCADE"), index=True, nullable=False
    )
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    # The image it was made from (re-embedded when the thumbnail changes).
    image_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    vector: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = _ts()


# --- Orders and requests for quote -------------------------------------------------------


class MarketOrder(Base):
    """An order (`kind` order) or a request for quote (`kind` quote)."""

    __tablename__ = "market_orders"

    order_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    device_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # order | quote
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    # order: awaiting_payment | paid | accepted | shipped | delivered | rejected | cancelled
    # quote: submitted | quoted | accepted | expired | cancelled
    state: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    # platform (paid on the checkout page) | offline (an accepted quote the
    # supplier invoices itself while payments are off)
    payment: Mapped[str] = mapped_column(String(8), default="platform", nullable=False)
    region: Mapped[str] = mapped_column(String(8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exponent: Mapped[int] = mapped_column(Integer, nullable=False)
    project: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    project_uid: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    contact: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    delivery: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    subtotal: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivery_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tax_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checkout_session: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    payment_intent: Mapped[str | None] = mapped_column(String(128), nullable=True)
    paid_at: Mapped[datetime | None] = _ts(nullable=True)
    # An order made by accepting a quote names it; the quote names the order.
    quote_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    accepted_order_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # A quote expires 30 days after it was sent.
    expires_at: Mapped[datetime | None] = _ts(nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancelled_at: Mapped[datetime | None] = _ts(nullable=True)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class MarketOrderSupplier(Base):
    """One supplier's part of an order, or its lead for a request."""

    __tablename__ = "market_order_suppliers"
    __table_args__ = (UniqueConstraint("order_id", "supplier_id", name="uq_order_supplier"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("market_orders.order_id", ondelete="CASCADE"), index=True, nullable=False
    )
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="CASCADE"), index=True, nullable=False
    )
    # order: pending | accepted | rejected | shipped | delivered | cancelled
    # quote: submitted | quoted | accepted | declined | expired | cancelled
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    lines: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    subtotal: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivery: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Tax contained in (or added to) subtotal + delivery.
    tax: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivery_days_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_days_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commission_bp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commission: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transfer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transfer_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    refund_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    quote_valid_until: Mapped[datetime | None] = _ts(nullable=True)
    quoted_at: Mapped[datetime | None] = _ts(nullable=True)
    accepted_at: Mapped[datetime | None] = _ts(nullable=True)
    shipped_at: Mapped[datetime | None] = _ts(nullable=True)
    delivered_at: Mapped[datetime | None] = _ts(nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class MarketOrderLine(Base):
    """A line with the unit price the server charged (the snapshot)."""

    __tablename__ = "market_order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("market_orders.order_id", ondelete="CASCADE"), index=True, nullable=False
    )
    supplier_id: Mapped[str] = mapped_column(String(32), nullable=False)
    product_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    variant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    includes_tax: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tax_rate_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    price_at: Mapped[datetime] = _ts()
    # Set when the supplier quotes (a request) or the quote was accepted.
    quoted_unit_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_fee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_days_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_days_max: Mapped[int | None] = mapped_column(Integer, nullable=True)


# --- Commissions, statements, reviews, feed runs -------------------------------------


class Commission(Base):
    __tablename__ = "commissions"
    __table_args__ = (UniqueConstraint("order_id", "supplier_id", name="uq_commission"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    rate_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    # Goods value excluding tax and delivery (GD1 §4.2).
    base: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exponent: Mapped[int] = mapped_column(Integer, nullable=False)
    # accrued (deducted from the transfer) | invoiced (on a statement's
    # invoice) | paid | void (refunded)
    state: Mapped[str] = mapped_column(String(10), default="accrued", nullable=False)
    statement_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    invoice_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = _ts()


class CommissionStatement(Base):
    """A supplier's monthly statement: commissions plus its listing fee."""

    __tablename__ = "commission_statements"
    __table_args__ = (
        UniqueConstraint("supplier_id", "month", "currency", name="uq_commission_statement"),
    )

    statement_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    supplier_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # YYYY-MM (UTC) the statement covers.
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exponent: Mapped[int] = mapped_column(Integer, nullable=False)
    commission_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    listing_fee: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    orders: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # pending (no invoice yet: PF2 absent or no billing customer) | invoiced
    state: Mapped[str] = mapped_column(String(10), default="pending", nullable=False)
    invoice_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = _ts()


class ProductReview(Base):
    __tablename__ = "product_reviews"
    __table_args__ = (UniqueConstraint("product_id", "user_id", name="uq_product_review"),)

    review_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.product_id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    order_id: Mapped[str] = mapped_column(String(32), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(String(2000), default="", nullable=False)
    # Shown with the review: the buyer's first name, never the e-mail.
    author: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    # pending | published | hidden
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True, nullable=False)
    created_at: Mapped[datetime] = _ts()
    moderated_at: Mapped[datetime | None] = _ts(nullable=True)


class FeedRun(Base):
    """One run of the feed importer (written by PF7's engine; PF8 owns the
    feed endpoints and the portal)."""

    __tablename__ = "feed_runs"

    feed_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="CASCADE"), index=True, nullable=False
    )
    # csv | json
    format: Mapped[str] = mapped_column(String(8), nullable=False)
    # upsert | replace
    mode: Mapped[str] = mapped_column(String(8), nullable=False)
    # queued | running | done | failed
    state: Mapped[str] = mapped_column(String(8), default="queued", nullable=False)
    # upload | pull | admin | portal
    source: Mapped[str] = mapped_column(String(8), default="upload", nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unchanged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hidden: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    warnings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    report_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = _ts()
    started_at: Mapped[datetime | None] = _ts(nullable=True)
    finished_at: Mapped[datetime | None] = _ts(nullable=True)


# --- The text index (SQLite FTS5; Postgres full-text after PF14) ----------------------

FTS_TABLE = "market_search_fts"

event.listen(
    Base.metadata,
    "after_create",
    DDL(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} USING fts5("
        "product_id UNINDEXED, name, body, tokenize = 'unicode61 remove_diacritics 2')"
    ).execute_if(dialect="sqlite"),
)
event.listen(
    Base.metadata,
    "before_drop",
    DDL(f"DROP TABLE IF EXISTS {FTS_TABLE}").execute_if(dialect="sqlite"),
)
