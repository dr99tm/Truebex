"""Paying for orders: Stripe Checkout on the platform's account and Stripe
Connect transfers to the suppliers (separate charges and transfers).

* `start` opens one Checkout Session for the whole order (one card entry for
  every supplier in it), `transfer_group` = the order id. Prices come from
  the order's lines, never from the browser.
* A verified `checkout.session.completed` (or the buyer's return, checked by
  retrieving the session from Stripe) marks the order `paid`.
* `market.transfers` pays each supplier its part (goods + delivery + tax)
  minus the commission once it has accepted; a rejected part, or a paid
  order cancelled before any acceptance, is refunded.
* Card data never reaches this server. `MARKET_PAYMENTS_ENABLED` stays off
  until GD5 signs off the marketplace terms: then every supplier is
  quote-only.

The `Gateway` is the only code that talks to Stripe; tests swap it with
`monkeypatch.setattr(checkout, "gateway", lambda: fake)`.
"""

import logging
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError
from ..models import User
from . import commissions
from .catalogue import payments_ready
from .models import MarketOrder, MarketOrderSupplier, Supplier
from .orders import _groups, _lines, mark_paid, unit_of

log = logging.getLogger("truebex.market")


class Gateway(Protocol):
    def create_checkout(self, params: dict) -> dict:
        """→ {"id", "url"}"""
        ...

    def retrieve_session(self, session_id: str) -> dict: ...

    def transfer(self, *, amount: int, currency: str, destination: str, transfer_group: str, key: str, metadata: dict) -> str: ...

    def refund(self, *, payment_intent: str, amount: int | None, key: str, metadata: dict) -> str: ...

    def construct_event(self, payload: bytes, signature: str) -> dict:
        """Raises ValueError unless signed by one of the webhook secrets."""
        ...

    def create_account(self, supplier: Supplier) -> str: ...

    def account_link(self, account_id: str, refresh_url: str, return_url: str) -> str: ...


class StripeGateway:
    def __init__(self) -> None:
        self.s = get_settings()

    def _key(self) -> str:
        return self.s.stripe_secret_key

    def create_checkout(self, params: dict) -> dict:
        import stripe

        session = stripe.checkout.Session.create(api_key=self._key(), **params)
        return {"id": session["id"], "url": session["url"]}

    def retrieve_session(self, session_id: str) -> dict:
        import stripe

        return dict(stripe.checkout.Session.retrieve(session_id, api_key=self._key()))

    def transfer(self, *, amount, currency, destination, transfer_group, key, metadata) -> str:
        import stripe

        t = stripe.Transfer.create(
            api_key=self._key(),
            amount=amount,
            currency=currency.lower(),
            destination=destination,
            transfer_group=transfer_group,
            metadata=metadata,
            idempotency_key=key,
        )
        return t["id"]

    def refund(self, *, payment_intent, amount, key, metadata) -> str:
        import stripe

        params: dict[str, Any] = {"payment_intent": payment_intent, "metadata": metadata}
        if amount is not None:
            params["amount"] = amount
        r = stripe.Refund.create(api_key=self._key(), idempotency_key=key, **params)
        return r["id"]

    def construct_event(self, payload: bytes, signature: str) -> dict:
        import stripe

        secrets = [x.strip() for x in self.s.stripe_connect_webhook_secret.split(",") if x.strip()]
        for secret in secrets:
            try:
                return stripe.Webhook.construct_event(payload, signature, secret)
            except (ValueError, stripe.SignatureVerificationError):
                continue
        raise ValueError("invalid Stripe signature")

    def create_account(self, supplier: Supplier) -> str:
        import stripe

        account = stripe.Account.create(
            api_key=self._key(),
            type="express",
            country=supplier.country,
            email=supplier.contact_email,
            capabilities={"transfers": {"requested": True}},
            business_profile={"name": supplier.name, "url": supplier.website},
            metadata={"supplier_id": supplier.supplier_id},
        )
        return account["id"]

    def account_link(self, account_id: str, refresh_url: str, return_url: str) -> str:
        import stripe

        link = stripe.AccountLink.create(
            api_key=self._key(),
            account=account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type="account_onboarding",
        )
        return link["url"]


def gateway() -> Gateway:
    return StripeGateway()


def enabled() -> bool:
    s = get_settings()
    return bool(s.market_payments_enabled and s.stripe_secret_key)


def _provider_error() -> ContractError:
    return ContractError("provider_error", 502, "The payment provider didn't respond. Please try again.")


# --- Checkout ----------------------------------------------------------------------------


def _line_items(db: Session, order: MarketOrder) -> list[dict]:
    currency = order.currency.lower()
    suppliers = {
        s.supplier_id: s
        for s in db.scalars(select(Supplier).where(Supplier.supplier_id.in_([g.supplier_id for g in _groups(db, order.order_id)])))
    }
    items: list[dict] = []
    for ln in _lines(db, order.order_id):
        items.append(
            {
                "price_data": {
                    "currency": currency,
                    "unit_amount": unit_of(ln),
                    "product_data": {"name": f"{ln.name} ({ln.variant_id})"[:250]},
                },
                "quantity": ln.qty,
            }
        )
    for g in _groups(db, order.order_id):
        name = suppliers[g.supplier_id].name if g.supplier_id in suppliers else "supplier"
        if g.delivery:
            items.append(
                {
                    "price_data": {
                        "currency": currency,
                        "unit_amount": g.delivery,
                        "product_data": {"name": f"Delivery from {name}"[:250]},
                    },
                    "quantity": 1,
                }
            )
        # Tax-exclusive regions: the tax the totals add.
        added = g.total - g.subtotal - g.delivery
        if added > 0:
            items.append(
                {
                    "price_data": {"currency": currency, "unit_amount": added, "product_data": {"name": f"Tax ({name})"[:250]}},
                    "quantity": 1,
                }
            )
    return items


def start(db: Session, order: MarketOrder, user: User) -> str:
    """The Stripe Checkout URL for an order awaiting payment."""
    if order.kind != "order" or order.state != "awaiting_payment":
        raise ContractError("conflict", 409, f"This order is {order.state}; there is nothing to pay.")
    if not enabled():
        raise ContractError("unavailable", 503, "Card payments for orders are not open yet.")
    groups = _groups(db, order.order_id)
    suppliers = list(db.scalars(select(Supplier).where(Supplier.supplier_id.in_([g.supplier_id for g in groups]))))
    if not all(payments_ready(s) for s in suppliers):
        raise ContractError(
            "unavailable", 409, "A supplier in this order takes requests for quote only for now.", {"reason": "quote_only"}
        )
    gw = gateway()
    if order.checkout_session:
        try:
            existing = gw.retrieve_session(order.checkout_session)
        except Exception:
            log.exception("checkout retrieve failed for %s", order.order_id)
            raise _provider_error()
        if existing.get("payment_status") == "paid":
            mark_paid(db, order, existing.get("payment_intent"))
            raise ContractError("conflict", 409, "This order is already paid.")
        if existing.get("status") == "open" and existing.get("url"):
            return existing["url"]
    site = get_settings().site_url.rstrip("/")
    params = {
        "mode": "payment",
        "line_items": _line_items(db, order),
        "client_reference_id": order.order_id,
        "customer_email": (order.contact or {}).get("email") or user.email,
        "success_url": f"{site}/market/checkout/?order={order.order_id}&paid=1",
        "cancel_url": f"{site}/market/checkout/?order={order.order_id}",
        "metadata": {"kind": "market_order", "order_id": order.order_id},
        "payment_intent_data": {
            "transfer_group": order.order_id,
            "metadata": {"kind": "market_order", "order_id": order.order_id},
        },
    }
    try:
        session = gw.create_checkout(params)
    except Exception:  # provider or network failure: nothing was charged
        log.exception("market checkout failed for %s", order.order_id)
        raise _provider_error()
    order.checkout_session = session["id"]
    db.add(order)
    db.commit()
    return session["url"]


def refresh(db: Session, order: MarketOrder) -> MarketOrder:
    """Ask Stripe for the session's real state (the buyer just came back:
    covers a webhook that never arrived while the server was off)."""
    if order.state == "awaiting_payment" and order.checkout_session and enabled():
        try:
            session = gateway().retrieve_session(order.checkout_session)
        except Exception:
            log.exception("checkout refresh failed for %s", order.order_id)
            return order
        if session.get("payment_status") == "paid":
            mark_paid(db, order, session.get("payment_intent"))
    return order


def handle_webhook(db: Session, payload: bytes, signature: str) -> str:
    """Verify and apply a Stripe event. Raises ValueError when unsigned."""
    event = gateway().construct_event(payload, signature)
    kind = event["type"]
    obj = event["data"]["object"]
    if kind in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        meta = obj.get("metadata") or {}
        order_id = meta.get("order_id") or obj.get("client_reference_id")
        order = db.get(MarketOrder, order_id) if meta.get("kind") == "market_order" and order_id else None
        if order is not None and obj.get("payment_status") == "paid" and obj.get("id") == order.checkout_session:
            mark_paid(db, order, obj.get("payment_intent"))
    elif kind == "account.updated":
        supplier = db.scalar(select(Supplier).where(Supplier.connect_account_id == obj.get("id")))
        if supplier is not None:
            caps = obj.get("capabilities") or {}
            supplier.connect_ready = bool(obj.get("payouts_enabled")) and caps.get("transfers") == "active"
            db.add(supplier)
            db.commit()
    return kind


# --- Transfers and refunds ----------------------------------------------------------------


def run_transfers(db: Session, at: datetime) -> int:
    """After a supplier accepts a paid order: transfer its part minus the
    commission, and accrue the commission."""
    rows = db.execute(
        select(MarketOrderSupplier, MarketOrder)
        .join(MarketOrder, MarketOrder.order_id == MarketOrderSupplier.order_id)
        .where(
            MarketOrder.kind == "order",
            MarketOrder.payment == "platform",
            MarketOrder.payment_intent.is_not(None),
            MarketOrderSupplier.state.in_(("accepted", "shipped", "delivered")),
            MarketOrderSupplier.transfer_id.is_(None),
        )
    ).tuples()
    n = 0
    for group, order in list(rows):
        supplier = db.get(Supplier, group.supplier_id)
        if supplier is None or not supplier.connect_account_id:
            log.warning("no Connect account for supplier %s (order %s)", group.supplier_id, order.order_id)
            continue
        rate, base, commission = commissions.compute(db, order, group, supplier)
        amount = max(group.total - commission, 0)
        try:
            transfer_id = gateway().transfer(
                amount=amount,
                currency=order.currency,
                destination=supplier.connect_account_id,
                transfer_group=order.order_id,
                key=f"tbx-transfer-{order.order_id}-{group.supplier_id}",
                metadata={"order_id": order.order_id, "supplier_id": group.supplier_id},
            )
        except Exception:
            log.exception("transfer failed for %s / %s", order.order_id, group.supplier_id)
            continue
        group.transfer_id, group.transfer_amount = transfer_id, amount
        group.commission_bp, group.commission = rate, commission
        db.add(group)
        commissions.accrue(db, order, group, rate, base, commission)
        db.commit()
        n += 1
    return n


def refund_part(db: Session, order: MarketOrder, group: MarketOrderSupplier) -> None:
    try:
        group.refund_id = gateway().refund(
            payment_intent=order.payment_intent,
            amount=group.total,
            key=f"tbx-refund-{order.order_id}-{group.supplier_id}",
            metadata={"order_id": order.order_id, "supplier_id": group.supplier_id},
        )
    except Exception:
        log.exception("refund failed for %s / %s", order.order_id, group.supplier_id)
        raise _provider_error()
    commissions.void(db, order.order_id, group.supplier_id)
    db.add(group)


def refund_order(db: Session, order: MarketOrder) -> None:
    if not order.payment_intent:
        return
    try:
        refund_id = gateway().refund(
            payment_intent=order.payment_intent,
            amount=None,
            key=f"tbx-refund-{order.order_id}",
            metadata={"order_id": order.order_id},
        )
    except Exception:
        log.exception("refund failed for %s", order.order_id)
        raise _provider_error()
    for g in _groups(db, order.order_id):
        g.refund_id = refund_id
        db.add(g)


# --- Stripe Connect onboarding (PF8's portal calls this) ------------------------------------


def onboarding_link(db: Session, supplier: Supplier, refresh_url: str, return_url: str) -> str:
    if not get_settings().stripe_secret_key:
        raise ContractError("unavailable", 503, "Stripe is not configured on this server.")
    gw = gateway()
    try:
        if not supplier.connect_account_id:
            supplier.connect_account_id = gw.create_account(supplier)
            supplier.connect_ready = False
            db.add(supplier)
            db.commit()
        return gw.account_link(supplier.connect_account_id, refresh_url, return_url)
    except ContractError:
        raise
    except Exception:
        log.exception("Connect onboarding failed for %s", supplier.supplier_id)
        raise _provider_error()
