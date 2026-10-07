"""Billing endpoints: catalog, checkout, subscription, history, webhooks."""

import logging
import secrets

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..billing import providers, service
from ..config import get_settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Payment, User
from ..plans import PLANS
from ..schemas import (
    BillingCatalog,
    CheckoutRequest,
    CheckoutResponse,
    PaymentOut,
    PlanOut,
    SubscriptionOut,
)

router = APIRouter(prefix="/billing", tags=["billing"])
settings = get_settings()
log = logging.getLogger("truebex.billing")


def _enabled_providers() -> list[str]:
    out = []
    if providers.stripe_enabled(settings):
        out.append("stripe")
    if providers.wayl_enabled(settings):
        out.append("wayl")
    return out


@router.get("/plans", response_model=BillingCatalog)
def catalog() -> BillingCatalog:
    """Public: plans, prices and which payment providers are switched on."""
    return BillingCatalog(
        plans=[
            PlanOut(
                id=p.id,
                name=p.name,
                price_usd_cents=p.price_usd_cents,
                price_iqd=settings.wayl_price_pro_iqd if p.id == "pro" else None,
                monthly_requests=p.monthly_requests,
                max_api_keys=p.max_api_keys,
                purchasable=p.purchasable,
            )
            for p in PLANS.values()
        ],
        providers=_enabled_providers(),
    )


@router.get("/subscription", response_model=SubscriptionOut)
def subscription(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SubscriptionOut:
    plan = service.effective_plan(db, current)
    sub = service.live_subscription(db, current)
    return SubscriptionOut(
        plan=plan,
        status=sub.status if sub else ("active" if plan != "free" else "none"),
        provider=sub.provider if sub else None,
        current_period_end=sub.current_period_end if sub else None,
        can_manage=bool(
            providers.stripe_enabled(settings) and service.stripe_customer_id(db, current)
        ),
    )


@router.get("/payments", response_model=list[PaymentOut])
def payment_history(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Payment]:
    return list(
        db.scalars(
            select(Payment)
            .where(Payment.user_id == current.id)
            .order_by(Payment.created_at.desc())
            .limit(50)
        )
    )


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(
    payload: CheckoutRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    plan = PLANS.get(payload.plan)
    if plan is None or not plan.purchasable:
        raise HTTPException(status_code=400, detail="That plan can't be bought online.")
    if payload.provider not in _enabled_providers():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{payload.provider.title()} payments aren't available yet.",
        )

    if payload.provider == "stripe":
        amount, currency = plan.price_usd_cents or 0, "USD"
    else:
        amount, currency = settings.wayl_price_pro_iqd, "IQD"

    payment = Payment(
        user_id=current.id,
        provider=payload.provider,
        plan=plan.id,
        reference=f"tbx_{secrets.token_hex(12)}",
        amount=amount,
        currency=currency,
    )
    try:
        if payload.provider == "stripe":
            url = providers.stripe_checkout(settings, db, current, payment)
        else:
            url = providers.wayl_checkout(settings, current, payment)
    except Exception:  # provider/network failure: nothing was charged
        log.exception("checkout failed (%s)", payload.provider)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The payment provider didn't respond. Please try again.",
        )
    db.add(payment)
    db.commit()
    return CheckoutResponse(url=url, reference=payment.reference)


@router.post("/payments/{reference}/refresh", response_model=PaymentOut)
def refresh_payment(
    reference: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Payment:
    """Re-check a payment with its provider (the user just came back from
    checkout). Covers webhooks that never arrived while the server was off."""
    payment = db.scalar(
        select(Payment).where(Payment.reference == reference, Payment.user_id == current.id)
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    if payment.status == "pending" and payment.provider == "wayl" and providers.wayl_enabled(settings):
        try:
            providers.wayl_sync(settings, db, payment)
        except httpx.HTTPError:
            log.exception("wayl refresh failed for %s", reference)
        db.refresh(payment)
    return payment


@router.post("/portal")
def stripe_portal(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """Stripe's hosted page for changing card / cancelling."""
    customer = service.stripe_customer_id(db, current)
    if not providers.stripe_enabled(settings) or not customer:
        raise HTTPException(status_code=404, detail="No Stripe subscription to manage.")
    return {"url": providers.stripe_portal(settings, customer)}


# --- Webhooks (called by the providers, not the browser) -----------------------


@router.post("/webhooks/stripe", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
    db: Session = Depends(get_db),
) -> dict:
    if not providers.stripe_enabled(settings):
        raise HTTPException(status_code=404)
    payload = await request.body()
    try:
        kind = providers.stripe_webhook(settings, db, payload, stripe_signature)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature.")
    return {"received": kind}


@router.post("/webhooks/wayl", include_in_schema=False)
async def wayl_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    if not providers.wayl_enabled(settings):
        raise HTTPException(status_code=404)
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Expected JSON.")
    reference = providers.wayl_reference_from_webhook(body if isinstance(body, dict) else {})
    payment = (
        db.scalar(select(Payment).where(Payment.reference == reference, Payment.provider == "wayl"))
        if reference
        else None
    )
    if payment is None:
        # Unknown link: acknowledge so Wayl stops retrying, change nothing.
        return {"received": False}
    try:
        status_ = providers.wayl_sync(settings, db, payment)
    except httpx.HTTPError:
        log.exception("wayl webhook sync failed for %s", reference)
        raise HTTPException(status_code=502, detail="Could not confirm with Wayl.")
    return {"received": True, "status": status_}

