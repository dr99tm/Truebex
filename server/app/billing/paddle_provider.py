"""Paddle Billing: the merchant of record for subscriptions (the default).

Paddle sells to the customer, charges VAT or sales tax, files it, issues the
invoice and handles chargebacks; Truebex Ltd sells to Paddle.

Flow on the static site: the server creates a transaction (the price id from
provider_prices, a quantity, the customer, `custom_data` naming the user and
our reference) and returns `/checkout/?_ptxn=txn_…&ref=…`; that page opens
Paddle.js's overlay; `refresh` fetches the transaction from Paddle's API and
signed webhooks do the rest. API: https://developer.paddle.com/api-reference
"""

import hashlib
import hmac
import json
import logging
import time
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Payment, ProviderPrice, Subscription, User
from . import service
from .base import (
    BillingProvider,
    Invoice,
    ProviderError,
    WebhookError,
    parse_time,
    str_or_none,
)

log = logging.getLogger("truebex.billing.paddle")

# Webhook timestamps older (or newer) than this are rejected.
SIGNATURE_TOLERANCE_S = 300

# Paddle subscription status -> ours.
_STATUS = {
    "active": "active",
    "trialing": "active",
    "past_due": "past_due",
    "paused": "paused",
    "canceled": "canceled",
}

_PAID = {"paid", "completed"}


class PaddleApiError(ProviderError):
    def __init__(self, status: int, code: str, detail: str):
        super().__init__(f"Paddle {status} {code}: {detail}")
        self.status = status
        self.code = code


def make_client(s: Settings) -> httpx.Client:
    return httpx.Client(
        base_url=s.paddle_api_url,
        headers={
            "Authorization": f"Bearer {s.paddle_api_key}",
            "Paddle-Version": "1",
        },
        timeout=30,
    )


def sign(secret: str, body: bytes, ts: int | None = None) -> str:
    """A `Paddle-Signature` header value for `body` (tests and the mock)."""
    ts = int(time.time()) if ts is None else ts
    h1 = hmac.new(secret.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h1}"


def verify_signature(secret: str, body: bytes, header: str, now: float | None = None) -> None:
    """HMAC-SHA256 over `ts:body`; raises WebhookError when it does not match
    or the timestamp is outside the tolerance window."""
    ts: int | None = None
    sigs: list[str] = []
    for part in (header or "").split(";"):
        key, _, value = part.strip().partition("=")
        if key == "ts" and value.isdigit():
            ts = int(value)
        elif key == "h1" and value:
            sigs.append(value)
    if ts is None or not sigs or not secret:
        raise WebhookError("missing Paddle signature")
    if abs((now or time.time()) - ts) > SIGNATURE_TOLERANCE_S:
        raise WebhookError("stale Paddle signature")
    expected = hmac.new(secret.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, s) for s in sigs):
        raise WebhookError("invalid Paddle signature")


def _header(headers: Mapping[str, str], name: str) -> str:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return ""


def _minor(value: Any) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


class PaddleProvider(BillingProvider):
    name = "paddle"

    def enabled(self) -> bool:
        s = self.settings
        return bool(s.paddle_api_key and s.paddle_webhook_secret)

    # --- HTTP -----------------------------------------------------------------

    def _api(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        from . import providers  # the registry; tests patch its client factory

        try:
            with providers._paddle_client(self.settings) as client:
                res = client.request(method, path, json=json_body, params=params)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Paddle unreachable: {exc}") from exc
        if res.status_code >= 400:
            try:
                err = res.json().get("error") or {}
            except ValueError:
                err = {}
            raise PaddleApiError(res.status_code, str(err.get("code", "")), str(err.get("detail", "")))
        return res.json()

    # --- Customers --------------------------------------------------------------

    def _customer_id(self, db: Session, user: User) -> str:
        known = service.customer_id(db, user, "paddle")
        if known:
            return known
        body: dict[str, Any] = {"email": user.email}
        if user.name:
            body["name"] = user.name
        try:
            return self._api("POST", "/customers", json_body=body)["data"]["id"]
        except PaddleApiError as exc:
            if exc.status != 409:
                raise
        rows = self._api("GET", "/customers", params={"email": user.email}).get("data") or []
        if not rows:
            raise ProviderError("Paddle reported the customer exists but did not list it")
        return rows[0]["id"]

    # --- Checkout -----------------------------------------------------------------

    def resolve_coupon(self, code: str) -> str | None:
        rows = self._api("GET", "/discounts", params={"code": code, "status": "active"}).get("data") or []
        for row in rows:
            if str(row.get("code", "")).lower() == code.lower():
                return row["id"]
        return None

    def create_checkout(
        self,
        db: Session,
        user: User,
        payment: Payment,
        price: ProviderPrice | None,
        seats: int,
        discount: str | None,
    ) -> str:
        if price is None:
            raise ProviderError("Paddle checkout needs a provider price")
        body: dict[str, Any] = {
            "items": [{"price_id": price.provider_price_id, "quantity": seats}],
            "customer_id": self._customer_id(db, user),
            "currency_code": payment.currency,
            "collection_mode": "automatic",
            "custom_data": {
                "user_id": str(user.id),
                "reference": payment.reference,
                "tier": payment.plan,
                "interval": payment.interval or "",
                "founding": "1" if service.is_founding_reference(db, payment.reference) else "0",
                # PF3 adds "org_id" for organisation-owned subscriptions.
            },
            "checkout": {"url": f"{self.settings.site_url}/checkout/"},
        }
        if discount:
            body["discount_id"] = discount
        data = self._api("POST", "/transactions", json_body=body)["data"]
        payment.provider_ref = data["id"]
        url = (data.get("checkout") or {}).get("url") or (
            f"{self.settings.site_url}/checkout/?_ptxn={data['id']}"
        )
        return f"{url}{'&' if '?' in url else '?'}ref={payment.reference}"

    # --- Applying Paddle state ------------------------------------------------------

    def _apply_transaction(self, db: Session, txn: dict) -> None:
        custom = txn.get("custom_data") or {}
        payment = None
        if custom.get("reference"):
            payment = db.scalar(
                select(Payment).where(
                    Payment.reference == str(custom["reference"]), Payment.provider == "paddle"
                )
            )
        if payment is None and txn.get("id"):
            payment = db.scalar(
                select(Payment).where(Payment.provider_ref == txn["id"], Payment.provider == "paddle")
            )
        if payment is None:
            return  # a renewal, or not created by our checkout
        status = str(txn.get("status", ""))
        if status in _PAID:
            totals = (txn.get("details") or {}).get("totals") or {}
            if totals.get("grand_total") is not None:
                payment.amount = _minor(totals.get("grand_total"))
                payment.tax_minor = _minor(totals.get("tax"))
            payment.invoice_id = str_or_none(txn.get("invoice_id")) or payment.invoice_id
            service.mark_payment_paid(db, payment)
            db.commit()
            service.consume_founding(db, payment, founding_hint=custom.get("founding") == "1")
        elif status == "canceled" and payment.status == "pending":
            payment.status = "canceled"
            db.add(payment)
            db.commit()

    def _apply_subscription(
        self, db: Session, sub: dict, event_at: datetime | None
    ) -> Subscription | None:
        custom = sub.get("custom_data") or {}
        existing = db.scalar(
            select(Subscription).where(
                Subscription.provider == "paddle",
                Subscription.provider_subscription_id == sub["id"],
            )
        )
        try:
            user_id = existing.user_id if existing else int(custom.get("user_id", ""))
        except ValueError:
            return None  # not created by our checkout
        items = [i for i in sub.get("items") or [] if i.get("status") != "inactive"]
        item = items[0] if items else {}
        price = item.get("price") or {}
        price_id = price.get("id") or item.get("price_id")
        row = service.price_by_provider_id(db, "paddle", price_id)
        cycle = price.get("billing_cycle") or sub.get("billing_cycle") or {}
        period = sub.get("current_billing_period") or {}
        scheduled = sub.get("scheduled_change") or {}
        return service.upsert_subscription(
            db,
            provider="paddle",
            provider_subscription_id=sub["id"],
            user_id=user_id,
            tier=row.tier if row else str(custom.get("tier") or "pro"),
            interval=row.interval if row else cycle.get("interval"),
            seats=int(item.get("quantity") or 1),
            status=_STATUS.get(str(sub.get("status", "")), "canceled"),
            current_period_end=parse_time(period.get("ends_at")),
            cancel_at_period_end=scheduled.get("action") == "cancel",
            customer_id=str_or_none(sub.get("customer_id")),
            currency=str_or_none(sub.get("currency_code")),
            provider_price_id=str_or_none(price_id),
            founding=custom.get("founding") == "1",
            event_at=event_at,
        )

    def _fetch_subscription(self, db: Session, sub_id: str) -> Subscription | None:
        data = self._api("GET", f"/subscriptions/{sub_id}")["data"]
        return self._apply_subscription(db, data, parse_time(data.get("updated_at")))

    def verify_payment(self, db: Session, payment: Payment) -> None:
        if not payment.provider_ref:
            return
        txn = self._api("GET", f"/transactions/{payment.provider_ref}")["data"]
        self._apply_transaction(db, txn)
        if txn.get("status") in _PAID and txn.get("subscription_id"):
            self._fetch_subscription(db, txn["subscription_id"])

    # --- Webhooks --------------------------------------------------------------------

    def handle_webhook(self, db: Session, body: bytes, headers: Mapping[str, str]) -> str | None:
        verify_signature(
            self.settings.paddle_webhook_secret, body, _header(headers, "Paddle-Signature")
        )
        try:
            event = json.loads(body)
            event_id = str(event["event_id"])
            kind = str(event["event_type"])
        except (ValueError, KeyError, TypeError) as exc:
            raise WebhookError("malformed Paddle event") from exc
        if service.event_seen(db, "paddle", event_id):
            return kind
        occurred = parse_time(event.get("occurred_at"))
        data = event.get("data") or {}
        status = "ignored"
        if kind.startswith("subscription."):
            applied = self._apply_subscription(db, data, occurred)
            status = "applied" if applied is not None else "stale"
        elif kind.startswith("transaction."):
            self._apply_transaction(db, data)
            status = "applied"
        service.record_event(db, "paddle", event_id, kind, occurred, status)
        return kind

    # --- Managing a subscription ----------------------------------------------------------

    def portal_url(self, db: Session, user: User, sub: Subscription) -> str:
        customer = sub.provider_customer_id or service.customer_id(db, user, "paddle")
        if not customer:
            raise ProviderError("no Paddle customer")
        body = {"subscription_ids": [sub.provider_subscription_id]} if sub.provider_subscription_id else {}
        data = self._api("POST", f"/customers/{customer}/portal-sessions", json_body=body)["data"]
        return data["urls"]["general"]["overview"]

    def _apply_change(
        self, db: Session, sub: Subscription, price: ProviderPrice, seats: int
    ) -> Subscription:
        data = self._api(
            "PATCH",
            f"/subscriptions/{sub.provider_subscription_id}",
            json_body={
                "items": [{"price_id": price.provider_price_id, "quantity": seats}],
                "proration_billing_mode": "prorated_immediately",
            },
        )["data"]
        applied = self._apply_subscription(db, data, parse_time(data.get("updated_at")))
        db.refresh(sub)
        return applied or sub

    def list_invoices(self, db: Session, user: User) -> list[Invoice]:
        customer = service.customer_id(db, user, "paddle")
        if not customer:
            return []
        rows = self._api(
            "GET",
            "/transactions",
            params={
                "customer_id": customer,
                "status": "billed,paid,completed",
                "order_by": "billed_at[DESC]",
                "per_page": 30,
            },
        ).get("data") or []
        out = []
        for txn in rows:
            if not txn.get("invoice_number"):
                continue
            totals = (txn.get("details") or {}).get("totals") or {}
            out.append(
                Invoice(
                    id=txn["id"],
                    number=txn.get("invoice_number"),
                    issued_at=parse_time(txn.get("billed_at") or txn.get("created_at")),
                    total_minor=_minor(totals.get("grand_total")),
                    tax_minor=_minor(totals.get("tax")),
                    currency=str(txn.get("currency_code") or "").upper(),
                    status=str(txn.get("status") or ""),
                    pdf_url=None,
                )
            )
        return out

    def invoice_pdf_url(self, db: Session, user: User, invoice_id: str) -> str:
        customer = service.customer_id(db, user, "paddle")
        txn = self._api("GET", f"/transactions/{invoice_id}")["data"]
        if not customer or txn.get("customer_id") != customer:
            raise ProviderError("not this customer's invoice")
        return self._api("GET", f"/transactions/{invoice_id}/invoice")["data"]["url"]

    def charge_usage(
        self,
        db: Session,
        sub: Subscription,
        metric: str,
        quantity: int,
        unit_amount_minor: int,
        description: str,
    ) -> str:
        data = self._api(
            "POST",
            f"/subscriptions/{sub.provider_subscription_id}/charge",
            json_body={
                "effective_from": "next_billing_period",
                "items": [
                    {
                        "quantity": quantity,
                        "price": {
                            "description": description,
                            "name": description,
                            "unit_price": {
                                "amount": str(unit_amount_minor),
                                "currency_code": sub.currency or "USD",
                            },
                            "product": {
                                "name": f"Truebex usage: {metric}",
                                "tax_category": "standard",
                            },
                        },
                    }
                ],
            },
        )["data"]
        return str(data.get("id") or sub.provider_subscription_id)

    def reconcile(self, db: Session, subs: list[Subscription], payments: list[Payment]) -> int:
        checked = 0
        for payment in payments:
            try:
                self.verify_payment(db, payment)
                checked += 1
            except ProviderError:
                log.exception("reconcile: payment %s", payment.reference)
        for sub in subs:
            if not sub.provider_subscription_id:
                continue
            try:
                self._fetch_subscription(db, sub.provider_subscription_id)
                checked += 1
            except ProviderError:
                log.exception("reconcile: subscription %s", sub.provider_subscription_id)
        return checked
