"""Billing that predates PF2: the dormant Wayl rail (run under WAYL_ENABLED so
it does not rot) and the Stripe webhook rules."""

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.billing import providers
from app.config import get_settings
from app.database import SessionLocal
from app.models import Subscription

from .conftest import checkout_body, signup

# --- Wayl (dormant) ---------------------------------------------------------------


class FakeWayl:
    """Stands in for api.thewayl.com via an httpx MockTransport."""

    def __init__(self):
        self.links: dict[str, dict] = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["X-WAYL-AUTHENTICATION"] == "wayl-test-key"
        if request.method == "POST" and request.url.path == "/api/v1/links":
            body = json.loads(request.content)
            ref = body["referenceId"]
            self.links[ref] = {**body, "status": "Created", "id": "wl_1", "total": str(body["total"])}
            return httpx.Response(201, json={"data": {"id": "wl_1", "url": f"https://pay.wayl.test/{ref}", "referenceId": ref}})
        if request.method == "GET" and request.url.path.startswith("/api/v1/links/"):
            ref = request.url.path.rsplit("/", 1)[1]
            return httpx.Response(200, json={"data": self.links[ref]})
        return httpx.Response(404)


@pytest.fixture()
def wayl_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "wayl_enabled", True)


def _patch_wayl(monkeypatch):
    fake = FakeWayl()

    def client(s):
        return httpx.Client(
            base_url=s.wayl_api_base,
            headers={"X-WAYL-AUTHENTICATION": s.wayl_api_key},
            transport=httpx.MockTransport(fake.handler),
        )

    monkeypatch.setattr(providers, "_wayl_client", client)
    return fake


def _wayl_body(tier="pro"):
    return checkout_body(tier=tier, currency="IQD", provider="wayl")


def test_no_client_side_plan_grant(client):
    h = signup(client)
    res = client.post("/billing/activate", json={"payment_id": "x", "plan": "pro"}, headers=h)
    assert res.status_code in (404, 405)


def test_wayl_checkout_and_verified_webhook(client, monkeypatch, wayl_on):
    fake = _patch_wayl(monkeypatch)
    h = signup(client)
    co = client.post("/billing/checkout", json=_wayl_body(), headers=h).json()
    ref = co["reference"]
    assert co["url"].endswith(ref)
    link = fake.links[ref]
    assert link["total"] == "130000" and link["currency"] == "IQD"
    assert link["webhookUrl"].endswith("/billing/webhooks/wayl")

    # A webhook claiming success while Wayl still says Created changes nothing.
    client.post("/billing/webhooks/wayl", json={"referenceId": ref, "status": "Complete"})
    assert client.get("/auth/me", headers=h).json()["plan"] == "free"

    fake.links[ref]["status"] = "Complete"
    r = client.post("/billing/webhooks/wayl", json={"referenceId": ref}).json()
    assert r == {"received": True, "status": "Complete"}
    assert client.get("/auth/me", headers=h).json()["plan"] == "pro"

    sub = client.get("/billing/subscription", headers=h).json()
    assert sub["provider"] == "wayl" and sub["status"] == "active"
    end = datetime.fromisoformat(sub["current_period_end"])
    assert timedelta(days=29) < end.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc) <= timedelta(days=30)

    # Replaying the webhook must not add a second month.
    client.post("/billing/webhooks/wayl", json={"referenceId": ref})
    assert client.get("/billing/subscription", headers=h).json()["current_period_end"] == sub["current_period_end"]

    pays = client.get("/billing/payments", headers=h).json()
    assert pays[0]["status"] == "paid" and pays[0]["currency"] == "IQD"


def test_wayl_unknown_reference_ignored(client, monkeypatch, wayl_on):
    _patch_wayl(monkeypatch)
    res = client.post("/billing/webhooks/wayl", json={"referenceId": "tbx_forged"})
    assert res.json() == {"received": False}


def test_wayl_refresh_after_redirect(client, monkeypatch, wayl_on):
    fake = _patch_wayl(monkeypatch)
    h = signup(client)
    ref = client.post("/billing/checkout", json=_wayl_body(), headers=h).json()["reference"]
    fake.links[ref]["status"] = "Delivered"
    paid = client.post(f"/billing/payments/{ref}/refresh", headers=h).json()
    assert paid["status"] == "paid"
    assert client.get("/auth/me", headers=h).json()["plan"] == "pro"


def test_cannot_buy_unpurchasable_plan(client, wayl_on):
    h = signup(client)
    res = client.post("/billing/checkout", json=_wayl_body("enterprise"), headers=h)
    assert res.status_code == 400


def test_wayl_off_without_flag(client, monkeypatch):
    _patch_wayl(monkeypatch)
    h = signup(client)
    assert client.post("/billing/webhooks/wayl", json={"referenceId": "x"}).status_code == 404
    assert client.post("/billing/checkout", json=_wayl_body(), headers=h).status_code == 503


def test_expired_period_falls_back_to_free(client):
    h = signup(client)
    uid = client.get("/auth/me", headers=h).json()["id"]
    with SessionLocal() as db:
        db.add(
            Subscription(
                user_id=uid,
                plan="pro",
                provider="wayl",
                status="active",
                current_period_end=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        db.commit()
    assert client.get("/auth/me", headers=h).json()["plan"] == "free"


# --- Stripe -------------------------------------------------------------------


def stripe_post(client, event: dict, secret="whsec_test_dummy"):
    payload = json.dumps(event)
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return client.post(
        "/billing/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": f"t={ts},v1={sig}", "Content-Type": "application/json"},
    )


_seq = iter(range(1, 1_000_000))


def stripe_sub_event(
    kind,
    uid,
    status,
    end,
    *,
    price="price_test_pro",
    quantity=1,
    created=None,
    meta=None,
    sub_id="sub_123",
    cancel_at_period_end=False,
    interval="month",
):
    return {
        "id": f"evt_{next(_seq)}",
        "object": "event",
        "type": kind,
        "created": created or int(time.time()),
        "data": {
            "object": {
                "id": sub_id,
                "object": "subscription",
                "customer": "cus_123",
                "currency": "gbp",
                "status": status,
                "cancel_at_period_end": cancel_at_period_end,
                "metadata": {"user_id": str(uid), "plan": "pro"} if meta is None else meta,
                "items": {
                    "data": [
                        {
                            "id": "si_1",
                            "quantity": quantity,
                            "current_period_end": end,
                            "price": {"id": price, "recurring": {"interval": interval}},
                        }
                    ]
                },
            }
        },
    }


def test_stripe_rejects_bad_signature(client):
    res = stripe_post(client, {"type": "x", "data": {"object": {}}}, secret="whsec_wrong")
    assert res.status_code == 400


def test_stripe_subscription_lifecycle(client):
    h = signup(client)
    uid = client.get("/auth/me", headers=h).json()["id"]
    end = int(time.time()) + 30 * 86400

    assert stripe_post(client, stripe_sub_event("customer.subscription.created", uid, "active", end)).status_code == 200
    assert client.get("/auth/me", headers=h).json()["plan"] == "pro"
    sub = client.get("/billing/subscription", headers=h).json()
    assert sub["provider"] == "stripe" and sub["can_manage"]

    stripe_post(client, stripe_sub_event("customer.subscription.deleted", uid, "canceled", end))
    assert client.get("/auth/me", headers=h).json()["plan"] == "free"
