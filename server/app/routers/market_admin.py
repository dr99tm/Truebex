"""Marketplace admin (users.is_admin): verify suppliers, review products,
moderate reviews, see orders and act for a supplier until PF8's inbox
exists, commissions and statements, feed runs, categories.

Kept beside routers/admin.py (PF1's releases) so parallel features do not
edit one file; the prefix is /admin/market.
"""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError, enveloped
from ..database import get_db
from ..deps import require_admin
from ..market import catalogue, checkout, commissions, hooks, importer, listing, orders, reviews, search
from ..market.common import invalid, is_hex32, not_found, now
from ..market.models import (
    Commission,
    CommissionStatement,
    FeedRun,
    MarketOrder,
    Product,
    ProductReview,
    Supplier,
)
from ..market.schemas import (
    CategoryIn,
    MemberIn,
    ReasonIn,
    SupplierActionIn,
    SupplierIn,
    SupplierPatch,
    SupplierQuoteIn,
)
from ..market.taxonomy import active_regions
from ..models import User

router = APIRouter(prefix="/admin/market", tags=["admin"], dependencies=[enveloped(), Depends(require_admin)])

MAX_FEED_UPLOAD = importer.MAX_BYTES


def _supplier(db: Session, supplier_id: str) -> Supplier:
    supplier = db.get(Supplier, supplier_id) if is_hex32(supplier_id) else None
    if supplier is None:
        raise not_found("That supplier")
    return supplier


def _product(db: Session, product_id: str) -> Product:
    product = db.get(Product, product_id) if is_hex32(product_id) else None
    if product is None:
        raise not_found("That product")
    return product


def _order(db: Session, order_id: str) -> MarketOrder:
    order = db.get(MarketOrder, order_id) if is_hex32(order_id) else None
    if order is None:
        raise not_found("That order")
    return order


def _regions(db: Session, codes: list[str]) -> dict:
    known = active_regions(db)
    out = {}
    for code in codes:
        if code.upper() not in known:
            raise invalid("regions", f"unknown region {code!r}", "body")
        out[code.upper()] = known[code.upper()]
    return out


def _user_by_email(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None:
        raise invalid("email", "no Truebex account has this e-mail address; ask them to sign up first", "body")
    return user


# --- Overview ------------------------------------------------------------------------------


@router.get("/summary")
def summary(db: Session = Depends(get_db)) -> dict:
    def counts(column, *where) -> dict:
        stmt = select(column, func.count()).group_by(column)
        for w in where:
            stmt = stmt.where(w)
        return {k: v for k, v in db.execute(stmt).all()}

    return {
        "suppliers": counts(Supplier.status),
        "products": counts(Product.status),
        "reviews": counts(ProductReview.status),
        "orders": counts(MarketOrder.state, MarketOrder.kind == "order"),
        "quotes": counts(MarketOrder.state, MarketOrder.kind == "quote"),
        "commissions": counts(Commission.state),
        "feeds": counts(FeedRun.state),
        # The flag (GD5's sign-off) and whether Stripe is configured to take payments.
        "payments_enabled": get_settings().market_payments_enabled,
        "stripe_ready": checkout.enabled(),
        "listing_plans": listing.plans_json(),
    }


# --- Suppliers -----------------------------------------------------------------------------


@router.get("/suppliers")
def list_suppliers(status_: str | None = Query(default=None, alias="status"), db: Session = Depends(get_db)) -> dict:
    stmt = select(Supplier).order_by(Supplier.created_at.desc())
    if status_:
        stmt = stmt.where(Supplier.status == status_)
    return {"suppliers": [catalogue.supplier_admin_json(db, s) for s in db.scalars(stmt.limit(500))]}


@router.post("/suppliers", status_code=status.HTTP_201_CREATED)
def create_supplier(body: SupplierIn, db: Session = Depends(get_db)) -> dict:
    regions = _regions(db, body.regions)
    owner = _user_by_email(db, body.owner_email) if body.owner_email else None
    supplier = catalogue.create_supplier(
        db,
        name=body.name,
        country=body.country.upper(),
        legal_name=body.legal_name,
        company_number=body.company_number,
        vat_id=body.vat_id,
        website=body.website,
        contact_email=body.contact_email,
        status="applied",
    )
    catalogue.set_supplier_regions(db, supplier, regions)
    if owner:
        catalogue.add_member(db, supplier, owner, "owner")
    db.commit()
    return catalogue.supplier_admin_json(db, supplier)


@router.patch("/suppliers/{supplier_id}")
def edit_supplier(
    supplier_id: str, body: SupplierPatch, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    supplier = _supplier(db, supplier_id)
    old_status = supplier.status
    if body.status is not None and body.status != supplier.status:
        supplier.status = body.status
        supplier.status_reason = body.reason
        if body.status == "verified":
            supplier.verified_at = now()
    if body.commission_bp is not None:
        supplier.commission_bp = body.commission_bp
    if body.clear_commission:
        supplier.commission_bp = None
    if body.listing_plan is not None:
        if body.listing_plan not in listing.plans():
            raise invalid("listing_plan", f"one of {', '.join(listing.plans())}", "body")
        supplier.listing_plan = body.listing_plan
    if body.connect_account_id is not None:
        supplier.connect_account_id = body.connect_account_id
    if body.connect_ready is not None:
        supplier.connect_ready = body.connect_ready
    if body.billing_customer_id is not None:
        supplier.billing_customer_id = body.billing_customer_id
    if body.regions is not None:
        catalogue.set_supplier_regions(db, supplier, _regions(db, body.regions))
    db.add(supplier)
    db.commit()
    if supplier.status != old_status:  # PF8: the application's decision and its e-mail
        hooks.emit("supplier.status_changed", db, supplier=supplier, old=old_status, new=supplier.status, reason=body.reason, admin=admin)
    return catalogue.supplier_admin_json(db, supplier)


@router.post("/suppliers/{supplier_id}/members")
def add_member(supplier_id: str, body: MemberIn, db: Session = Depends(get_db)) -> dict:
    supplier = _supplier(db, supplier_id)
    catalogue.add_member(db, supplier, _user_by_email(db, body.email), body.role)
    db.commit()
    return catalogue.supplier_admin_json(db, supplier)


@router.post("/suppliers/{supplier_id}/connect")
def connect_onboarding(supplier_id: str, db: Session = Depends(get_db)) -> dict:
    """A Stripe Connect onboarding link to send to the supplier (PF8's
    portal shows it to the supplier itself)."""
    supplier = _supplier(db, supplier_id)
    site = get_settings().site_url.rstrip("/")
    url = checkout.onboarding_link(
        db, supplier, f"{site}/dashboard/admin/market/?connect=refresh", f"{site}/dashboard/admin/market/?connect=done"
    )
    return {"url": url, "connect_account_id": supplier.connect_account_id}


# --- Products --------------------------------------------------------------------------------


@router.get("/products")
def list_products(
    status_: str | None = Query(default="pending_review", alias="status"),
    supplier_id: str | None = Query(default=None, max_length=32),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Product).order_by(Product.updated_at.desc())
    if status_ and status_ != "all":
        stmt = stmt.where(Product.status == status_)
    if supplier_id:
        stmt = stmt.where(Product.supplier_id == supplier_id)
    return {"products": [catalogue.product_admin_json(db, p) for p in db.scalars(stmt.limit(200))]}


@router.post("/products/{product_id}/approve")
def approve_product(product_id: str, db: Session = Depends(get_db)) -> dict:
    product = _product(db, product_id)
    supplier = db.get(Supplier, product.supplier_id)
    if supplier is None or supplier.status != "verified":
        raise ContractError("conflict", 409, "Verify the supplier before approving its products.")
    catalogue.set_product_status(db, product, "approved")
    search.reindex(db, product, supplier)
    db.commit()
    hooks.emit("product.reviewed", db, product=product, decision="approved")
    return catalogue.product_admin_json(db, product)


@router.post("/products/{product_id}/reject")
def reject_product(product_id: str, body: ReasonIn, db: Session = Depends(get_db)) -> dict:
    product = _product(db, product_id)
    catalogue.set_product_status(db, product, "rejected", body.reason)
    db.commit()
    hooks.emit("product.reviewed", db, product=product, decision="rejected", note=body.reason)
    return catalogue.product_admin_json(db, product)


@router.post("/products/{product_id}/withdraw")
def withdraw_product(product_id: str, body: SupplierActionIn, db: Session = Depends(get_db)) -> dict:
    """Take a published product down (the app then gets 410 with substitutes)."""
    product = _product(db, product_id)
    catalogue.set_product_status(db, product, "withdrawn", body.reason)
    db.commit()
    return catalogue.product_admin_json(db, product)


# --- Reviews ---------------------------------------------------------------------------------


@router.get("/reviews")
def list_reviews(status_: str | None = Query(default="pending", alias="status"), db: Session = Depends(get_db)) -> dict:
    stmt = select(ProductReview, Product.name).join(Product, Product.product_id == ProductReview.product_id)
    if status_ and status_ != "all":
        stmt = stmt.where(ProductReview.status == status_)
    rows = db.execute(stmt.order_by(ProductReview.created_at.desc()).limit(200)).all()
    return {"reviews": [{**reviews.review_json(r, admin=True), "product_name": name} for r, name in rows]}


@router.post("/reviews/{review_id}/publish")
def publish_review(review_id: str, db: Session = Depends(get_db)) -> dict:
    return reviews.review_json(reviews.moderate(db, review_id, "published"), admin=True)


@router.post("/reviews/{review_id}/hide")
def hide_review(review_id: str, db: Session = Depends(get_db)) -> dict:
    return reviews.review_json(reviews.moderate(db, review_id, "hidden"), admin=True)


# --- Orders (and acting for a supplier until PF8's inbox) ---------------------------------------


@router.get("/orders")
def list_orders(
    state: str | None = Query(default=None, max_length=20),
    kind: str | None = Query(default=None, max_length=8),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(MarketOrder).order_by(MarketOrder.created_at.desc())
    if state:
        stmt = stmt.where(MarketOrder.state == state)
    if kind:
        stmt = stmt.where(MarketOrder.kind == kind)
    rows = db.scalars(stmt.limit(200))
    return {"orders": [orders.order_json(db, o) for o in rows]}


@router.get("/orders/{order_id}")
def one_order(order_id: str, db: Session = Depends(get_db)) -> dict:
    return orders.order_json(db, _order(db, order_id))


@router.post("/orders/{order_id}/suppliers/{supplier_id}/quote")
def quote_for_supplier(order_id: str, supplier_id: str, body: SupplierQuoteIn, db: Session = Depends(get_db)) -> dict:
    return orders.order_json(db, orders.supplier_quote(db, _order(db, order_id), supplier_id, body))


@router.post("/orders/{order_id}/suppliers/{supplier_id}/{action}")
def act_for_supplier(
    order_id: str, supplier_id: str, action: str, body: SupplierActionIn | None = None, db: Session = Depends(get_db)
) -> dict:
    order = _order(db, order_id)
    reason = body.reason if body else None
    if action == "accept":
        order = orders.supplier_accept(db, order, supplier_id)
    elif action == "reject":
        order = orders.supplier_reject(db, order, supplier_id, reason)
    elif action == "decline":
        order = orders.supplier_decline(db, order, supplier_id, reason)
    elif action == "ship":
        order = orders.supplier_ship(db, order, supplier_id)
    elif action == "deliver":
        order = orders.supplier_deliver(db, order, supplier_id)
    else:
        raise not_found("That action")
    return orders.order_json(db, order)


# --- Commissions and statements ---------------------------------------------------------------


@router.get("/commissions")
def list_commissions(db: Session = Depends(get_db)) -> dict:
    names = dict(db.execute(select(Supplier.supplier_id, Supplier.name)).all())
    rows = db.scalars(select(Commission).order_by(Commission.created_at.desc()).limit(500))
    statements = db.scalars(select(CommissionStatement).order_by(CommissionStatement.created_at.desc()).limit(200))
    return {
        "commissions": [{**commissions.commission_json(c), "supplier_name": names.get(c.supplier_id)} for c in rows],
        "statements": [commissions.statement_json(s, names.get(s.supplier_id)) for s in statements],
    }


@router.post("/commissions/statements")
def make_statements(db: Session = Depends(get_db)) -> dict:
    """Make last month's statements now (the monthly job does the same)."""
    names = dict(db.execute(select(Supplier.supplier_id, Supplier.name)).all())
    made = commissions.run_statements(db, now())
    return {"statements": [commissions.statement_json(s, names.get(s.supplier_id)) for s in made]}


# --- Feed runs ------------------------------------------------------------------------------------


@router.get("/feeds")
def list_feeds(db: Session = Depends(get_db)) -> dict:
    names = dict(db.execute(select(Supplier.supplier_id, Supplier.name)).all())
    rows = db.scalars(select(FeedRun).order_by(FeedRun.created_at.desc()).limit(100))
    return {"feeds": [{**importer.report_json(r), "supplier_name": names.get(r.supplier_id)} for r in rows]}


@router.get("/feeds/{feed_id}")
def one_feed(feed_id: str, db: Session = Depends(get_db)) -> dict:
    run = db.get(FeedRun, feed_id) if is_hex32(feed_id) else None
    if run is None:
        raise not_found("That feed run")
    return importer.report_json(run)


@router.post("/feeds", status_code=status.HTTP_201_CREATED)
async def import_feed(
    supplier_id: str = Form(..., max_length=32),
    format: str = Form(..., pattern="^(csv|json)$"),  # noqa: A002 - the contract's field name
    mode: str = Form(default="upsert", pattern="^(upsert|replace)$"),
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Import a feed for a supplier now (the engine PF8's 5.11 queues)."""
    supplier = _supplier(db, supplier_id)
    data = await file.read(MAX_FEED_UPLOAD + 1)
    if len(data) > MAX_FEED_UPLOAD:
        raise ContractError("too_large", 413, "A feed file is at most 50 MB.")
    try:
        run = importer.queue(db, supplier, data, format, mode, source="admin", by_user_id=admin.id)
    except importer.FeedTooLarge as exc:
        raise ContractError("too_large", 413, str(exc))
    except importer.FeedInvalid as exc:
        raise ContractError("feed_invalid", 422, str(exc))
    run = importer.execute(db, run.feed_id)
    return importer.report_json(run)


# --- Categories and the search index ----------------------------------------------------------------


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def add_category(body: CategoryIn, db: Session = Depends(get_db)) -> dict:
    try:
        row = catalogue.add_category(db, body.path, body.label)
    except ValueError:
        raise invalid("path", "a category starts with a path of the app's taxonomy (GET /market/categories)", "body")
    db.commit()
    return {"path": row.path, "label": row.label, "app_path": row.app_path}


@router.post("/search/rebuild")
def rebuild_search(db: Session = Depends(get_db)) -> dict:
    return {"indexed": search.rebuild(db)}
