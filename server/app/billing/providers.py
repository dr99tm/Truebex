"""Payment provider adapters.

Each adapter turns a pending Payment into a hosted checkout URL and turns
provider events into calls on billing.service. A provider is enabled only
when its keys are set in server/.env; otherwise it is hidden from the site
and checkout returns 503.
"""

from datetime import datetime, timezone
from typing import Any

import httpx
import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Payment, User
from ..plans import get_plan
from . import service

# ---------------------------------------------------------------------------
# Stripe: recurring card subscriptions via Stripe Checkout.
# ---------------------------------------------------------------------------

# Stripe subscription status -> ours.
_STRIPE_STATUS = {
    "active": "active",
    "trialing": "active",
    "past_due": "past_due",
    "unpaid": "past_due",
    "incomplete": "past_due",
    "canceled": "canceled",
    "incomplete_expired": "canceled",
    "paused": "canceled",
}


def stripe_enabled(s: Settings) -> bool:
    return bool(s.stripe_secret_key and s.stripe_webhook_secret and s.stripe_price_pro)


def stripe_checkout(s: Settings, db: Session, user: User, payment: Payment) -> str:
    customer = service.stripe_customer_id(db, user)
    meta = {"user_id": str(user.id), "plan": payment.plan, "reference": payment.reference}
    params: dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": s.stripe_price_pro, "quantity": 1}],
        "client_reference_id": payment.reference,
        "success_url": f"{s.site_url}/dashboard/billing/?checkout=success&ref={payment.reference}",
        "cancel_url": f"{s.site_url}/dashboard/billing/?checkout=canceled&ref={payment.reference}",
        "metadata": meta,
        "subscription_data": {"metadata": meta},
        "allow_promotion_codes": True,
    }
    if customer:
        params["customer"] = customer
    else:
        params["customer_email"] = user.email
    session = stripe.checkout.Session.create(api_key=s.stripe_secret_key, **params)
    payment.provider_ref = session["id"]
    return session["url"]


def stripe_portal(s: Settings, customer_id: str) -> str:
    portal = stripe.billing_portal.Session.create(
        api_key=s.stripe_secret_key,
        customer=customer_id,
        return_url=f"{s.site_url}/dashboard/billing/",
    )
    return portal["url"]


def _period_end(sub: Any) -> datetime | None:
    # Newer Stripe API versions moved current_period_end onto the items.
    ts = sub.get("current_period_end")
    if ts is None:
        items = (sub.get("items") or {}).get("data") or []
        if items:
            ts = items[0].get("current_period_end")
    return datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None


def _apply_stripe_subscription(db: Session, sub: Any) -> None:
    meta = sub.get("metadata") or {}
    try:
        user_id = int(meta.get("user_id", ""))
    except ValueError:
        return  # not created by our checkout
    service.upsert_stripe_subscription(
        db,
        user_id=user_id,
        plan=meta.get("plan") or "pro",
        stripe_subscription_id=sub["id"],
        stripe_customer_id=sub.get("customer"),
        status=_STRIPE_STATUS.get(sub.get("status", ""), "canceled"),
        current_period_end=_period_end(sub),
    )


def stripe_webhook(s: Settings, db: Session, payload: bytes, signature: str) -> str:
    """Verify and apply a Stripe webhook. Raises ValueError if unsigned."""
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, s.stripe_webhook_secret
        )
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise ValueError("invalid Stripe signature") from exc

    kind = event["type"]
    obj = event["data"]["object"]

    if kind == "checkout.session.completed":
        payment = db.scalar(
            select(Payment).where(Payment.reference == obj.get("client_reference_id"))
        )
        if payment is not None:
            service.mark_payment_paid(db, payment)
            db.commit()
        if obj.get("subscription"):
            sub = stripe.Subscription.retrieve(
                obj["subscription"], api_key=s.stripe_secret_key
            )
            _apply_stripe_subscription(db, sub)
    elif kind in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        _apply_stripe_subscription(db, obj)
    return kind


# ---------------------------------------------------------------------------
# Wayl: one-time IQD payment links (QiCard, FIB, ZainCash). Each paid link
# buys one prepaid period. API: https://api.thewayl.com/reference
# ---------------------------------------------------------------------------

WAYL_PAID = {"Complete", "Delivered"}
WAYL_FAILED = {"Cancelled", "Rejected", "Returned"}


def wayl_enabled(s: Settings) -> bool:
    return bool(s.wayl_api_key and s.wayl_webhook_secret)


def _wayl_client(s: Settings) -> httpx.Client:
    return httpx.Client(
        base_url=s.wayl_api_base,
        headers={"X-WAYL-AUTHENTICATION": s.wayl_api_key},
        timeout=30,
    )


def wayl_checkout(s: Settings, user: User, payment: Payment) -> str:
    plan = get_plan(payment.plan)
    body = {
        "env": s.wayl_env,
        "referenceId": payment.reference,
        "total": payment.amount,
        "currency": "IQD",
        "customParameter": f"user:{user.id}",
        "lineItem": [
            {
                "label": f"Truebex {plan.name} - 30 days",
                "amount": payment.amount,
                "type": "increase",
            }
        ],
        "webhookUrl": f"{s.api_url}/billing/webhooks/wayl",
        "webhookSecret": s.wayl_webhook_secret,
        "redirectionUrl": f"{s.site_url}/dashboard/billing/?checkout=success",
        "linkExpiresIn": "24h",
    }
    with _wayl_client(s) as client:
        res = client.post("/api/v1/links", json=body)
        res.raise_for_status()
        data = res.json()["data"]
    payment.provider_ref = str(data.get("id") or "")
    return data["url"]


def wayl_fetch_status(s: Settings, reference: str) -> dict[str, Any]:
    with _wayl_client(s) as client:
        res = client.get(f"/api/v1/links/{reference}")
        res.raise_for_status()
        return res.json()["data"]


def wayl_sync(s: Settings, db: Session, payment: Payment) -> str:
    """Ask Wayl for the link's real status and apply it. Returns the status.

    Webhook bodies are never trusted: they only tell us which link to check.
    """
    link = wayl_fetch_status(s, payment.reference)
    status = str(link.get("status", ""))
    try:
        total = int(float(link.get("total", 0)))
    except (TypeError, ValueError):
        total = 0
    if status in WAYL_PAID and total >= payment.amount:
        service.grant_wayl_period(db, payment)
    elif status in WAYL_FAILED and payment.status == "pending":
        payment.status = "failed"
        db.add(payment)
        db.commit()
    return status


def wayl_reference_from_webhook(body: dict[str, Any]) -> str | None:
    for container in (body, body.get("data") or {}):
        ref = container.get("referenceId") if isinstance(container, dict) else None
        if isinstance(ref, str) and ref:
            return ref
    return None
