"""Shared helpers for the marketplace tests (PF7, contract marketplace-api)."""

import hashlib
import hmac
import io
import json
import time
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.market import seed
from app.market.catalogue import create_supplier, set_supplier_regions
from app.market.models import Product, ProductVariant, VariantAvailability, VariantPrice
from app.market.taxonomy import active_regions
from app.models import User

from .conftest import signup
from .licence_helpers import activated

FIXTURES = Path(__file__).parent / "contracts" / "marketplace"
CONTRACT = {"X-Truebex-Contract": "marketplace-api/1.1"}
PRODUCTS = json.loads((FIXTURES / "products.json").read_text(encoding="utf-8"))
SUPPLIER_ID = PRODUCTS["supplier"]["supplier_id"]
PRODUCT = {p["sku"]: p for p in PRODUCTS["products"]}
SOFA = PRODUCT["SOFA-OSLO-3"]
AKER = PRODUCT["TABLE-AKER-CT"]
FJORD = PRODUCT["TABLE-FJORD-CT"]
PAINT = PRODUCT["PAINT-CHALK"]
WEBHOOK_SECRET = "whsec_market_test"


def load(*, payments_ready: bool = False) -> str:
    with SessionLocal() as db:
        seed.load_fixture(db, FIXTURES, payments_ready=payments_ready)
    return SUPPLIER_ID


def with_contract(headers: dict | None = None) -> dict:
    return {**CONTRACT, **(headers or {})}


def make_admin(client, email: str = "admin@example.com") -> dict:
    h = signup(client, email=email)
    with SessionLocal() as db:
        db.scalar(select(User).where(User.email == email)).is_admin = True
        db.commit()
    return h


def device_token(client, headers: dict) -> dict:
    """A device credential for the same account (the app's 5.7-5.10 caller)."""
    token = activated(client, headers)["device_token"]
    return {"Authorization": f"Bearer {token}", **CONTRACT}


def payments_on(monkeypatch) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "market_payments_enabled", True)
    monkeypatch.setattr(s, "stripe_connect_webhook_secret", WEBHOOK_SECRET)


def second_supplier(*, ready: bool = False, region: str = "AE") -> str:
    """A second verified supplier with one in-stock armchair priced in `region`."""
    with SessionLocal() as db:
        s = create_supplier(
            db, name="Dune Interiors", country="AE", status="verified",
            connect_account_id="acct_dune" if ready else None, connect_ready=ready,
        )  # fmt: skip
        regions = active_regions(db)
        set_supplier_regions(db, s, {region: regions[region]})
        p = Product(
            product_id=hashlib.sha256(b"dune chair").hexdigest()[:32], supplier_id=s.supplier_id, sku="DUNE-ARM",
            name="Dune armchair", kind="object", category="furniture/seating/armchairs", description="",
            images=[], includes=[], status="approved",
        )  # fmt: skip
        from app.market.common import now

        p.approved_at = now()
        db.add(p)
        db.flush()
        db.add(ProductVariant(product_id=p.product_id, variant_id="sand", options={"colour": "Sand"}, materials=[], images=[], dims_mm=[800, 780, 820]))
        r = regions[region]
        db.add(
            VariantPrice(
                product_id=p.product_id, variant_id="sand", region=region, amount=210000, currency=r.currency,
                exponent=r.exponent, includes_tax=True, tax_rate_bp=r.tax_rate_bp, delivery_fee=10000,
                delivery_days_min=3, delivery_days_max=5,
            )
        )  # fmt: skip
        db.add(VariantAvailability(product_id=p.product_id, variant_id="sand", region=region, state="in_stock", stock=5))
        from app.market.search import reindex

        db.flush()
        reindex(db, p, s)
        db.commit()
        return s.supplier_id


def order_body(kind: str = "order", region: str = "AE", lines: list | None = None) -> dict:
    return {
        "kind": kind,
        "region": region,
        "project": {"name": "House", "project_id": None},
        "contact": {"name": "Layla Haddad", "email": "buyer@example.com", "phone": None, "message": "After 1 Dec"},
        "delivery": {"country": region, "city": "Dubai", "postcode": None},
        "lines": lines
        or [{"supplier_id": SUPPLIER_ID, "sku": "SOFA-OSLO-3", "variant_id": "oat-linen", "qty": 1}],
    }


def line(sku: str, variant: str, qty: int = 1, supplier: str = SUPPLIER_ID, seen: dict | None = None) -> dict:
    out = {"supplier_id": supplier, "sku": sku, "variant_id": variant, "qty": qty}
    if seen is not None:
        out["price_seen"] = seen
    return out


def stripe_post(client, event: dict, secret: str = WEBHOOK_SECRET):
    payload = json.dumps(event)
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return client.post(
        "/market/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": f"t={ts},v1={sig}", "Content-Type": "application/json"},
    )


def png(size=(640, 640), colour=(200, 40, 40), stripe=None) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", size, colour)
    if stripe:
        ImageDraw.Draw(img).rectangle([0, 0, size[0] // 2, size[1]], fill=stripe)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


class FakeGateway:
    """Stripe stand-in: records every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.sessions: dict[str, dict] = {}

    def create_checkout(self, params: dict) -> dict:
        sid = f"cs_test_{len(self.sessions) + 1}"
        self.sessions[sid] = {"id": sid, "url": f"https://checkout.stripe.test/{sid}", "status": "open", "payment_status": "unpaid"}
        self.calls.append(("checkout", params))
        return {"id": sid, "url": self.sessions[sid]["url"]}

    def retrieve_session(self, session_id: str) -> dict:
        return self.sessions[session_id]

    def transfer(self, **kw) -> str:
        self.calls.append(("transfer", kw))
        return f"tr_{len(self.calls)}"

    def refund(self, **kw) -> str:
        self.calls.append(("refund", kw))
        return f"re_{len(self.calls)}"

    def construct_event(self, payload: bytes, signature: str) -> dict:
        from app.market.checkout import StripeGateway

        return StripeGateway().construct_event(payload, signature)

    def create_account(self, supplier) -> str:
        return "acct_new"

    def account_link(self, account_id, refresh_url, return_url) -> str:
        return f"https://connect.stripe.test/{account_id}"
