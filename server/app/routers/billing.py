"""Billing endpoints: catalogue, checkout, subscription, seats, plan changes,
invoices, the customer portal and provider webhooks; PF2b's easy exit,
renewal cooling-off refund and EU withdrawal (billing/consumer.py).

The browser names a tier, an interval, a currency and seats; the server picks
the price (catalogue.json -> provider_prices) and a plan changes only from a
provider event or provider state the server verified itself.
"""

import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timezone

import httpx
import stripe
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..billing import consumer, notices, pricing, providers, service
from ..billing.base import NotSupported, ProviderError, WebhookError
from ..billing.pricing import PriceUnavailable
from ..config import get_settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Payment, Subscription, User
from ..plans import CURRENCIES, PLANS
from ..schemas import (
    BillingCatalog,
    CancelRequest,
    ChangeRequest,
    CheckoutRequest,
    CheckoutResponse,
    ExitOut,
    FoundingOut,
    InvoiceOut,
    PaymentOut,
    PriceOut,
    RulesOut,
    SeatsRequest,
    SubscriptionOut,
    TierOut,
    WithdrawRequest,
)

router = APIRouter(prefix="/billing", tags=["billing"])
settings = get_settings()
log = logging.getLogger("truebex.billing")

# Errors a provider call can raise; none of them changes our state.
_PROVIDER_ERRORS = (ProviderError, httpx.HTTPError, stripe.StripeError)

# Invoice PDF links stay valid this long (the dashboard is reloaded to renew).
PDF_LINK_TTL_S = 3600


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def _bad_gateway() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="The payment provider didn't respond. Please try again.",
    )


def _price_http(exc: PriceUnavailable) -> HTTPException:
    code = 503 if exc.reason == "not_synced" else 400
    return HTTPException(status_code=code, detail=exc.detail)


# --- Catalogue ---------------------------------------------------------------------


@router.get("/plans", response_model=BillingCatalog)
def catalog(db: Session = Depends(get_db)) -> BillingCatalog:
    """Public: tiers, prices per interval and currency, the founding offer and
    the provider offered at checkout."""
    wayl_on = providers.get_provider("wayl", settings).enabled()
    tiers = []
    for plan in PLANS.values():
        prices = [
            PriceOut(interval=p.interval, currency=p.currency, amount_minor=p.amount_minor)
            for p in plan.prices
        ]
        if wayl_on and plan.id == "pro":
            # Dormant regional rail: only with WAYL_ENABLED, never on the site.
            prices.append(
                PriceOut(interval="month", currency="IQD", amount_minor=settings.wayl_price_pro_iqd)
            )
        tiers.append(
            TierOut(
                id=plan.id,
                name=plan.name,
                purchasable=plan.purchasable,
                per_seat=plan.per_seat,
                min_seats=plan.min_seats,
                prices=prices,
            )
        )
    offered = providers.checkout_provider(settings)
    founding = service.founding_status(db)
    # The offer is shown only while it can be bought.
    founding["enabled"] = founding["enabled"] and offered is not None
    return BillingCatalog(
        tiers=tiers,
        founding=FoundingOut(**founding),
        provider=offered.name if offered else None,
        currencies=list(CURRENCIES),
        providers=providers.enabled_providers(settings),
        rules=RulesOut(**consumer.rules()),
    )


# --- Subscription --------------------------------------------------------------------


def _subscription_out(db: Session, user: User) -> SubscriptionOut:
    plan = service.effective_plan(db, user)
    live = service.live_subscription(db, user)
    managed = service.managed_subscription(db, user)
    # A past-due or paused subscription is shown so its card can be fixed.
    view = live or (managed if managed and managed.status in ("past_due", "paused") else None)
    can_manage = bool(
        managed is not None
        and managed.provider_customer_id
        and providers.get_provider(managed.provider, settings).enabled()
    )
    # PF2b: what the customer can end from Billing right now.
    now = datetime.now(timezone.utc)
    exits = {
        "can_cancel": consumer.can_cancel(db, managed, now),
        "cooling_off_until": consumer.cooling_off_until(db, managed, now),
        "withdrawal_until": consumer.withdrawal_until(db, managed, now),
    }
    if view is None:
        return SubscriptionOut(
            tier=plan,
            interval=None,
            seats=1,
            status="active" if plan != "free" else "none",
            provider=None,
            current_period_end=None,
            cancel_at_period_end=False,
            founding=False,
            can_manage=can_manage,
            **exits,
        )
    return SubscriptionOut(
        tier=plan,
        interval=view.interval,
        seats=view.seats or 1,
        status=view.status,
        provider=view.provider,
        current_period_end=view.current_period_end,
        cancel_at_period_end=bool(view.cancel_at_period_end),
        founding=bool(view.founding),
        can_manage=can_manage,
        currency=view.currency,
        **exits,
    )


@router.get("/subscription", response_model=SubscriptionOut)
def subscription(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SubscriptionOut:
    return _subscription_out(db, current)


def _live_managed(db: Session, user: User) -> Subscription:
    sub = service.managed_subscription(db, user)
    if sub is None or not service.is_live(sub):
        raise HTTPException(status_code=404, detail="No subscription to change.")
    return sub


@router.post("/seats", response_model=SubscriptionOut)
def change_seats(
    payload: SeatsRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionOut:
    """Change the seats of a per-seat subscription, prorated by the provider."""
    sub = _live_managed(db, current)
    plan = PLANS.get(sub.plan)
    if plan is None or not plan.per_seat:
        raise _unprocessable(f"{plan.name if plan else 'This'} plan has one seat.")
    if payload.seats < plan.min_seats:
        raise _unprocessable(f"{plan.name} needs at least {plan.min_seats} seats.")
    assigned = service.seats_assigned(db, sub)
    if payload.seats < assigned:
        raise HTTPException(
            status_code=409,
            detail=f"{assigned} seats are assigned. Remove people before lowering the count.",
        )
    adapter = providers.get_provider(sub.provider, settings)
    if not adapter.enabled():
        raise HTTPException(status_code=503, detail="Billing changes aren't available right now.")
    try:
        adapter.change_subscription(db, sub, seats=payload.seats)
    except PriceUnavailable as exc:
        raise _price_http(exc)
    except _PROVIDER_ERRORS:
        log.exception("seat change failed for subscription %s", sub.id)
        raise _bad_gateway()
    return _subscription_out(db, current)


@router.post("/change", response_model=SubscriptionOut)
def change_plan(
    payload: ChangeRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionOut:
    """Move the subscription to another tier or interval, prorated."""
    if payload.tier is None and payload.interval is None:
        raise _unprocessable("Choose a plan or a billing interval.")
    sub = _live_managed(db, current)
    tier = payload.tier or sub.plan
    interval = payload.interval or sub.interval or "month"
    try:
        pricing.catalogue_price(tier, interval, sub.currency or "USD")
    except PriceUnavailable as exc:
        raise _price_http(exc)
    adapter = providers.get_provider(sub.provider, settings)
    if not adapter.enabled():
        raise HTTPException(status_code=503, detail="Billing changes aren't available right now.")
    try:
        adapter.change_subscription(db, sub, tier=tier, interval=interval)
    except PriceUnavailable as exc:
        raise _price_http(exc)
    except _PROVIDER_ERRORS:
        log.exception("plan change failed for subscription %s", sub.id)
        raise _bad_gateway()
    return _subscription_out(db, current)


# --- Payments and checkout -------------------------------------------------------------


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


@router.get("/payments/{reference}", response_model=PaymentOut)
def payment_detail(
    reference: str = Path(max_length=64),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Payment:
    """One checkout: /checkout/ shows its key information beside the pay
    button (PF2b)."""
    payment = db.scalar(
        select(Payment).where(Payment.reference == reference, Payment.user_id == current.id)
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    return payment


def _new_reference() -> str:
    return f"tbx_{secrets.token_hex(12)}"


def _wayl_checkout(payload: CheckoutRequest, current: User, db: Session) -> CheckoutResponse:
    adapter = providers.get_provider("wayl", settings)
    if not adapter.enabled():
        raise HTTPException(status_code=503, detail="That payment method isn't available.")
    if payload.tier != "pro" or payload.interval != "month" or payload.seats != 1:
        raise HTTPException(status_code=400, detail="That plan can't be bought this way.")
    payment = Payment(
        user_id=current.id,
        provider="wayl",
        plan="pro",
        reference=_new_reference(),
        amount=settings.wayl_price_pro_iqd,
        currency="IQD",
        interval="month",
        seats=1,
        consent_version=payload.consent.version,
        consent_at=datetime.now(timezone.utc),
        business=payload.business,
    )
    try:
        url = adapter.create_checkout(db, current, payment, None, 1, None)
    except _PROVIDER_ERRORS:
        log.exception("checkout failed (wayl)")
        raise _bad_gateway()
    db.add(payment)
    db.commit()
    return CheckoutResponse(url=url, reference=payment.reference, founding=False)


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(
    payload: CheckoutRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    # Today's placeholder consent, or GD5 7.4's box once the wording is
    # approved (PF2b), in the QS-17 variant.
    if payload.consent.version != consumer.consent_version():
        raise _unprocessable("The cancellation terms changed. Reload the page and accept them again.")
    approved = consumer.wording_approved()
    if approved and (payload.key_info is None or payload.key_info.version != notices.KEY_INFO.version):
        raise _unprocessable("Read and acknowledge the key information before you pay.")
    plan = PLANS.get(payload.tier)
    if plan is None or not plan.purchasable:
        raise HTTPException(status_code=400, detail="That plan can't be bought online.")
    if payload.provider == "wayl":
        return _wayl_checkout(payload, current, db)

    currency = payload.currency.upper()
    try:
        pricing.catalogue_price(plan.id, payload.interval, currency)
    except PriceUnavailable as exc:
        raise _price_http(exc)
    seats = payload.seats
    if plan.per_seat and seats < plan.min_seats:
        raise _unprocessable(f"{plan.name} needs at least {plan.min_seats} seats.")
    if not plan.per_seat and seats != 1:
        raise _unprocessable(f"{plan.name} has one seat.")

    adapter = providers.checkout_provider(settings)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Online payment isn't available yet.",
        )
    existing = service.managed_subscription(db, current)
    if existing is not None and (
        service.is_live(existing) or existing.status in ("past_due", "paused")
    ):
        raise HTTPException(
            status_code=409,
            detail="You already have a subscription. Change it, or update its card under Manage.",
        )

    discount = None
    code = (payload.coupon or "").strip()
    if code:
        try:
            discount = adapter.resolve_coupon(code)
        except _PROVIDER_ERRORS:
            log.exception("coupon lookup failed")
            raise _bad_gateway()
        if discount is None:
            raise HTTPException(status_code=400, detail="That code isn't valid.")

    reference = _new_reference()
    # A coupon replaces the founding price; one discount per checkout.
    founding = discount is None and service.hold_founding(db, current, reference, plan.id)
    try:
        price = pricing.resolve(db, adapter.name, plan.id, payload.interval, currency, founding)
    except PriceUnavailable as exc:
        if not founding:
            raise _price_http(exc)
        # The founding price isn't mirrored to the provider: sell at list price.
        log.warning("founding price not synced for %s/%s/%s", plan.id, payload.interval, currency)
        service.release_founding(db, reference)
        founding = False
        try:
            price = pricing.resolve(db, adapter.name, plan.id, payload.interval, currency, False)
        except PriceUnavailable as exc2:
            raise _price_http(exc2)

    now = datetime.now(timezone.utc)
    payment = Payment(
        user_id=current.id,
        provider=adapter.name,
        plan=plan.id,
        reference=reference,
        amount=price.amount_minor * seats,
        currency=currency,
        interval=payload.interval,
        seats=seats,
        consent_version=payload.consent.version,
        consent_at=now,
        business=payload.business,
    )
    if approved:
        # The key information for the price the server picked, stored with
        # the consent (DMCC: acknowledged at the last step).
        payment.key_info = consumer.key_info_text(
            plan.id, seats, payload.interval, currency, price.amount_minor * seats, adapter.name
        )
        payment.key_info_version = notices.KEY_INFO.version
        payment.key_info_at = now
    try:
        url = adapter.create_checkout(db, current, payment, price, seats, discount)
    except _PROVIDER_ERRORS:
        # Nothing was charged; give the founding seats back.
        log.exception("checkout failed (%s)", adapter.name)
        service.release_founding(db, reference)
        raise _bad_gateway()
    db.add(payment)
    db.commit()
    return CheckoutResponse(url=url, reference=reference, founding=founding, key_info=payment.key_info)


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
    if payment.status == "pending":
        try:
            adapter = providers.get_provider(payment.provider, settings)
        except KeyError:
            adapter = None
        if adapter is not None and adapter.enabled():
            try:
                adapter.verify_payment(db, payment)
            except _PROVIDER_ERRORS:
                log.exception("%s refresh failed for %s", payment.provider, reference)
        db.refresh(payment)
    return payment


# --- Invoices ----------------------------------------------------------------------------


def _pdf_signature(user_id: int, provider: str, invoice_id: str, exp: int) -> str:
    msg = f"invoice-pdf:{user_id}:{provider}:{invoice_id}:{exp}".encode()
    return hmac.new(settings.secret_key.encode(), msg, hashlib.sha256).hexdigest()


def _pdf_link(user_id: int, provider: str, invoice_id: str) -> str:
    """A link the browser can open without a session header: signed for this
    user and invoice, valid one hour. Relative to the API's base URL."""
    exp = int(time.time()) + PDF_LINK_TTL_S
    sig = _pdf_signature(user_id, provider, invoice_id, exp)
    return f"/billing/invoices/{invoice_id}/pdf?u={user_id}&p={provider}&exp={exp}&sig={sig}"


@router.get("/invoices", response_model=list[InvoiceOut])
def invoices(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[InvoiceOut]:
    """VAT invoices from every provider the user has bought through."""
    out: list[InvoiceOut] = []
    for name in ("paddle", "stripe"):
        adapter = providers.get_provider(name, settings)
        if not adapter.enabled() or not service.customer_id(db, current, name):
            continue
        try:
            rows = adapter.list_invoices(db, current)
        except _PROVIDER_ERRORS:
            log.exception("invoice list failed (%s)", name)
            raise _bad_gateway()
        for inv in rows:
            out.append(
                InvoiceOut(
                    id=inv.id,
                    number=inv.number,
                    issued_at=inv.issued_at,
                    total_minor=inv.total_minor,
                    tax_minor=inv.tax_minor,
                    currency=inv.currency,
                    status=inv.status,
                    pdf_url=inv.pdf_url or _pdf_link(current.id, name, inv.id),
                )
            )
    out.sort(key=lambda i: i.issued_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return out


@router.get("/invoices/{invoice_id}/pdf", include_in_schema=False)
def invoice_pdf(
    invoice_id: str,
    u: int = Query(...),
    p: str = Query(..., max_length=16),
    exp: int = Query(...),
    sig: str = Query(..., max_length=128),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Redirect to a fresh PDF URL from the provider (signed link only)."""
    if exp < time.time() or not hmac.compare_digest(sig, _pdf_signature(u, p, invoice_id, exp)):
        raise HTTPException(status_code=403, detail="This invoice link has expired. Reload the billing page.")
    user = db.get(User, u)
    try:
        adapter = providers.get_provider(p, settings)
    except KeyError:
        adapter = None
    if user is None or adapter is None or not adapter.enabled():
        raise HTTPException(status_code=404, detail="Invoice not found.")
    try:
        url = adapter.invoice_pdf_url(db, user, invoice_id)
    except NotSupported:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    except _PROVIDER_ERRORS:
        log.exception("invoice pdf failed (%s %s)", p, invoice_id)
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return RedirectResponse(url, status_code=302)


# --- Customer portal -----------------------------------------------------------------------


@router.post("/portal")
def portal(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """The provider's own page for cards and cancellation."""
    sub = service.managed_subscription(db, current)
    if sub is None or not sub.provider_customer_id:
        raise HTTPException(status_code=404, detail="No subscription to manage.")
    adapter = providers.get_provider(sub.provider, settings)
    if not adapter.enabled():
        raise HTTPException(status_code=404, detail="No subscription to manage.")
    try:
        return {"url": adapter.portal_url(db, current, sub)}
    except _PROVIDER_ERRORS:
        log.exception("portal failed (%s)", sub.provider)
        raise _bad_gateway()


# --- Ending a subscription inside Billing (PF2b) -----------------------------------------------


def _exit_out(ex) -> ExitOut:
    return ExitOut(
        kind=ex.kind,
        requested_at=ex.requested_at,
        effective_at=ex.effective_at,
        refund_minor=ex.refund_minor,
        currency=ex.currency,
        status=consumer.exit_status(ex),
    )


def _live_for_exit(db: Session, user: User) -> Subscription:
    sub = service.managed_subscription(db, user)
    if sub is None or not service.is_live(sub):
        raise HTTPException(status_code=404, detail="No subscription to cancel.")
    if not providers.get_provider(sub.provider, settings).enabled():
        raise HTTPException(status_code=503, detail="Cancelling isn't available right now. Use Manage instead.")
    return sub


@router.post("/cancel", response_model=ExitOut)
def cancel(
    payload: CancelRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExitOut:
    """The easy exit: cancel at the end of the period, in one flow, without
    the provider's portal. With `refund` (the renewal cooling-off, behind
    SUBSCRIPTION_NOTICES_ENABLED): cancel now and refund the rest of the
    renewed year. Confirmed by e-mail; the plan changes when the provider's
    signed webhook arrives."""
    now = datetime.now(timezone.utc)
    sub = _live_for_exit(db, current)
    if consumer.pending_exit(db, sub, now) is not None:
        raise HTTPException(status_code=409, detail="Your cancellation is already on its way.")
    if payload.refund:
        if consumer.cooling_off_until(db, sub, now) is None:
            raise HTTPException(status_code=409, detail="A refund isn't available for this plan now.")
        kind = "cooling_off"
    else:
        if sub.cancel_at_period_end:
            raise HTTPException(status_code=409, detail="Your plan is already set to end.")
        kind = "cancel"
    return _exit_out(consumer.start_exit(db, current, sub, kind, now))


@router.post("/withdraw", response_model=ExitOut)
def withdraw(
    payload: WithdrawRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExitOut:
    """The EU withdrawal function (Directive 2011/83/EU Art. 11a; behind
    EU_WITHDRAWAL_ENABLED): an EU consumer inside the withdrawal period ends
    the contract and is refunded; the acknowledgement, with the date and
    time, is e-mailed at once."""
    if not settings.eu_withdrawal_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    now = datetime.now(timezone.utc)
    sub = _live_for_exit(db, current)
    if consumer.pending_exit(db, sub, now) is not None:
        raise HTTPException(status_code=409, detail="Your withdrawal is already on its way.")
    if consumer.withdrawal_until(db, sub, now) is None:
        raise HTTPException(status_code=409, detail="This purchase can't be withdrawn from here.")
    return _exit_out(consumer.start_exit(db, current, sub, "withdrawal", now))


# --- Webhooks (called by the providers, not the browser) ---------------------------------------


async def _webhook(name: str, request: Request, db: Session) -> str | None:
    adapter = providers.get_provider(name, settings)
    if not adapter.enabled():
        raise HTTPException(status_code=404)
    body = await request.body()
    try:
        return await run_in_threadpool(adapter.handle_webhook, db, body, request.headers)
    except WebhookError:
        raise HTTPException(status_code=400, detail="Invalid signature.")


@router.post("/webhooks/paddle", include_in_schema=False)
async def paddle_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    return {"received": await _webhook("paddle", request, db)}


@router.post("/webhooks/stripe", include_in_schema=False)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    return {"received": await _webhook("stripe", request, db)}


@router.post("/webhooks/wayl", include_in_schema=False)
async def wayl_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    adapter = providers.get_provider("wayl", settings)
    if not adapter.enabled():
        raise HTTPException(status_code=404)
    body = await request.body()
    try:
        status_ = await run_in_threadpool(adapter.handle_webhook, db, body, request.headers)
    except WebhookError:
        raise HTTPException(status_code=400, detail="Expected JSON.")
    except httpx.HTTPError:
        log.exception("wayl webhook sync failed")
        raise HTTPException(status_code=502, detail="Could not confirm with Wayl.")
    if status_ is None:
        # Unknown link: acknowledge so Wayl stops retrying, change nothing.
        return {"received": False}
    return {"received": True, "status": status_}
