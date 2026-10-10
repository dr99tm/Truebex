"""Marketplace admin, reviews, the picture search and the fetch guard (PF7)."""

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.market import checkout, embeddings, media
from app.market.models import Product

from .conftest import signup
from .licence_helpers import error_of
from .market_helpers import (
    CONTRACT,
    FIXTURES,
    PAINT,
    SOFA,
    SUPPLIER_ID,
    FakeGateway,
    load,
    make_admin,
    order_body,
    payments_on,
    stripe_post,
    with_contract,
)

FEED_CSV = (FIXTURES / "feed-two-regions.csv").read_bytes()


def test_market_admin_approvals(client, monkeypatch):
    user = signup(client, email="user@example.com")
    # 401 without a session, 403 for a non-admin, on every admin area.
    for path in ("/admin/market/summary", "/admin/market/suppliers", "/admin/market/products", "/admin/market/reviews",
                 "/admin/market/orders", "/admin/market/commissions", "/admin/market/feeds"):  # fmt: skip
        error_of(client.get(path), 401, "unauthenticated")
        error_of(client.get(path, headers=user), 403, "forbidden")
    error_of(client.post(f"/admin/market/products/{'a' * 32}/approve", headers=user), 403, "forbidden")

    admin = make_admin(client)
    # A supplier applies (PF8's sign-up; the admin can create one too).
    res = client.post(
        "/admin/market/suppliers",
        json={"name": "Atlas Living", "country": "ae", "regions": ["AE", "GB"], "owner_email": "user@example.com",
              "website": "https://atlas.example.com", "contact_email": "sales@atlas.example.com"},
        headers=admin,
    )  # fmt: skip
    assert res.status_code == 201, res.text
    supplier = res.json()
    sid = supplier["supplier_id"]
    assert supplier["status"] == "applied" and supplier["country"] == "AE" and supplier["regions"] == ["AE", "GB"]
    assert supplier["members"] == [{"email": "user@example.com", "role": "owner", "user_id": supplier["members"][0]["user_id"]}]
    assert supplier["commission_bp"] == 1000 and supplier["orderable"] is False
    error_of(client.post("/admin/market/suppliers", json={"name": "X", "country": "GB", "regions": ["ZZ"]}, headers=admin), 422, "validation_failed")
    error_of(client.post("/admin/market/suppliers", json={"name": "X", "country": "GB", "owner_email": "nobody@example.com"}, headers=admin), 422, "validation_failed")
    error_of(client.get(f"/market/suppliers/{sid}", headers=CONTRACT), 404, "not_found")  # not verified yet

    # Its feed lands in the review queue.
    monkeypatch.setattr(media, "HttpFetcher", lambda: __import__("app.market.seed", fromlist=["x"]).media_fetcher(FIXTURES))
    res = client.post(
        "/admin/market/feeds", data={"supplier_id": sid, "format": "csv"},
        files={"file": ("feed.csv", FEED_CSV, "text/csv")}, headers=admin,
    )  # fmt: skip
    assert res.status_code == 201 and res.json()["created"] == 6
    queue = client.get("/admin/market/products", headers=admin).json()["products"]
    assert {p["sku"] for p in queue} == {"SOFA-OSLO-3", "CHAIR-BERGEN"} and all(p["status"] == "pending_review" for p in queue)
    chair = next(p for p in queue if p["sku"] == "CHAIR-BERGEN")
    sofa = next(p for p in queue if p["sku"] == "SOFA-OSLO-3")
    assert chair["category_known"] and chair["app_path"] == "furniture/seating" and chair["thumbnail_url"]
    assert chair["variants"][0]["geometry"]["format"] == "glb"

    # Approving needs a verified supplier.
    error_of(client.post(f"/admin/market/products/{chair['product_id']}/approve", headers=admin), 409, "conflict")
    res = client.patch(f"/admin/market/suppliers/{sid}", json={"status": "verified", "commission_bp": 800, "listing_plan": "standard"}, headers=admin)
    assert res.status_code == 200 and res.json()["status"] == "verified" and res.json()["commission_bp"] == 800
    error_of(client.patch(f"/admin/market/suppliers/{sid}", json={"listing_plan": "gold"}, headers=admin), 422, "validation_failed")
    error_of(client.patch(f"/admin/market/suppliers/{sid}", json={"status": "famous"}, headers=admin), 422, "validation_failed")

    assert client.get("/market/search", params={"q": "bergen"}, headers=CONTRACT).json()["results"] == []
    res = client.post(f"/admin/market/products/{chair['product_id']}/approve", headers=admin)
    assert res.status_code == 200 and res.json()["status"] == "approved"
    found = client.get("/market/search", params={"q": "bergen", "region": "AE"}, headers=CONTRACT).json()["results"]
    assert [r["name"] for r in found] == ["Bergen lounge chair"] and found[0]["price"]["amount"] == 299900

    # Rejecting records the reason; a rejected product stays out of the catalogue.
    error_of(client.post(f"/admin/market/products/{sofa['product_id']}/reject", json={}, headers=admin), 422, "validation_failed")
    res = client.post(f"/admin/market/products/{sofa['product_id']}/reject", json={"reason": "Images show another product"}, headers=admin)
    assert res.json()["status"] == "rejected" and res.json()["review_note"] == "Images show another product"
    error_of(client.get(f"/market/products/{sofa['product_id']}", headers=CONTRACT), 404, "not_found")
    assert [p["sku"] for p in client.get("/admin/market/products", params={"status": "rejected"}, headers=admin).json()["products"]] == ["SOFA-OSLO-3"]

    # Members, categories, the overview, Connect onboarding.
    signup(client, email="cat@example.com")
    res = client.post(f"/admin/market/suppliers/{sid}/members", json={"email": "cat@example.com", "role": "catalogue"}, headers=admin)
    assert {m["role"] for m in res.json()["members"]} == {"owner", "catalogue"}
    res = client.post("/admin/market/categories", json={"path": "furniture/seating/benches", "label": "Benches"}, headers=admin)
    assert res.status_code == 201 and res.json()["app_path"] == "furniture/seating"
    assert "furniture/seating/benches" in {c["path"] for c in client.get("/market/categories", headers=CONTRACT).json()["categories"]}
    error_of(client.post("/admin/market/categories", json={"path": "spaceships/x", "label": "X"}, headers=admin), 422, "validation_failed")
    error_of(client.post("/admin/market/categories", json={"path": "sheets/a4", "label": "X"}, headers=admin), 422, "validation_failed")
    summary = client.get("/admin/market/summary", headers=admin).json()
    assert summary["products"] == {"approved": 1, "rejected": 1} and summary["suppliers"] == {"verified": 1}
    assert summary["payments_enabled"] is False and summary["stripe_ready"] is False
    assert summary["listing_plans"][0]["id"] == "founding"
    payments_on(monkeypatch)
    assert client.get("/admin/market/summary", headers=admin).json()["payments_enabled"] is True
    fake = FakeGateway()
    monkeypatch.setattr(checkout, "gateway", lambda: fake)
    res = client.post(f"/admin/market/suppliers/{sid}/connect", headers=admin)
    assert res.json() == {"url": "https://connect.stripe.test/acct_new", "connect_account_id": "acct_new"}
    assert client.post("/admin/market/search/rebuild", headers=admin).json() == {"indexed": 2}
    error_of(client.patch(f"/admin/market/suppliers/{'0' * 32}", json={"status": "verified"}, headers=admin), 404, "not_found")
    error_of(client.post(f"/admin/market/products/{'0' * 32}/approve", headers=admin), 404, "not_found")


def _delivered(client, monkeypatch, buyer: dict) -> str:
    """A paid, accepted, shipped and delivered order of the sofa and the paint."""
    payments_on(monkeypatch)
    fake = FakeGateway()
    monkeypatch.setattr(checkout, "gateway", lambda: fake)
    admin = make_admin(client)
    lines = [
        {"supplier_id": SUPPLIER_ID, "sku": "SOFA-OSLO-3", "variant_id": "oat-linen", "qty": 1},
        {"supplier_id": SUPPLIER_ID, "sku": "PAINT-CHALK", "variant_id": "2-5l", "qty": 2},
    ]
    order = client.post("/market/orders", json=order_body(lines=lines), headers=buyer).json()
    sid = client.post(f"/market/checkout/{order['order_id']}", headers=buyer).json()["url"].rsplit("/", 1)[1]
    stripe_post(client, {"type": "checkout.session.completed", "data": {"object": {
        "id": sid, "metadata": {"kind": "market_order", "order_id": order["order_id"]}, "payment_status": "paid", "payment_intent": "pi_r"}}})  # fmt: skip
    for action in ("accept", "ship"):
        assert client.post(f"/admin/market/orders/{order['order_id']}/suppliers/{SUPPLIER_ID}/{action}", headers=admin).status_code == 200
    error_of(client.post(f"/admin/market/orders/{order['order_id']}/suppliers/{SUPPLIER_ID}/accept", headers=admin), 409, "conflict")
    res = client.post(f"/admin/market/orders/{order['order_id']}/suppliers/{SUPPLIER_ID}/deliver", headers=admin)
    assert res.json()["state"] == "delivered"
    return admin


def test_market_reviews_verified_and_moderated(client, monkeypatch):
    load(payments_ready=True)
    buyer = with_contract(signup(client, email="buyer@example.com"))
    stranger = with_contract(signup(client, email="stranger@example.com"))
    path = f"/market/products/{SOFA['product_id']}/reviews"

    error_of(client.post(path, json={"rating": 5, "text": "Lovely"}), 401, "unauthenticated")
    error_of(client.post(path, json={"rating": 5, "text": "Lovely"}, headers=stranger), 403, "not_a_buyer")
    # An order that is not delivered yet does not count.
    pending = client.post("/market/orders", json=order_body("quote"), headers=buyer)
    assert pending.status_code == 201
    error_of(client.post(path, json={"rating": 5}, headers=buyer), 403, "not_a_buyer")

    admin = _delivered(client, monkeypatch, buyer)
    error_of(client.post(path, json={"rating": 6}, headers=buyer), 422, "validation_failed")
    error_of(client.post(path, json={"rating": 4, "text": "x" * 2001}, headers=buyer), 422, "validation_failed")
    res = client.post(path, json={"rating": 4, "text": "Comfortable and well made."}, headers=buyer)
    assert res.status_code == 201 and res.json()["status"] == "pending"
    review_id = res.json()["review_id"]
    error_of(client.post(path, json={"rating": 5}, headers=buyer), 409, "conflict")

    # Pending: not public yet.
    public = client.get(path).json()
    assert public["reviews"] == [] and public["rating"] == {"avg": None, "count": 0}

    error_of(client.post(f"/admin/market/reviews/{review_id}/publish", headers=buyer), 403, "forbidden")
    queue = client.get("/admin/market/reviews", headers=admin).json()["reviews"]
    assert [(r["review_id"], r["status"], r["product_name"]) for r in queue] == [(review_id, "pending", "Oslo 3-seater sofa")]
    assert client.post(f"/admin/market/reviews/{review_id}/publish", headers=admin).json()["status"] == "published"
    public = client.get(path).json()
    assert [r["rating"] for r in public["reviews"]] == [4] and public["rating"] == {"avg": 4.0, "count": 1}
    assert "email" not in public["reviews"][0] and public["reviews"][0]["author"]
    product = client.get(f"/market/products/{SOFA['product_id']}", headers=CONTRACT).json()
    assert product["rating"] == {"avg": 4.0, "count": 1}

    # A second buyer's review moves the average; hiding one takes it out.
    assert client.post(f"/market/products/{PAINT['product_id']}/reviews", json={"rating": 2}, headers=buyer).status_code == 201
    assert client.post(f"/admin/market/reviews/{review_id}/hide", headers=admin).json()["status"] == "hidden"
    assert client.get(path).json()["rating"] == {"avg": None, "count": 0}
    error_of(client.post(f"/admin/market/reviews/{'0' * 32}/publish", headers=admin), 404, "not_found")
    error_of(client.get(f"/market/products/{'0' * 32}/reviews"), 404, "not_found")


def test_market_image_search_stub(client, monkeypatch):
    load()
    files = lambda data: {"image": ("photo.png", data, "image/png")}  # noqa: E731
    # Off by default: 503.
    error_of(client.post("/market/search/image", files=files(b"x")), 503, "unavailable")

    monkeypatch.setattr(get_settings(), "embedding_model", "stub")
    with SessionLocal() as db:
        assert embeddings.embed_pending(db) == 6
        assert embeddings.embed_pending(db) == 0  # each product once
    for sku, picture in (("SOFA-OSLO-3", "thumbs/sofa-oslo-oat.png"), ("PAINT-CHALK", "thumbs/paint-chalk.png"), ("WP-LATTICE", "thumbs/wallpaper-lattice.png")):
        res = client.post("/market/search/image", files=files((FIXTURES / picture).read_bytes()), data={"region": "AE", "limit": "3"})
        assert res.status_code == 200, res.text
        results = res.json()["results"]
        assert res.json()["model"] == "stub-16px-v1"
        with SessionLocal() as db:
            expected = db.scalar(select(Product.product_id).where(Product.sku == sku))
        assert results[0]["product_id"] == expected and results[0]["score"] > 0.99
        assert results[0]["price"]["currency"] == "AED" and len(results) <= 3

    # Over 5 MB: 413. Neither a picture nor a description: 422. Not a picture: 422.
    error_of(client.post("/market/search/image", files=files(b"\0" * (5 * 1024 * 1024 + 1))), 413, "too_large")
    error_of(client.post("/market/search/image", data={"region": "AE"}), 422, "validation_failed")
    error_of(client.post("/market/search/image", files=files(b"not a picture")), 422, "validation_failed")
    error_of(client.post("/market/search/image", files=files(b"x"), data={"region": "ZZ"}), 422, "validation_failed")
    # The stub has no text model: a description goes to the text index.
    res = client.post("/market/search/image", data={"text": "oslo sofa"})
    assert res.json()["model"] == "text-index" and res.json()["results"][0]["name"] == "Oslo 3-seater sofa"

    # A product whose first picture changes is embedded again.
    with SessionLocal() as db:
        p = db.scalar(select(Product).where(Product.sku == "SOFA-OSLO-3"))
        p.images = list(reversed(p.images))
        db.commit()
        assert embeddings.embed_pending(db) == 1


def test_market_fetch_guard():
    """Feed URLs are fetched over https from public addresses only, after DNS."""
    fetch = media.HttpFetcher(resolver=lambda host: host == "cdn.example.com")
    with pytest.raises(media.MediaError) as exc:
        fetch.get("http://cdn.example.com/a.png", 100)
    assert exc.value.code == "bad_url"
    with pytest.raises(media.MediaError) as exc:
        fetch.get("https://intranet.local/a.png", 100)
    assert exc.value.code == "bad_url"
    assert media._public_address("127.0.0.1") is False and media._public_address("10.0.0.8") is False
    assert media._public_address("169.254.169.254") is False and media._public_address("::1") is False
    assert media.geometry_format("https://x.example.com/a/b.GLB?v=2") == "glb"
    assert media.geometry_format("https://x.example.com/a/b.stl") is None
    with pytest.raises(media.MediaError) as exc:
        media.store_geometry(None, b"not gltf", "glb")
    assert exc.value.code == "geometry_fetch_failed"
