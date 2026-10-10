"""The marketplace API (contract marketplace-api v1.1, §5.1–5.10) and the
platform's own marketplace routes (checkout, Stripe webhook, picture search,
reviews, product images).

Catalogue reads (5.1–5.6) need no credential and are rate-limited per
address; orders (5.7–5.10) take a device token (the app) or a session (the
website). PF8 adds the supplier feed endpoints 5.11–5.13 on top of
`market.importer`.
"""

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import ratelimit
from ..config import get_settings
from ..contract_http import CONTRACT_HEADER, ContractError, contract, enveloped
from ..database import get_db
from ..deps import LicenceCaller, get_current_user, get_session_or_device
from ..market import catalogue, checkout, embeddings, hooks, media, orders, reviews, search
from ..market.common import CONTRACT_MAJOR, CONTRACT_MINOR, CONTRACT_NAME, CONTRACT_VERSION, invalid, is_hex32, not_found
from ..market.prices import MAX_BATCH, batch, region_or_invalid
from ..market.schemas import OrderRequest, PricesRequest, ReviewIn
from ..models import User
from ..storage import InvalidKey, check_key, get_store

router = APIRouter(
    prefix="/market", tags=["market"], dependencies=[contract(CONTRACT_NAME, CONTRACT_MAJOR, CONTRACT_MINOR)]
)
internal = APIRouter(prefix="/market", tags=["market"], dependencies=[enveloped()])


def anonymous_reads(request: Request) -> None:
    """Catalogue reads per address (contract §7: 429 `rate_limited`)."""
    per_minute = get_settings().market_reads_per_minute
    wait = ratelimit.take(
        "market.reads", ratelimit.client_ip(request), per_minute=float(per_minute), burst=max(1, per_minute)
    )
    if wait is not None:
        retry = max(1, int(wait + 0.999))
        raise ContractError("rate_limited", 429, "Too many catalogue requests. Try again shortly.", retry_after_s=retry)


Reads = Depends(anonymous_reads)


# --- 5.1–5.6 catalogue ---------------------------------------------------------------------


@router.get("/categories", dependencies=[Reads])
def categories(request: Request, response: Response, db: Session = Depends(get_db)):
    body = catalogue.categories_json(db)
    etag = catalogue.etag_of(body)
    headers = {"ETag": etag, "Cache-Control": "public, max-age=86400"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={**headers, CONTRACT_HEADER: CONTRACT_VERSION})
    response.headers.update(headers)
    return body


@router.get("/regions", dependencies=[Reads])
def regions(request: Request, response: Response, db: Session = Depends(get_db)):
    from ..market.taxonomy import active_regions, region_json

    body = {"regions": [region_json(r) for r in active_regions(db).values()]}
    etag = catalogue.etag_of(body)
    headers = {"ETag": etag, "Cache-Control": "public, max-age=86400"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={**headers, CONTRACT_HEADER: CONTRACT_VERSION})
    response.headers.update(headers)
    return body


@router.get("/search", dependencies=[Reads])
def search_products(
    q: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=160),
    region: str | None = Query(default=None, max_length=8),
    min: int | None = Query(default=None, ge=0),  # noqa: A002 - the contract's names
    max: int | None = Query(default=None, ge=0),  # noqa: A002
    available: bool | None = None,
    supplier: str | None = Query(default=None, max_length=32),
    kind: str | None = Query(default=None, max_length=16),
    sort: str = Query(default="relevance", max_length=16),
    cursor: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=24, ge=1, le=search.MAX_LIMIT),
    db: Session = Depends(get_db),
) -> dict:
    params = search.SearchParams(
        q=q,
        category=category or None,
        region=region.upper() if region else None,
        min=min,
        max=max,
        available=available,
        supplier=supplier or None,
        kind=kind or None,
        sort=sort,
        cursor=cursor or None,
        limit=limit,
    )
    body = search.search(db, params)
    # PF8 analytics: one impression per product shown.
    hooks.emit("search.results", db, product_ids=[r["product_id"] for r in body["results"]], region=params.region)
    return body


@router.get("/products/{product_id}", dependencies=[Reads])
def product(product_id: str, region: str | None = Query(default=None, max_length=8), db: Session = Depends(get_db)) -> dict:
    if not is_hex32(product_id):
        raise not_found("That product")
    r = region_or_invalid(db, region) if region else None
    body = catalogue.public_product(db, product_id, r)
    hooks.emit("product.viewed", db, product_id=product_id, region=r.region if r else None)  # PF8 analytics
    return body


@router.post("/prices", dependencies=[Reads])
def prices(body: PricesRequest, db: Session = Depends(get_db)) -> dict:
    if len(body.items) > MAX_BATCH:
        raise ContractError("too_large", 413, f"Ask for at most {MAX_BATCH} items per call.", {"max_items": MAX_BATCH})
    region = region_or_invalid(db, body.region.upper(), where="body")
    return batch(db, region, [i.model_dump() for i in body.items])


@router.get("/suppliers/{supplier_id}", dependencies=[Reads])
def supplier_profile(supplier_id: str, db: Session = Depends(get_db)) -> dict:
    supplier = catalogue.get_supplier(db, supplier_id) if is_hex32(supplier_id) else None
    if supplier is None or supplier.status != "verified":
        raise not_found("That supplier")
    return catalogue.supplier_json(db, supplier)


# --- 5.7–5.10 orders and requests ------------------------------------------------------------


@router.post("/orders", status_code=status.HTTP_201_CREATED)
def place_order(
    body: OrderRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    caller: LicenceCaller = Depends(get_session_or_device),
    db: Session = Depends(get_db),
) -> dict:
    if idempotency_key is not None and not is_hex32(idempotency_key.lower()):
        raise invalid("Idempotency-Key", "32 hex characters", "header")
    order, replayed = orders.place(
        db, caller.user, caller.device.device_id if caller.device else None, body,
        idempotency_key.lower() if idempotency_key else None,
    )  # fmt: skip
    if replayed:
        response.headers["Idempotency-Replayed"] = "true"
    return orders.order_json(db, order)


@router.get("/orders")
def my_orders(
    state: str | None = Query(default=None, max_length=20),
    cursor: str | None = Query(default=None, max_length=200),
    project_uid: str | None = Query(default=None, max_length=32),
    caller: LicenceCaller = Depends(get_session_or_device),
    db: Session = Depends(get_db),
) -> dict:
    return orders.list_orders(db, caller.user, state=state, cursor=cursor, project_uid=project_uid)


@router.get("/orders/{order_id}")
def one_order(order_id: str, caller: LicenceCaller = Depends(get_session_or_device), db: Session = Depends(get_db)) -> dict:
    return orders.order_json(db, orders.get_owned(db, caller.user, order_id))


@router.post("/orders/{order_id}/cancel")
def cancel_order(order_id: str, caller: LicenceCaller = Depends(get_session_or_device), db: Session = Depends(get_db)) -> dict:
    order = orders.cancel(db, orders.get_owned(db, caller.user, order_id))
    return orders.order_json(db, order)


# --- Platform routes (not in the contract) ------------------------------------------------------


@internal.post("/orders/{order_id}/accept", status_code=status.HTTP_201_CREATED)
def accept_quote(order_id: str, caller: LicenceCaller = Depends(get_session_or_device), db: Session = Depends(get_db)) -> dict:
    """The buyer accepts a quoted request: the order made from it."""
    quote = orders.get_owned(db, caller.user, order_id)
    return orders.order_json(db, orders.accept_quote(db, quote))


@internal.post("/checkout/{order_id}")
def start_checkout(order_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """The website's Pay button: a Stripe Checkout URL for the order."""
    order = orders.get_owned(db, current, order_id)
    return {"url": checkout.start(db, order, current), "order_id": order.order_id}


@internal.post("/checkout/{order_id}/refresh")
def refresh_checkout(order_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """After the redirect back: ask Stripe whether the session was paid."""
    order = checkout.refresh(db, orders.get_owned(db, current, order_id))
    return orders.order_json(db, order)


@internal.post("/webhooks/stripe", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
    db: Session = Depends(get_db),
) -> dict:
    if not get_settings().stripe_connect_webhook_secret:
        raise ContractError("not_found", 404, "Not found.")
    payload = await request.body()
    try:
        kind = checkout.handle_webhook(db, payload, stripe_signature)
    except ValueError:
        raise ContractError("invalid_signature", 400, "Invalid signature.")
    return {"received": kind}


@internal.post("/search/image", dependencies=[Reads])
async def picture_search(
    request: Request,
    image: UploadFile | None = File(default=None),
    text: str | None = Form(default=None, max_length=300),
    region: str | None = Form(default=None, max_length=8),
    limit: int = Form(default=24, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """Products by a picture (multipart `image`, JPEG or PNG ≤ 5 MB) or a
    description (`text`). Platform-internal until the contract adds it."""
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > embeddings.MAX_QUERY_IMAGE_BYTES + 64 * 1024:
        raise ContractError("too_large", 413, "Pictures are limited to 5 MB.")
    embedder = embeddings.get_embedder()
    if embedder is None:
        raise ContractError("unavailable", 503, "Picture search is not switched on on this server.")
    r = region_or_invalid(db, region.upper(), where="body").region if region else None
    if image is not None:
        data = await image.read(embeddings.MAX_QUERY_IMAGE_BYTES + 1)
        if len(data) > embeddings.MAX_QUERY_IMAGE_BYTES:
            raise ContractError("too_large", 413, "Pictures are limited to 5 MB.")
        try:
            vector = embedder.embed_image(data)
        except Exception:
            raise invalid("image", "not a readable JPEG or PNG picture", "body")
    elif text and text.strip():
        vector = embedder.embed_text(text)
        if vector is None:  # no text model: the description goes to the text index
            found = search.search(db, search.SearchParams(q=text, region=r, limit=limit))
            return {"results": found["results"], "model": "text-index"}
    else:
        raise invalid("image", "send a picture (image) or a description (text)", "body")
    hits = embeddings.nearest(db, embedder, vector, limit)
    scores = dict(hits)
    results = search.items_for(db, [pid for pid, _ in hits], r)[:limit]
    for item in results:
        item["score"] = round(scores[item["product_id"]], 4)
    return {"results": results, "model": embedder.model}


@internal.get("/products/{product_id}/reviews", dependencies=[Reads])
def product_reviews(
    product_id: str,
    cursor: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    from ..market.models import Product

    product = db.get(Product, product_id) if is_hex32(product_id) else None
    if product is None or product.status != "approved":
        raise not_found("That product")
    rows = reviews.published(db, product_id, cursor, limit + 1)
    return {
        "reviews": [reviews.review_json(r) for r in rows[:limit]],
        "rating": catalogue.rating_json(product),
        "next_cursor": cursor + limit if len(rows) > limit else None,
    }


@internal.post("/products/{product_id}/reviews", status_code=status.HTTP_201_CREATED)
def post_review(
    product_id: str, body: ReviewIn, current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    review = reviews.post(db, current, product_id, body.rating, body.text)
    return {**reviews.review_json(review), "status": review.status}


@internal.get("/geometry/{product_id}/{variant_id}", dependencies=[Reads], include_in_schema=False)
def geometry_file(
    product_id: str, variant_id: str, region: str | None = Query(default=None, max_length=8), db: Session = Depends(get_db)
):
    """A published variant's 3D file (contract 5.4 `geometry.url`): counted as
    a placement for the supplier's analytics (PF8), then a redirect to a
    signed URL (1 h) served as an attachment."""
    from sqlalchemy import select

    from ..market.models import Product, ProductVariant, Supplier
    from ..market.prices import is_public
    from ..market.taxonomy import active_regions

    product = db.get(Product, product_id) if is_hex32(product_id) else None
    supplier = db.get(Supplier, product.supplier_id) if product else None
    if product is None or not is_public(product, supplier):
        raise not_found("That product")
    v = db.scalar(
        select(ProductVariant).where(ProductVariant.product_id == product_id, ProductVariant.variant_id == variant_id)
    )
    if v is None or v.status == "hidden" or not v.geometry:
        raise not_found("That 3D file")
    code = region.upper() if region and region.upper() in active_regions(db) else None
    url = media.geometry_url(get_store(), v.geometry, f"{product.sku}-{v.variant_id}")
    hooks.emit("geometry.downloaded", db, product_id=product_id, region=code)
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "private, no-store"})


@internal.get("/media/{kind}/{name}", include_in_schema=False)
def media_file(kind: str, name: str):
    """Product images and thumbnails: public, content-addressed, immutable."""
    if kind not in ("images", "thumbs") or not name.endswith(".jpg") or not is_sha_name(name):
        raise not_found("That image")
    try:
        key = check_key(f"market/{kind}/{name}")
    except InvalidKey:
        raise not_found("That image")
    store = get_store()
    info = store.stat(key)
    if info is None:
        raise not_found("That image")
    headers = {"Cache-Control": "public, max-age=31536000, immutable"}
    if hasattr(store, "file_path"):
        return FileResponse(store.file_path(key), media_type="image/jpeg", headers=headers)
    return RedirectResponse(store.signed_get_url(key, expires_in=86400), headers=headers)


def is_sha_name(name: str) -> bool:
    stem = name[: -len(".jpg")]
    return len(stem) == 64 and all(c in "0123456789abcdef" for c in stem)
