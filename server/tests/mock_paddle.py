"""A small stand-in for Paddle Billing's API, for tests and for clicking
through checkout locally without a Paddle account.

    .venv/Scripts/python.exe -m uvicorn tests.mock_paddle:app --port 8098

Then, in server/.env: BILLING_PROVIDER=paddle, PADDLE_API_BASE=http://127.0.0.1:8098,
any PADDLE_API_KEY, and PADDLE_WEBHOOK_SECRET=pdl_ntfset_mock_secret (or set
MOCK_PADDLE_WEBHOOK_SECRET to match yours). Run scripts/sync_prices.py after
the mock starts (its state lives in memory).

Unlike real Paddle, a transaction's checkout URL opens the mock's own pay
page (no Paddle.js): "Pay with a test card" (with the buyer's country and an
optional business purchase) completes the transaction, starts the
subscription, sends signed webhooks to MOCK_PADDLE_WEBHOOK_URL and redirects
back to the billing page. The customer portal can cancel at the end of the
period; seat and plan changes add a prorated invoice.

PF2b: `POST /subscriptions/{id}/cancel` (at the period end or immediately),
`POST /adjustments` (refunds, full or partial), `renew(sub_id)` (a renewal
charge and the next period, as Paddle bills it; also `POST /mock/renew/{id}`
for clicking through) and the buyer's address
(`GET /customers/{id}/addresses/{id}`). Every event the mock makes is kept in
STATE["sent"], so tests can deliver what an API call caused.
"""

import calendar
import hashlib
import hmac
import html
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

app = FastAPI(title="Mock Paddle")

WEBHOOK: dict[str, Any] = {
    "url": os.environ.get("MOCK_PADDLE_WEBHOOK_URL", "http://127.0.0.1:8000/billing/webhooks/paddle"),
    "secret": os.environ.get("MOCK_PADDLE_WEBHOOK_SECRET", "pdl_ntfset_mock_secret"),
    # Tests switch this off and post the events themselves.
    "send": True,
}

# "page": checkout URLs open the mock's pay page (clicking through locally);
# "paddle": they are `<checkout.url>?_ptxn=txn_…` as real Paddle answers (tests).
CHECKOUT: dict[str, str] = {"style": os.environ.get("MOCK_PADDLE_CHECKOUT", "page")}

# Mock VAT rate applied on top of the price (tax-exclusive prices).
VAT_PERCENT = 20

STATE: dict[str, Any] = {}


def reset() -> None:
    STATE.clear()
    STATE.update(
        customers={},
        products={},
        prices={},
        transactions={},
        subscriptions={},
        charges=[],
        requests=[],
        addresses={},
        cancels=[],
        adjustments=[],
        # Every webhook event made, newest last (sent or not).
        sent=[],
        invoice_seq=0,
        discounts={
            "dsc_launch10": {
                "id": "dsc_launch10",
                "status": "active",
                "code": "LAUNCH10",
                "type": "percentage",
                "amount": "10",
                "enabled_for_checkout": True,
                "recur": True,
            }
        },
    )


reset()


# --- helpers -------------------------------------------------------------------------


def _id(prefix: str) -> str:
    return f"{prefix}_01{secrets.token_hex(12)}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ts(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ") if dt else None


def _add_interval(dt: datetime, interval: str, frequency: int = 1) -> datetime:
    if interval == "year":
        months = 12 * frequency
    elif interval == "month":
        months = frequency
    else:
        return dt + timedelta(days=7 * frequency if interval == "week" else frequency)
    month = dt.month - 1 + months
    year, month = dt.year + month // 12, month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _error(status: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        {"error": {"type": "request_error", "code": code, "detail": detail}}, status_code=status
    )


def _ok(data: Any, status: int = 200) -> JSONResponse:
    return JSONResponse({"data": data, "meta": {"request_id": _id("req")}}, status_code=status)


def _list(rows: list) -> JSONResponse:
    return JSONResponse(
        {
            "data": rows,
            "meta": {
                "request_id": _id("req"),
                "pagination": {"per_page": 200, "next": None, "has_more": False, "estimated_total": len(rows)},
            },
        }
    )


def sign(secret: str, body: bytes, ts: int | None = None) -> str:
    ts = int(time.time()) if ts is None else ts
    h1 = hmac.new(secret.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h1}"


def event(kind: str, data: dict, occurred_at: datetime | None = None) -> dict:
    return {
        "event_id": _id("evt"),
        "event_type": kind,
        "occurred_at": _ts(occurred_at or _now()),
        "notification_id": _id("ntf"),
        "data": json.loads(json.dumps(data)),
    }


def _send(events: list[dict]) -> None:
    STATE["sent"].extend(events)
    if not WEBHOOK["send"] or not WEBHOOK["url"]:
        return
    for ev in events:
        body = json.dumps(ev).encode()
        try:
            httpx.post(
                WEBHOOK["url"],
                content=body,
                headers={"Paddle-Signature": sign(WEBHOOK["secret"], body), "Content-Type": "application/json"},
                timeout=10,
            )
        except httpx.HTTPError:
            pass  # the billing page's refresh and the reconcile job cover a miss


def _site(txn: dict) -> str:
    url = str((txn.get("checkout") or {}).get("return") or "http://127.0.0.1:3100/checkout/")
    return url.split("/checkout/")[0]


def _totals(items: list[dict], currency: str, discount: dict | None) -> dict:
    subtotal = sum(int(i["price"]["unit_price"]["amount"]) * int(i["quantity"]) for i in items)
    off = subtotal * int(discount["amount"]) // 100 if discount and discount["type"] == "percentage" else 0
    tax = (subtotal - off) * VAT_PERCENT // 100
    grand = subtotal - off + tax
    return {
        "subtotal": str(subtotal),
        "discount": str(off),
        "tax": str(tax),
        "total": str(grand),
        "grand_total": str(grand),
        "credit": "0",
        "balance": str(grand),
        "fee": None,
        "earnings": None,
        "currency_code": currency,
    }


def _line_items(items: list[dict], currency: str) -> list[dict]:
    out = []
    for item in items:
        totals = _totals([item], currency, None)
        out.append(
            {
                "id": _id("txnitm"),
                "price_id": item["price"].get("id"),
                "quantity": item["quantity"],
                "totals": {"subtotal": totals["subtotal"], "tax": totals["tax"], "total": totals["total"]},
            }
        )
    return out


def _next_invoice_number() -> str:
    STATE["invoice_seq"] += 1
    return f"{_now().year}-{STATE['invoice_seq']:05d}"


def _bill(txn: dict) -> None:
    txn["status"] = "completed"
    txn["billed_at"] = _ts(_now())
    txn["updated_at"] = txn["billed_at"]
    txn["invoice_id"] = _id("inv")
    txn["invoice_number"] = _next_invoice_number()


def _auth(request: Request) -> JSONResponse | None:
    STATE["requests"].append(
        {"method": request.method, "path": request.url.path, "query": dict(request.query_params)}
    )
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer ") or len(header) < 10:
        return _error(403, "forbidden", "missing API key")
    return None


# --- customers -----------------------------------------------------------------------


@app.post("/customers")
async def create_customer(request: Request):
    if (denied := _auth(request)) is not None:
        return denied
    body = await request.json()
    email = str(body.get("email", "")).lower()
    for cust in STATE["customers"].values():
        if cust["email"] == email:
            return _error(409, "customer_already_exists", f"customer email conflicts with customer of id {cust['id']}")
    cust = {"id": _id("ctm"), "email": email, "name": body.get("name"), "status": "active"}
    STATE["customers"][cust["id"]] = cust
    return _ok(cust, 201)


@app.get("/customers")
def list_customers(request: Request, email: str = ""):
    if (denied := _auth(request)) is not None:
        return denied
    return _list([c for c in STATE["customers"].values() if not email or c["email"] == email.lower()])


@app.post("/customers/{customer_id}/portal-sessions")
async def portal_session(customer_id: str, request: Request):
    if (denied := _auth(request)) is not None:
        return denied
    if customer_id not in STATE["customers"]:
        return _error(404, "entity_not_found", "customer not found")
    base = str(request.base_url).rstrip("/")
    return _ok(
        {
            "id": _id("cpls"),
            "customer_id": customer_id,
            "urls": {"general": {"overview": f"{base}/portal/{customer_id}"}, "subscriptions": []},
            "created_at": _ts(_now()),
        },
        201,
    )


# --- catalogue ---------------------------------------------------------------------------


@app.get("/products")
def list_products(request: Request, status: str = ""):
    if (denied := _auth(request)) is not None:
        return denied
    return _list([p for p in STATE["products"].values() if not status or p["status"] == status])


@app.post("/products")
async def create_product(request: Request):
    if (denied := _auth(request)) is not None:
        return denied
    body = await request.json()
    product = {
        "id": _id("pro"),
        "name": body["name"],
        "tax_category": body.get("tax_category", "standard"),
        "description": body.get("description"),
        "custom_data": body.get("custom_data"),
        "status": "active",
    }
    STATE["products"][product["id"]] = product
    return _ok(product, 201)


@app.get("/prices")
def list_prices(request: Request, product_id: str = "", status: str = ""):
    if (denied := _auth(request)) is not None:
        return denied
    rows = [
        p
        for p in STATE["prices"].values()
        if (not product_id or p["product_id"] == product_id) and (not status or p["status"] == status)
    ]
    return _list(rows)


@app.post("/prices")
async def create_price(request: Request):
    if (denied := _auth(request)) is not None:
        return denied
    body = await request.json()
    if body.get("product_id") not in STATE["products"]:
        return _error(400, "product_not_found", "product not found")
    price = {
        "id": _id("pri"),
        "product_id": body["product_id"],
        "description": body.get("description"),
        "name": body.get("name"),
        "unit_price": body["unit_price"],
        "billing_cycle": body.get("billing_cycle"),
        "tax_mode": body.get("tax_mode", "account_setting"),
        "quantity": body.get("quantity") or {"minimum": 1, "maximum": 100},
        "custom_data": body.get("custom_data"),
        "status": "active",
    }
    STATE["prices"][price["id"]] = price
    return _ok(price, 201)


@app.get("/discounts")
def list_discounts(request: Request, code: str = "", status: str = ""):
    if (denied := _auth(request)) is not None:
        return denied
    rows = [
        d
        for d in STATE["discounts"].values()
        if (not code or d["code"].lower() == code.lower()) and (not status or d["status"] == status)
    ]
    return _list(rows)


# --- transactions ---------------------------------------------------------------------------


def _items(raw: list[dict]) -> list[dict] | JSONResponse:
    items = []
    for item in raw:
        price = STATE["prices"].get(item.get("price_id"))
        if price is None:
            return _error(400, "transaction_price_not_found", f"price {item.get('price_id')} not found")
        quantity = int(item.get("quantity") or 1)
        limits = price.get("quantity") or {}
        if not limits.get("minimum", 1) <= quantity <= limits.get("maximum", 100):
            return _error(400, "transaction_item_quantity_out_of_range", "quantity out of range")
        items.append({"price": price, "price_id": price["id"], "quantity": quantity, "status": "active"})
    return items


@app.post("/transactions")
async def create_transaction(request: Request):
    if (denied := _auth(request)) is not None:
        return denied
    body = await request.json()
    items = _items(body.get("items") or [])
    if isinstance(items, JSONResponse):
        return items
    if body.get("customer_id") and body["customer_id"] not in STATE["customers"]:
        return _error(400, "customer_not_found", "customer not found")
    currency = body.get("currency_code") or items[0]["price"]["unit_price"]["currency_code"]
    discount = STATE["discounts"].get(body.get("discount_id") or "")
    if body.get("discount_id") and discount is None:
        return _error(400, "transaction_discount_not_found", "discount not found")
    txn_id = _id("txn")
    base = str(request.base_url).rstrip("/")
    now = _ts(_now())
    back = (body.get("checkout") or {}).get("url")
    if CHECKOUT["style"] == "paddle" and back:
        url = f"{back}?_ptxn={txn_id}"
    else:
        url = f"{base}/pay/{txn_id}"
    txn = {
        "id": txn_id,
        "status": "ready",
        "customer_id": body.get("customer_id"),
        "currency_code": currency,
        "collection_mode": body.get("collection_mode", "automatic"),
        "custom_data": body.get("custom_data"),
        "discount_id": body.get("discount_id"),
        "items": items,
        "details": {"totals": _totals(items, currency, discount), "line_items": _line_items(items, currency)},
        "checkout": {"url": url, "return": back},
        "address_id": None,
        "business_id": None,
        "subscription_id": None,
        "invoice_id": None,
        "invoice_number": None,
        "origin": "api",
        "billed_at": None,
        "created_at": now,
        "updated_at": now,
    }
    STATE["transactions"][txn_id] = txn
    return _ok(txn, 201)


@app.get("/transactions")
def list_transactions(
    request: Request, customer_id: str = "", status: str = "", subscription_id: str = "", origin: str = ""
):
    if (denied := _auth(request)) is not None:
        return denied
    wanted = {s for s in status.split(",") if s}
    origins = {o for o in origin.split(",") if o}
    rows = [
        t
        for t in STATE["transactions"].values()
        if (not customer_id or t["customer_id"] == customer_id)
        and (not wanted or t["status"] in wanted)
        and (not subscription_id or t.get("subscription_id") == subscription_id)
        and (not origins or t.get("origin") in origins)
    ]
    rows.sort(key=lambda t: t.get("billed_at") or t["created_at"], reverse=True)
    return _list(rows)


@app.get("/transactions/{txn_id}")
def get_transaction(txn_id: str, request: Request, include: str = ""):
    if (denied := _auth(request)) is not None:
        return denied
    txn = STATE["transactions"].get(txn_id)
    if txn is None:
        return _error(404, "entity_not_found", "transaction not found")
    if "address" in include.split(",") and txn.get("address_id"):
        return _ok({**txn, "address": STATE["addresses"].get(txn["address_id"])})
    return _ok(txn)


@app.get("/customers/{customer_id}/addresses/{address_id}")
def get_address(customer_id: str, address_id: str, request: Request):
    if (denied := _auth(request)) is not None:
        return denied
    address = STATE["addresses"].get(address_id)
    if address is None or address["customer_id"] != customer_id:
        return _error(404, "entity_not_found", "address not found")
    return _ok(address)


@app.patch("/transactions/{txn_id}")
async def update_transaction(txn_id: str, request: Request):
    if (denied := _auth(request)) is not None:
        return denied
    txn = STATE["transactions"].get(txn_id)
    if txn is None:
        return _error(404, "entity_not_found", "transaction not found")
    body = await request.json()
    if body.get("status") == "canceled":
        if txn["status"] not in ("draft", "ready"):
            return _error(400, "transaction_immutable", "transaction can no longer be changed")
        txn["status"] = "canceled"
        txn["updated_at"] = _ts(_now())
    return _ok(txn)


@app.get("/transactions/{txn_id}/invoice")
def get_invoice(txn_id: str, request: Request):
    if (denied := _auth(request)) is not None:
        return denied
    txn = STATE["transactions"].get(txn_id)
    if txn is None:
        return _error(404, "entity_not_found", "transaction not found")
    if not txn.get("invoice_number"):
        return _error(400, "transaction_not_billed", "no invoice yet")
    base = str(request.base_url).rstrip("/")
    return _ok({"url": f"{base}/invoices/{txn_id}.pdf"})


# --- subscriptions ------------------------------------------------------------------------------


def _subscription_from(txn: dict) -> dict:
    first = txn["items"][0]["price"]
    cycle = first.get("billing_cycle") or {"interval": "month", "frequency": 1}
    start = _now()
    sub = {
        "id": _id("sub"),
        "status": "active",
        "customer_id": txn["customer_id"],
        "currency_code": txn["currency_code"],
        "custom_data": txn.get("custom_data"),
        "items": [dict(i) for i in txn["items"]],
        "billing_cycle": cycle,
        "current_billing_period": {
            "starts_at": _ts(start),
            "ends_at": _ts(_add_interval(start, cycle["interval"], cycle.get("frequency", 1))),
        },
        "next_billed_at": None,
        "scheduled_change": None,
        "discount": {"id": txn["discount_id"]} if txn.get("discount_id") else None,
        "created_at": _ts(start),
        "updated_at": _ts(start),
        "canceled_at": None,
    }
    sub["next_billed_at"] = sub["current_billing_period"]["ends_at"]
    return sub


def pay(txn_id: str, country: str = "GB", business: bool = False) -> list[dict]:
    """Complete a transaction as a buyer in `country` would (a business
    purchase adds a business with a tax id). Returns the webhook events
    (sent too when WEBHOOK["send"])."""
    txn = STATE["transactions"][txn_id]
    address = {
        "id": _id("add"),
        "customer_id": txn["customer_id"],
        "country_code": country.upper(),
        "postal_code": None,
        "status": "active",
    }
    STATE["addresses"][address["id"]] = address
    txn["address_id"] = address["id"]
    if business:
        txn["business_id"] = _id("biz")
    _bill(txn)
    sub = _subscription_from(txn)
    STATE["subscriptions"][sub["id"]] = sub
    txn["subscription_id"] = sub["id"]
    events = [event("transaction.completed", txn), event("subscription.created", sub)]
    _send(events)
    return events


def cancel_at_period_end(sub_id: str) -> list[dict]:
    sub = STATE["subscriptions"][sub_id]
    sub["scheduled_change"] = {
        "action": "cancel",
        "effective_at": sub["current_billing_period"]["ends_at"],
        "resume_at": None,
    }
    sub["updated_at"] = _ts(_now())
    events = [event("subscription.updated", sub)]
    _send(events)
    return events


def renew(sub_id: str) -> list[dict]:
    """Bill the next period now, as Paddle does at a renewal: a completed
    `subscription_recurring` transaction and the subscription moved one
    period on. Returns the events (sent too when WEBHOOK["send"])."""
    sub = STATE["subscriptions"][sub_id]
    cycle = sub.get("billing_cycle") or {"interval": "month", "frequency": 1}
    period = sub["current_billing_period"]
    start = datetime.fromisoformat(period["ends_at"].replace("Z", "+00:00"))
    end = _add_interval(start, cycle["interval"], cycle.get("frequency", 1))
    items = [dict(i) for i in sub["items"]]
    txn = {
        "id": _id("txn"),
        "status": "ready",
        "customer_id": sub["customer_id"],
        "currency_code": sub["currency_code"],
        "collection_mode": "automatic",
        "custom_data": sub.get("custom_data"),
        "discount_id": None,
        "items": items,
        "details": {
            "totals": _totals(items, sub["currency_code"], None),
            "line_items": _line_items(items, sub["currency_code"]),
        },
        "checkout": None,
        "subscription_id": sub_id,
        "billing_period": {"starts_at": _ts(start), "ends_at": _ts(end)},
        "origin": "subscription_recurring",
        "address_id": None,
        "business_id": None,
        "created_at": _ts(_now()),
        "updated_at": _ts(_now()),
    }
    _bill(txn)
    STATE["transactions"][txn["id"]] = txn
    sub["current_billing_period"] = {"starts_at": _ts(start), "ends_at": _ts(end)}
    sub["next_billed_at"] = _ts(end)
    sub["updated_at"] = _ts(_now())
    events = [event("transaction.completed", txn), event("subscription.updated", sub)]
    _send(events)
    return events


def cancel_now(sub_id: str) -> list[dict]:
    sub = STATE["subscriptions"][sub_id]
    sub["status"] = "canceled"
    sub["scheduled_change"] = None
    sub["current_billing_period"] = None
    sub["canceled_at"] = sub["updated_at"] = _ts(_now())
    events = [event("subscription.canceled", sub)]
    _send(events)
    return events


@app.get("/subscriptions/{sub_id}")
def get_subscription(sub_id: str, request: Request):
    if (denied := _auth(request)) is not None:
        return denied
    sub = STATE["subscriptions"].get(sub_id)
    return _ok(sub) if sub else _error(404, "entity_not_found", "subscription not found")


@app.patch("/subscriptions/{sub_id}")
async def update_subscription(sub_id: str, request: Request):
    if (denied := _auth(request)) is not None:
        return denied
    sub = STATE["subscriptions"].get(sub_id)
    if sub is None:
        return _error(404, "entity_not_found", "subscription not found")
    if sub["status"] == "canceled":
        return _error(400, "subscription_update_when_canceled", "subscription is canceled")
    body = await request.json()
    if "items" in body:
        items = _items(body["items"])
        if isinstance(items, JSONResponse):
            return items
        old = sum(int(i["price"]["unit_price"]["amount"]) * i["quantity"] for i in sub["items"])
        sub["items"] = items
        new = sum(int(i["price"]["unit_price"]["amount"]) * i["quantity"] for i in items)
        sub["billing_cycle"] = items[0]["price"].get("billing_cycle") or sub["billing_cycle"]
        if body.get("proration_billing_mode") == "prorated_immediately" and new > old:
            # Bill the difference for the rest of the period now.
            period = sub["current_billing_period"]
            start = datetime.fromisoformat(period["starts_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(period["ends_at"].replace("Z", "+00:00"))
            left = max(0.0, (end - _now()).total_seconds() / max(1.0, (end - start).total_seconds()))
            amount = int((new - old) * left)
            adjust = {
                "price": {
                    "id": None,
                    "description": "Prorated change",
                    "unit_price": {"amount": str(amount), "currency_code": sub["currency_code"]},
                },
                "quantity": 1,
            }
            txn = {
                "id": _id("txn"),
                "status": "completed",
                "customer_id": sub["customer_id"],
                "currency_code": sub["currency_code"],
                "custom_data": sub.get("custom_data"),
                "items": [adjust],
                "details": {"totals": _totals([adjust], sub["currency_code"], None)},
                "checkout": None,
                "subscription_id": sub_id,
                "origin": "subscription_update",
                "created_at": _ts(_now()),
                "billed_at": None,
            }
            _bill(txn)
            STATE["transactions"][txn["id"]] = txn
    if body.get("proration_billing_mode"):
        STATE.setdefault("prorations", []).append(body["proration_billing_mode"])
    sub["updated_at"] = _ts(_now())
    _send([event("subscription.updated", sub)])
    return _ok(sub)


@app.post("/subscriptions/{sub_id}/cancel")
async def cancel_subscription(sub_id: str, request: Request):
    if (denied := _auth(request)) is not None:
        return denied
    sub = STATE["subscriptions"].get(sub_id)
    if sub is None:
        return _error(404, "entity_not_found", "subscription not found")
    if sub["status"] == "canceled":
        return _error(400, "subscription_locked_canceled", "subscription is canceled")
    raw = await request.body()
    body = json.loads(raw) if raw else {}
    effective = body.get("effective_from") or "next_billing_period"
    if effective not in ("next_billing_period", "immediately"):
        return _error(400, "bad_request", "effective_from is invalid")
    STATE["cancels"].append({"subscription_id": sub_id, "effective_from": effective})
    if effective == "immediately":
        cancel_now(sub_id)
    else:
        cancel_at_period_end(sub_id)
    return _ok(sub)


@app.post("/adjustments")
async def create_adjustment(request: Request):
    if (denied := _auth(request)) is not None:
        return denied
    body = await request.json()
    txn = STATE["transactions"].get(body.get("transaction_id") or "")
    if txn is None:
        return _error(404, "entity_not_found", "transaction not found")
    if body.get("action") != "refund" or not body.get("reason"):
        return _error(400, "bad_request", "action refund and a reason are required")
    if txn["status"] not in ("completed", "paid"):
        return _error(400, "adjustment_transaction_not_completed", "transaction is not completed")
    kind = body.get("type") or "partial"
    grand = int(txn["details"]["totals"]["grand_total"])
    if kind == "full":
        total = grand
    else:
        lines = {li["id"]: li for li in txn["details"].get("line_items") or []}
        total = 0
        for item in body.get("items") or []:
            line = lines.get(item.get("item_id"))
            if line is None:
                return _error(400, "adjustment_invalid_item", "unknown transaction item")
            line_total = int(line["totals"]["total"])
            amount = line_total if item.get("type") == "full" else int(item.get("amount") or 0)
            if not 0 < amount <= line_total:
                return _error(400, "adjustment_amount_above_remaining_allowed", "amount out of range")
            total += amount
        if total <= 0:
            return _error(400, "bad_request", "a partial refund needs items")
    refunded = sum(a["totals"]["total"] for a in STATE["adjustments"] if a["transaction_id"] == txn["id"])
    if refunded + total > grand:
        return _error(400, "adjustment_total_amount_exceeds_transaction_total", "already refunded")
    adjustment = {
        "id": _id("adj"),
        "action": "refund",
        "type": kind,
        "transaction_id": txn["id"],
        "subscription_id": txn.get("subscription_id"),
        "customer_id": txn["customer_id"],
        "reason": body["reason"],
        "currency_code": txn["currency_code"],
        "status": "pending_approval",
        "items": body.get("items") or [],
        "totals": {"total": total, "currency_code": txn["currency_code"]},
        "created_at": _ts(_now()),
    }
    STATE["adjustments"].append(adjustment)
    _send([event("adjustment.created", adjustment)])
    return _ok({**adjustment, "totals": {"total": str(total), "currency_code": txn["currency_code"]}}, 201)


@app.post("/mock/renew/{sub_id}")
def renew_now(sub_id: str):
    """Click-through helper: bill the next period now (sends the webhooks).
    `latest` renews the newest active subscription."""
    if sub_id == "latest":
        active = [s for s in STATE["subscriptions"].values() if s["status"] == "active"]
        if not active:
            return _error(404, "entity_not_found", "no active subscription")
        sub_id = max(active, key=lambda s: s["created_at"])["id"]
    if sub_id not in STATE["subscriptions"]:
        return _error(404, "entity_not_found", "subscription not found")
    renew(sub_id)
    return _ok(STATE["subscriptions"][sub_id])


@app.post("/subscriptions/{sub_id}/charge")
async def charge(sub_id: str, request: Request):
    if (denied := _auth(request)) is not None:
        return denied
    sub = STATE["subscriptions"].get(sub_id)
    if sub is None:
        return _error(404, "entity_not_found", "subscription not found")
    body = await request.json()
    STATE["charges"].append({"subscription_id": sub_id, **body})
    return _ok(sub)


# --- pages a buyer sees ---------------------------------------------------------------------------


def _money(minor: str | int, currency: str) -> str:
    return f"{int(minor) / 100:,.2f} {currency}"


@app.get("/pay/{txn_id}", response_class=HTMLResponse)
def pay_page(txn_id: str):
    txn = STATE["transactions"].get(txn_id)
    if txn is None:
        return HTMLResponse("<h1>Unknown transaction</h1>", status_code=404)
    totals = txn["details"]["totals"]
    lines = "".join(
        f"<li>{html.escape(str(i['price'].get('description') or i['price']['id']))} &times; {i['quantity']}</li>"
        for i in txn["items"]
    )
    ref = html.escape(str((txn.get("custom_data") or {}).get("reference", "")))
    cancel = f"{_site(txn)}/dashboard/billing/?checkout=canceled&ref={ref}"
    return (
        "<!doctype html><title>Mock Paddle checkout</title>"
        "<body style='font-family:sans-serif;max-width:32rem;margin:3rem auto'>"
        f"<h1>Mock Paddle checkout</h1><ul>{lines}</ul>"
        f"<p>Subtotal {_money(totals['subtotal'], txn['currency_code'])}"
        f" &middot; discount {_money(totals['discount'], txn['currency_code'])}"
        f" &middot; VAT {VAT_PERCENT}% {_money(totals['tax'], txn['currency_code'])}</p>"
        f"<p><strong>Total {_money(totals['grand_total'], txn['currency_code'])}</strong></p>"
        f"<form method=post action='/pay/{txn_id}'>"
        "<p><label>Country <select name=country id=country>"
        "<option value=GB>United Kingdom</option><option value=DE>Germany</option>"
        "<option value=FR>France</option><option value=IE>Ireland</option>"
        "<option value=US>United States</option></select></label></p>"
        "<p><label><input type=checkbox name=business value=1 id=business> Business purchase (tax id)</label></p>"
        "<button id=pay>Pay with a test card</button></form>"
        f"<p><a href='{html.escape(cancel)}'>Cancel</a></p>"
    )


@app.post("/pay/{txn_id}")
async def pay_submit(txn_id: str, request: Request):
    txn = STATE["transactions"].get(txn_id)
    if txn is None:
        return HTMLResponse("<h1>Unknown transaction</h1>", status_code=404)
    form = parse_qs((await request.body()).decode())
    country = (form.get("country") or ["GB"])[0][:2] or "GB"
    if txn["status"] == "ready":
        pay(txn_id, country=country, business=bool(form.get("business")))
    ref = (txn.get("custom_data") or {}).get("reference", "")
    return RedirectResponse(f"{_site(txn)}/dashboard/billing/?checkout=success&ref={ref}", status_code=303)


@app.get("/portal/{customer_id}", response_class=HTMLResponse)
def portal_page(customer_id: str):
    subs = [s for s in STATE["subscriptions"].values() if s["customer_id"] == customer_id]
    rows = "".join(
        f"<li>{html.escape(s['id'])} &middot; {s['status']} &middot; seats "
        f"{sum(i['quantity'] for i in s['items'])}"
        + (" &middot; ends at period end" if s.get("scheduled_change") else "")
        + (
            f" <form method=post action='/portal/{customer_id}/cancel/{s['id']}' style='display:inline'>"
            "<button>Cancel at period end</button></form>"
            if s["status"] == "active" and not s.get("scheduled_change")
            else ""
        )
        + "</li>"
        for s in subs
    )
    return (
        "<!doctype html><title>Mock Paddle portal</title>"
        "<body style='font-family:sans-serif;max-width:40rem;margin:3rem auto'>"
        f"<h1>Mock Paddle customer portal</h1><ul>{rows or '<li>No subscriptions</li>'}</ul>"
    )


@app.post("/portal/{customer_id}/cancel/{sub_id}")
def portal_cancel(customer_id: str, sub_id: str):
    sub = STATE["subscriptions"].get(sub_id)
    if sub is None or sub["customer_id"] != customer_id:
        return HTMLResponse("<h1>Unknown subscription</h1>", status_code=404)
    cancel_at_period_end(sub_id)
    return RedirectResponse(f"/portal/{customer_id}", status_code=303)


def invoice_pdf_bytes(txn: dict) -> bytes:
    """A one-page PDF with the invoice number, seller, VAT line and total."""
    totals = txn["details"]["totals"]
    cur = txn["currency_code"]
    lines = [
        f"Invoice {txn['invoice_number']}",
        "Seller: Paddle.com Market Ltd, reseller for Truebex Ltd (mock)",
        f"Customer: {txn['customer_id']}",
        f"Subtotal: {_money(totals['subtotal'], cur)}",
        f"VAT {VAT_PERCENT}%: {_money(totals['tax'], cur)}",
        f"Total: {_money(totals['grand_total'], cur)}",
    ]
    text = "BT /F1 14 Tf 72 760 Td 20 TL " + " ".join(
        "(" + ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") Tj T*" for ln in lines
    ) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(text)} >>\nstream\n{text}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for n, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


@app.get("/invoices/{txn_id}.pdf")
def invoice_pdf(txn_id: str):
    txn = STATE["transactions"].get(txn_id)
    if txn is None or not txn.get("invoice_number"):
        return Response(status_code=404)
    return Response(invoice_pdf_bytes(txn), media_type="application/pdf")
