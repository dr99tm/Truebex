"""Product reviews: only a buyer with a delivered order of the product may
review it (GD1 §4.10), once per product; a review is `pending` until an admin
publishes it; the product's average and count follow its published reviews.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..models import User
from .common import invalid, new_id, not_found, now, rfc3339
from .models import MarketOrder, MarketOrderLine, MarketOrderSupplier, Product, ProductReview

REVIEW_STATES = ("pending", "published", "hidden")


def _author(user: User) -> str:
    """The first name only (never the e-mail address)."""
    first = (user.name or "").strip().split(" ")[0]
    return first[:60] or "A Truebex buyer"


def delivered_order(db: Session, user: User, product: Product) -> str | None:
    return db.scalar(
        select(MarketOrder.order_id)
        .join(MarketOrderLine, MarketOrderLine.order_id == MarketOrder.order_id)
        .join(
            MarketOrderSupplier,
            (MarketOrderSupplier.order_id == MarketOrder.order_id)
            & (MarketOrderSupplier.supplier_id == MarketOrderLine.supplier_id),
        )
        .where(
            MarketOrder.user_id == user.id,
            MarketOrder.kind == "order",
            MarketOrderLine.product_id == product.product_id,
            MarketOrderSupplier.state == "delivered",
        )
        .limit(1)
    )


def post(db: Session, user: User, product_id: str, rating: int, text: str) -> ProductReview:
    product = db.get(Product, product_id)
    if product is None or product.status != "approved":
        raise not_found("That product")
    order_id = delivered_order(db, user, product)
    if order_id is None:
        raise ContractError(
            "not_a_buyer", 403, "Only buyers whose order of this product was delivered can review it."
        )
    if not 1 <= rating <= 5:
        raise invalid("rating", "a whole number from 1 to 5", "body")
    existing = db.scalar(
        select(ProductReview).where(ProductReview.product_id == product_id, ProductReview.user_id == user.id)
    )
    if existing is not None:
        raise ContractError("conflict", 409, "You have already reviewed this product.")
    review = ProductReview(
        review_id=new_id(),
        product_id=product_id,
        user_id=user.id,
        order_id=order_id,
        rating=rating,
        text=text.strip(),
        author=_author(user),
        status="pending",
        created_at=now(),
    )
    db.add(review)
    db.commit()
    return review


def recompute(db: Session, product: Product) -> None:
    avg, count = db.execute(
        select(func.avg(ProductReview.rating), func.count()).where(
            ProductReview.product_id == product.product_id, ProductReview.status == "published"
        )
    ).one()
    product.rating_count = int(count or 0)
    product.rating_avg = float(avg) if count else None
    db.add(product)


def moderate(db: Session, review_id: str, status: str) -> ProductReview:
    if status not in ("published", "hidden"):
        raise invalid("status", "published or hidden", "body")
    review = db.get(ProductReview, review_id)
    if review is None:
        raise not_found("That review")
    review.status, review.moderated_at = status, now()
    db.add(review)
    db.flush()
    product = db.get(Product, review.product_id)
    if product is not None:
        recompute(db, product)
    db.commit()
    return review


def review_json(r: ProductReview, *, admin: bool = False) -> dict:
    out = {
        "review_id": r.review_id,
        "product_id": r.product_id,
        "rating": r.rating,
        "text": r.text,
        "author": r.author,
        "created_at": rfc3339(r.created_at),
    }
    if admin:
        out.update({"status": r.status, "order_id": r.order_id, "user_id": r.user_id, "moderated_at": rfc3339(r.moderated_at)})
    return out


def published(db: Session, product_id: str, offset: int, limit: int) -> list[ProductReview]:
    return list(
        db.scalars(
            select(ProductReview)
            .where(ProductReview.product_id == product_id, ProductReview.status == "published")
            .order_by(ProductReview.created_at.desc(), ProductReview.review_id)
            .offset(offset)
            .limit(limit)
        )
    )
