"""The supplier portal (PF8): `/supplier/*` for signed-in members of a
supplier (session; role checks per route), the feed endpoints of contract
marketplace-api §5.11–5.13 under `/market/feeds` (a supplier's API key), and
the admin's view of an application.

Services live in `app/supplier/`; PF7's `app/market/` holds the catalogue,
the importer and the orders this portal drives.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, Query, Request, UploadFile, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..contract_http import ContractError, contract, enveloped
from ..database import SessionLocal, get_db
from ..deps import get_current_user, require_admin
from ..market import importer
from ..market.common import CONTRACT_MAJOR, CONTRACT_MINOR, CONTRACT_NAME, is_hex32, not_found, rfc3339
from ..market.models import FeedRun, Supplier
from ..models import User
from ..supplier import (
    analytics,
    applications,
    catalogue,
    feeds,
    imports,
    inbox,
    listing,
    members,
    prices,
    template,
)
from ..supplier.common import ANY, CATALOGUE, ORDERS, OWNER, Member, member, memberships, resolve
from ..supplier.schemas import (
    AcceptInviteIn,
    ApplicationIn,
    FeedSourceIn,
    InboxQuoteIn,
    InviteIn,
    KeyIn,
    ListingIn,
    PricesIn,
    ProductIn,
    ProductPatch,
    ReasonIn,
    RegionsIn,
    RoleIn,
    ShipIn,
    SubmitManyIn,
    VariantIn,
    VariantPatch,
)

router = APIRouter(prefix="/supplier", tags=["supplier portal"], dependencies=[enveloped()])
feeds_router = APIRouter(
    prefix="/market/feeds", tags=["market feeds"], dependencies=[contract(CONTRACT_NAME, CONTRACT_MAJOR, CONTRACT_MINOR)]
)
admin = APIRouter(prefix="/admin/market", tags=["admin"], dependencies=[enveloped(), Depends(require_admin)])

Any = Depends(member(ANY))
Catalogue = Depends(member(CATALOGUE, write=True))
Orders = Depends(member(ORDERS))
OrdersWrite = Depends(member(ORDERS, write=True))
Owner = Depends(member(OWNER))
OwnerWrite = Depends(member(OWNER, write=True))


async def _read(upload: UploadFile, limit: int, request: Request, what: str) -> bytes:
    def too_large() -> ContractError:
        size = f"{limit // (1024 * 1024)} MB" if limit >= 1024 * 1024 else f"{limit} bytes"
        return ContractError("too_large", 413, f"{what} is at most {size}.", {"max_bytes": limit})

    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > limit + 1024 * 1024:
        raise too_large()
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise too_large()
    return data


def _run_in_background(supplier_id: str) -> None:
    """Run a just-queued feed now (the 30 s job would take it otherwise)."""
    with SessionLocal() as db:
        feeds.run_queued(db, supplier_id=supplier_id)


# --- Who am I, sign-up ---------------------------------------------------------------------


def _supplier_json(db: Session, s: Supplier) -> dict:
    from ..market.catalogue import payments_ready

    return {
        "supplier_id": s.supplier_id,
        "name": s.name,
        "legal_name": s.legal_name,
        "country": s.country,
        "company_number": s.company_number,
        "vat_id": s.vat_id,
        "website": s.website,
        "contact_email": s.contact_email,
        "status": s.status,
        "status_reason": s.status_reason,
        "verified_at": rfc3339(s.verified_at),
        "listing_plan": s.listing_plan,
        "regions": [r["region"] for r in prices.regions_json(db, s)["regions"] if r["served"]],
        "payouts_connected": bool(s.connect_account_id),
        "payouts_ready": bool(s.connect_ready),
        "orderable": payments_ready(s),
    }


@router.get("/me")
def me(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    supplier_id: str | None = Header(default=None, alias="X-Truebex-Supplier", max_length=32),
) -> dict:
    rows = memberships(db, current)
    out = {
        "user": {"id": current.id, "email": current.email, "name": current.name},
        "memberships": [
            {"supplier_id": s.supplier_id, "name": s.name, "role": role, "status": s.status} for s, role in rows
        ],
        "supplier": None,
        "role": None,
        "application": None,
    }
    if rows:
        m = resolve(db, current, supplier_id if any(s.supplier_id == supplier_id for s, _ in rows) else None)
        out["supplier"] = _supplier_json(db, m.supplier)
        out["role"] = m.role
        out["application"] = applications.application_json(applications.application_of(db, m.supplier.supplier_id))
    return out


@router.post("/applications", status_code=status.HTTP_201_CREATED)
def apply(body: ApplicationIn, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    app = applications.apply(db, current, body)
    return applications.application_json(app)


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    m: Member = Owner,
    db: Session = Depends(get_db),
) -> dict:
    data = await _read(file, applications.MAX_DOCUMENT_BYTES, request, "A document")
    return applications.add_document(db, m.supplier, data, file.filename or "document.pdf")


@router.get("/overview")
def overview(m: Member = Any, db: Session = Depends(get_db)) -> dict:
    last = db.scalar(select(FeedRun).where(FeedRun.supplier_id == m.supplier.supplier_id).order_by(FeedRun.created_at.desc()))
    counts = catalogue.list_products(db, m.supplier, None, None)["counts"]
    return {
        "supplier": _supplier_json(db, m.supplier),
        "role": m.role,
        "application": applications.application_json(applications.application_of(db, m.supplier.supplier_id)),
        "open": inbox.open_counts(db, m.supplier),
        "products": counts,
        "last_run": importer.report_json(last) if last else None,
        "feed_source": feeds.source_json(feeds.source_of(db, m.supplier)),
        "week": analytics.week(db, m.supplier),
    }


# --- Catalogue -------------------------------------------------------------------------------


@router.get("/products")
def list_products(
    status_: str | None = Query(default=None, alias="status", max_length=20),
    q: str | None = Query(default=None, max_length=120),
    m: Member = Any,
    db: Session = Depends(get_db),
) -> dict:
    return catalogue.list_products(db, m.supplier, status_, q)


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(body: ProductIn, m: Member = Catalogue, db: Session = Depends(get_db)) -> dict:
    return catalogue.detail_json(db, catalogue.create(db, m, body))


@router.post("/products/submit")
def submit_products(body: SubmitManyIn, m: Member = Catalogue, db: Session = Depends(get_db)) -> dict:
    return catalogue.submit_many(db, m, body.product_ids)


@router.get("/products/{product_id}")
def get_product(product_id: str, m: Member = Any, db: Session = Depends(get_db)) -> dict:
    return catalogue.detail_json(db, catalogue.owned(db, m.supplier, product_id))


@router.patch("/products/{product_id}")
def edit_product(product_id: str, body: ProductPatch, m: Member = Catalogue, db: Session = Depends(get_db)) -> dict:
    product = catalogue.edit(db, m, catalogue.owned(db, m.supplier, product_id), body)
    return catalogue.detail_json(db, product)


@router.post("/products/{product_id}/variants", status_code=status.HTTP_201_CREATED)
def add_variant(product_id: str, body: VariantIn, m: Member = Catalogue, db: Session = Depends(get_db)) -> dict:
    product = catalogue.owned(db, m.supplier, product_id)
    catalogue.add_variant(db, m, product, body)
    return catalogue.detail_json(db, product)


@router.patch("/products/{product_id}/variants/{variant_id}")
def edit_variant(
    product_id: str, variant_id: str, body: VariantPatch, m: Member = Catalogue, db: Session = Depends(get_db)
) -> dict:
    product = catalogue.owned(db, m.supplier, product_id)
    catalogue.edit_variant(db, m, product, variant_id, body)
    return catalogue.detail_json(db, product)


@router.delete("/products/{product_id}/variants/{variant_id}")
def remove_variant(product_id: str, variant_id: str, m: Member = Catalogue, db: Session = Depends(get_db)) -> dict:
    product = catalogue.owned(db, m.supplier, product_id)
    catalogue.remove_variant(db, m, product, variant_id)
    return catalogue.detail_json(db, product)


@router.post("/products/{product_id}/variants/{variant_id}/images", status_code=status.HTTP_201_CREATED)
async def add_image(
    request: Request,
    product_id: str,
    variant_id: str,
    image: UploadFile = File(...),
    m: Member = Catalogue,
    db: Session = Depends(get_db),
) -> dict:
    product = catalogue.owned(db, m.supplier, product_id)
    data = await _read(image, catalogue.MAX_IMAGE_BYTES, request, "A picture")
    catalogue.add_image(db, m, product, variant_id, data)
    return catalogue.detail_json(db, product)


@router.delete("/products/{product_id}/variants/{variant_id}/images/{sha}")
def remove_image(product_id: str, variant_id: str, sha: str, m: Member = Catalogue, db: Session = Depends(get_db)) -> dict:
    product = catalogue.owned(db, m.supplier, product_id)
    catalogue.remove_image(db, m, product, variant_id, sha)
    return catalogue.detail_json(db, product)


@router.post("/products/{product_id}/{action}")
def product_action(product_id: str, action: str, m: Member = Catalogue, db: Session = Depends(get_db)) -> dict:
    product = catalogue.owned(db, m.supplier, product_id)
    actions = {
        "submit": catalogue.submit,
        "hide": catalogue.hide,
        "show": catalogue.show,
        "withdraw": catalogue.withdraw,
        "discontinue": catalogue.discontinue,
    }
    if action not in actions:
        raise not_found("That action")
    return catalogue.detail_json(db, actions[action](db, m, product))


@router.post("/geometry")
async def upload_geometry(
    request: Request,
    file: UploadFile = File(...),
    product_id: str = Form(..., max_length=32),
    variant_id: str = Form(..., max_length=64),
    m: Member = Catalogue,
    db: Session = Depends(get_db),
) -> dict:
    from ..supplier.geometry_check import MAX_BYTES

    product = catalogue.owned(db, m.supplier, product_id)
    data = await _read(file, MAX_BYTES, request, "A 3D file")
    return catalogue.set_geometry(db, m, product, variant_id, data, file.filename or "")


# --- Prices and regions -------------------------------------------------------------------------


@router.get("/prices")
def get_prices(region: str | None = Query(default=None, max_length=8), m: Member = Any, db: Session = Depends(get_db)) -> dict:
    return prices.grid(db, m.supplier, region)


@router.put("/prices")
def put_prices(
    body: PricesIn, region: str | None = Query(default=None, max_length=8), m: Member = Catalogue, db: Session = Depends(get_db)
) -> dict:
    return prices.save(db, m.supplier, region, body.rows)


@router.get("/regions")
def get_regions(m: Member = Any, db: Session = Depends(get_db)) -> dict:
    return prices.regions_json(db, m.supplier)


@router.put("/regions")
def put_regions(body: RegionsIn, m: Member = Catalogue, db: Session = Depends(get_db)) -> dict:
    return prices.set_regions(db, m.supplier, body)


# --- Imports and feeds ------------------------------------------------------------------------------


@router.get("/imports")
def list_imports(m: Member = Any, db: Session = Depends(get_db)) -> dict:
    return {**imports.history(db, m.supplier), "source": feeds.source_json(feeds.source_of(db, m.supplier))}


@router.post("/imports", status_code=status.HTTP_201_CREATED)
async def upload_import(
    request: Request,
    file: UploadFile = File(...),
    format: str | None = Form(default=None, max_length=8),  # noqa: A002 - the field's name
    mode: str = Form(default="upsert", max_length=8),
    m: Member = Catalogue,
    db: Session = Depends(get_db),
) -> dict:
    fmt = imports.format_of(file.filename or "", format)
    data = await _read(file, importer.MAX_BYTES, request, "A file")
    return imports.import_json(db, imports.create(db, m, data, file.filename or "", fmt, mode))


@router.get("/imports/template.xlsx")
def download_template(m: Member = Any, db: Session = Depends(get_db)) -> Response:
    return Response(
        template.build(db, m.supplier),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="truebex-catalogue-template.xlsx"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/imports/{import_id}")
def get_import(import_id: str, m: Member = Any, db: Session = Depends(get_db)) -> dict:
    return imports.import_json(db, imports.get(db, m.supplier, import_id))


@router.post("/imports/{import_id}/apply", status_code=status.HTTP_202_ACCEPTED)
def apply_import(import_id: str, background: BackgroundTasks, m: Member = Catalogue, db: Session = Depends(get_db)) -> dict:
    imp = imports.get(db, m.supplier, import_id)
    imports.apply(db, m, imp)
    background.add_task(_run_in_background, m.supplier.supplier_id)
    return imports.import_json(db, imports.get(db, m.supplier, import_id))


@router.get("/runs/{feed_id}")
def get_run(feed_id: str, m: Member = Any, db: Session = Depends(get_db)) -> dict:
    return importer.report_json(feeds.get_run(db, m.supplier, feed_id))


@router.get("/feeds/source")
def get_source(m: Member = Any, db: Session = Depends(get_db)) -> dict:
    return {"source": feeds.source_json(feeds.source_of(db, m.supplier))}


@router.put("/feeds/source")
def put_source(body: FeedSourceIn, m: Member = Catalogue, db: Session = Depends(get_db)) -> dict:
    src = feeds.set_source(db, m.supplier, m.user, body.url, body.format, body.mode)
    return {"source": feeds.source_json(src)}


@router.delete("/feeds/source")
def delete_source(m: Member = Catalogue, db: Session = Depends(get_db)) -> dict:
    feeds.remove_source(db, m.supplier)
    return {"source": None}


@router.post("/feeds/source/pull")
def pull_source(background: BackgroundTasks, m: Member = Catalogue, db: Session = Depends(get_db)) -> dict:
    """Read the registered address now (the daily 02:00 UTC read stays)."""
    from ..market.common import now

    src = feeds.source_of(db, m.supplier)
    if src is None:
        raise not_found("A registered feed address")
    feeds.pull(db, src, now())
    background.add_task(_run_in_background, m.supplier.supplier_id)
    return {"source": feeds.source_json(feeds.source_of(db, m.supplier))}


# --- Inbox ---------------------------------------------------------------------------------------------


@router.get("/inbox")
def list_inbox(
    kind: str | None = Query(default=None, max_length=8),
    state: str | None = Query(default=None, max_length=16),
    open_: bool = Query(default=False, alias="open"),
    m: Member = Orders,
    db: Session = Depends(get_db),
) -> dict:
    return inbox.list_items(db, m.supplier, kind, state, open_)


@router.get("/inbox/{order_id}")
def get_inbox_item(order_id: str, m: Member = Orders, db: Session = Depends(get_db)) -> dict:
    return inbox.one(db, m.supplier, order_id)


@router.post("/inbox/{order_id}/quote")
def quote(order_id: str, body: InboxQuoteIn, m: Member = OrdersWrite, db: Session = Depends(get_db)) -> dict:
    return inbox.quote(db, m.supplier, order_id, body)


@router.post("/inbox/{order_id}/ship")
def ship(order_id: str, body: ShipIn, m: Member = OrdersWrite, db: Session = Depends(get_db)) -> dict:
    return inbox.act(db, m.supplier, order_id, "ship", carrier=body.carrier, reference=body.reference)


@router.post("/inbox/{order_id}/{action}")
def inbox_action(
    order_id: str, action: str, body: ReasonIn | None = None, m: Member = OrdersWrite, db: Session = Depends(get_db)
) -> dict:
    if action not in ("accept", "reject", "decline", "deliver"):
        raise not_found("That action")
    return inbox.act(db, m.supplier, order_id, action, reason=body.reason if body else None)


# --- Analytics -------------------------------------------------------------------------------------------


@router.get("/analytics")
def get_analytics(
    from_: str | None = Query(default=None, alias="from", max_length=10),
    to: str | None = Query(default=None, max_length=10),
    region: str | None = Query(default=None, max_length=8),
    m: Member = Any,
    db: Session = Depends(get_db),
) -> dict:
    return analytics.report(db, m.supplier, from_, to, region.upper() if region else None)


# --- Listing plan, statements, payouts -------------------------------------------------------------------


@router.get("/listing")
def get_listing(m: Member = Owner, db: Session = Depends(get_db)) -> dict:
    return listing.overview(db, m.supplier)


@router.post("/listing")
def choose_listing(body: ListingIn, m: Member = OwnerWrite, db: Session = Depends(get_db)) -> dict:
    return {**listing.choose(db, m, body.plan), "listing": listing.overview(db, m.supplier)}


@router.get("/statements")
def get_statements(m: Member = Owner, db: Session = Depends(get_db)) -> dict:
    return listing.statements(db, m.supplier)


@router.get("/statements/{statement_id}/invoice")
def get_invoice(statement_id: str, m: Member = Owner, db: Session = Depends(get_db)) -> dict:
    return {"url": listing.invoice_url(db, m, statement_id)}


@router.post("/payouts/connect")
def connect_payouts(m: Member = OwnerWrite, db: Session = Depends(get_db)) -> dict:
    return listing.connect(db, m.supplier)


# --- Team and keys --------------------------------------------------------------------------------------


@router.get("/members")
def get_team(m: Member = Owner, db: Session = Depends(get_db)) -> dict:
    return members.team_json(db, m.supplier)


@router.post("/members", status_code=status.HTTP_201_CREATED)
def invite(body: InviteIn, m: Member = OwnerWrite, db: Session = Depends(get_db)) -> dict:
    return members.invite(db, m, str(body.email), body.role)


@router.patch("/members/{user_id}")
def change_role(user_id: int, body: RoleIn, m: Member = OwnerWrite, db: Session = Depends(get_db)) -> dict:
    members.set_role(db, m, user_id, body.role)
    return members.team_json(db, m.supplier)


@router.delete("/members/{user_id}")
def remove_member(user_id: int, m: Member = OwnerWrite, db: Session = Depends(get_db)) -> dict:
    members.remove(db, m, user_id)
    return members.team_json(db, m.supplier)


@router.delete("/invites/{invite_id}")
def revoke_invite(invite_id: str, m: Member = OwnerWrite, db: Session = Depends(get_db)) -> dict:
    members.revoke_invite(db, m, invite_id)
    return members.team_json(db, m.supplier)


@router.post("/invites/accept")
def accept_invite(body: AcceptInviteIn, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return members.accept(db, current, body.token)


@router.post("/keys", status_code=status.HTTP_201_CREATED)
def create_key(body: KeyIn, m: Member = OwnerWrite, db: Session = Depends(get_db)) -> dict:
    return members.create_key(db, m, body.name)


@router.delete("/keys/{key_id}")
def revoke_key(key_id: int, m: Member = OwnerWrite, db: Session = Depends(get_db)) -> dict:
    return members.revoke_key(db, m, key_id)


# --- Contract §5.11–5.13: the feeds of supplier systems -----------------------------------------------------

_bearer = HTTPBearer(auto_error=False)


def feed_caller(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> feeds.FeedCaller:
    return feeds.caller_for_key(db, x_api_key or (creds.credentials if creds else None))


@feeds_router.post("", status_code=status.HTTP_202_ACCEPTED)
async def post_feed(
    request: Request,
    file: UploadFile = File(...),
    format: str = Form(..., pattern="^(csv|json)$"),  # noqa: A002 - the contract's field name
    mode: str = Form(default="upsert", pattern="^(upsert|replace)$"),
    caller: feeds.FeedCaller = Depends(feed_caller),
    db: Session = Depends(get_db),
) -> dict:
    """5.11: a feed file → 202 queued; header or JSON shape wrong → 422 `feed_invalid`."""
    data = await _read(file, importer.MAX_BYTES, request, "A feed file")
    run = feeds.upload(db, caller.supplier, caller.user, data, format, mode)
    return {"feed_id": run.feed_id, "state": run.state}


@feeds_router.put("/source")
def put_feed_source(body: FeedSourceIn, caller: feeds.FeedCaller = Depends(feed_caller), db: Session = Depends(get_db)) -> dict:
    """5.12: the https address pulled daily at 02:00 UTC."""
    return feeds.source_json(feeds.set_source(db, caller.supplier, caller.user, body.url, body.format, body.mode))


@feeds_router.get("/{feed_id}")
def get_feed(feed_id: str, caller: feeds.FeedCaller = Depends(feed_caller), db: Session = Depends(get_db)) -> dict:
    """5.13: the import report (≤ 200 row errors)."""
    if not is_hex32(feed_id):
        raise not_found("That feed run")
    return importer.report_json(feeds.get_run(db, caller.supplier, feed_id))


# --- Admin: the application behind a supplier ----------------------------------------------------------------


@admin.get("/suppliers/{supplier_id}/application")
def supplier_application(supplier_id: str, db: Session = Depends(get_db)) -> dict:
    supplier = db.get(Supplier, supplier_id) if is_hex32(supplier_id) else None
    if supplier is None:
        raise not_found("That supplier")
    return applications.admin_json(db, supplier)
