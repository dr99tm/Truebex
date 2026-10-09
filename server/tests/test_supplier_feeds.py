"""Supplier feeds (PF8, contract marketplace-api §5.11–5.13): the contract's
§10 feed tests first, then limits, the JSON feed, the daily pull and GD1's
template through the endpoint."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app import mail
from app.database import SessionLocal
from app.market import importer, media
from app.market.models import FeedRun, Product, VariantPrice
from app.supplier import feeds
from app.supplier.models import FeedSource

from .conftest import signup
from .licence_helpers import error_of
from .market_helpers import CONTRACT, FIXTURES, make_admin, png
from .supplier_helpers import (
    FEED_CSV,
    FEED_JSON,
    FEED_REPORT,
    GD1,
    as_supplier,
    csv_of,
    key_headers,
    no_internet,
    outbox,
    post_feed,
    rows_of,
    run_feeds,
    supplier_key,
    verified,
)


@pytest.fixture(autouse=True)
def _clear_outbox():
    mail.OUTBOX.clear()


def _prices(supplier_id: str) -> dict:
    with SessionLocal() as db:
        out = {}
        for p in db.scalars(select(Product).where(Product.supplier_id == supplier_id)):
            for r in db.scalars(select(VariantPrice).where(VariantPrice.product_id == p.product_id)):
                out[(p.sku, r.variant_id, r.region)] = (r.amount, r.currency)
        return out


# --- The contract's §10 feed tests ------------------------------------------------------------


def test_feed_csv_two_regions(client, monkeypatch):
    """feed-two-regions.csv through 5.11 imports as feed-report.json says:
    a GB and an AE price on each variant."""
    no_internet(monkeypatch)
    h, sid = verified(client)
    key = supplier_key(client, h)
    res = post_feed(client, key, FEED_CSV)
    assert res.status_code == 202, res.text
    assert res.json()["state"] == "queued" and len(res.json()["feed_id"]) == 32
    assert res.headers["X-Truebex-Contract"] == "marketplace-api/1.1"
    feed_id = res.json()["feed_id"]
    assert client.get(f"/market/feeds/{feed_id}", headers=key_headers(key)).json()["state"] == "queued"

    assert run_feeds() == [feed_id]
    report = client.get(f"/market/feeds/{feed_id}", headers=key_headers(key)).json()
    keys = ("state", "rows", "created", "updated", "unchanged", "rejected", "errors", "hidden", "warnings", "format", "mode", "source", "detail")
    assert {k: report[k] for k in keys} == {k: FEED_REPORT[k] for k in keys}
    assert report["supplier_id"] == sid and report["finished_at"]

    prices = _prices(sid)
    assert prices == {
        ("SOFA-OSLO-3", "oat-linen", "GB"): (129900, "GBP"),
        ("SOFA-OSLO-3", "oat-linen", "AE"): (129900, "AED"),
        ("SOFA-OSLO-3", "charcoal-wool", "GB"): (144900, "GBP"),
        ("SOFA-OSLO-3", "charcoal-wool", "AE"): (144900, "AED"),
        ("CHAIR-BERGEN", "olive-boucle", "GB"): (64900, "GBP"),
        ("CHAIR-BERGEN", "olive-boucle", "AE"): (299900, "AED"),
    }
    # The products wait for review; approved, the app sees each region's price list.
    admin = make_admin(client, "admin2@example.com")
    with SessionLocal() as db:
        ids = {p.sku: p.product_id for p in db.scalars(select(Product).where(Product.supplier_id == sid))}
        assert {p.status for p in db.scalars(select(Product).where(Product.supplier_id == sid))} == {"pending_review"}
    for pid in ids.values():
        assert client.post(f"/admin/market/products/{pid}/approve", headers=admin).status_code == 200
    for region, currency in (("AE", "AED"), ("GB", "GBP")):
        body = client.get(f"/market/products/{ids['SOFA-OSLO-3']}", params={"region": region}, headers=CONTRACT).json()
        assert {v["price"]["currency"] for v in body["variants"]} == {currency}
    # The same file again: every row unchanged.
    again = post_feed(client, key, FEED_CSV).json()["feed_id"]
    run_feeds()
    report = client.get(f"/market/feeds/{again}", headers=key_headers(key)).json()
    assert (report["created"], report["updated"], report["unchanged"]) == (0, 0, 6)


def test_feed_rejects_unknown_category(client, monkeypatch):
    no_internet(monkeypatch)
    h, sid = verified(client)
    key = supplier_key(client, h)
    rows = rows_of(FEED_CSV)
    for r in rows:
        if r["sku"] == "CHAIR-BERGEN":
            r["category"] = "furniture/hovercraft"
    feed_id = post_feed(client, key, csv_of(rows)).json()["feed_id"]
    run_feeds()
    report = client.get(f"/market/feeds/{feed_id}", headers=key_headers(key)).json()
    assert report["state"] == "done"
    assert report["rejected"] == 2 and report["created"] == 4
    assert {(e["row"], e["column"], e["code"], e["value"]) for e in report["errors"]} == {
        (6, "category", "unknown_category", "furniture/hovercraft"),
        (7, "category", "unknown_category", "furniture/hovercraft"),
    }
    with SessionLocal() as db:
        assert {p.sku for p in db.scalars(select(Product).where(Product.supplier_id == sid))} == {"SOFA-OSLO-3"}
    # A run with rejected rows e-mails the catalogue contacts.
    mails = outbox("2 of 6 catalogue rows were rejected")
    assert mails and "unknown_category" in mails[0].text and f"run={feed_id}" in mails[0].text


def test_feed_requires_supplier_key(client, monkeypatch):
    no_internet(monkeypatch)
    h, sid = verified(client)
    # No key, a session token, a revoked or unknown key: 401.
    error_of(post_feed(client, "", FEED_CSV, headers=CONTRACT), 401, "unauthenticated")
    error_of(post_feed(client, "", FEED_CSV, headers={**h, **CONTRACT}), 401, "unauthenticated")
    error_of(client.get(f"/market/feeds/{'0' * 32}", headers=key_headers("tbx_live_unknown")), 401, "unauthenticated")

    # A developer key of someone who is no member: 403 not_supplier.
    stranger = signup(client, email="stranger@example.com")
    dev_key = client.post("/keys", json={"name": "dev"}, headers=stranger).json()["key"]
    error_of(post_feed(client, dev_key, FEED_CSV), 403, "not_supplier")

    # A viewer (by invitation) with a developer key: 403 not_supplier.
    client.post("/supplier/members", json={"email": "viewer@example.com", "role": "viewer"}, headers=h)
    token = outbox("invited you")[-1].text.split("token=")[1].split()[0]
    viewer = signup(client, email="viewer@example.com")
    assert client.post("/supplier/invites/accept", json={"token": token}, headers=viewer).status_code == 200
    viewer_key = client.post("/keys", json={"name": "dev"}, headers=viewer).json()["key"]
    error_of(post_feed(client, viewer_key, FEED_CSV), 403, "not_supplier")
    error_of(client.put("/market/feeds/source", json={"url": "https://feeds.example.com/a.csv", "format": "csv"}, headers=key_headers(viewer_key)), 403, "not_supplier")

    # The owner's own developer key works while they belong to one supplier only…
    owner_dev = client.post("/keys", json={"name": "dev"}, headers=h).json()["key"]
    assert post_feed(client, owner_dev, FEED_CSV).status_code == 202
    # …and is ambiguous once they are a catalogue member of a second supplier.
    from app.market.catalogue import add_member, create_supplier
    from app.models import User

    with SessionLocal() as db:
        other = create_supplier(db, name="Second Co", country="GB", status="verified")
        add_member(db, other, db.scalar(select(User).where(User.email == "owner@nord.example.com")), "owner")
        db.commit()
        other_id = other.supplier_id
    body = error_of(post_feed(client, owner_dev, FEED_CSV), 403, "not_supplier")
    assert "supplier key" in body["detail"]
    # A portal key is bound to its supplier: it still works, and sees only that supplier's runs.
    key = supplier_key(client, h)
    feed_id = post_feed(client, key, FEED_CSV).json()["feed_id"]
    with SessionLocal() as db:
        assert db.get(FeedRun, feed_id).supplier_id == sid
    other_key = supplier_key(client, as_supplier(h, other_id), "second")
    error_of(client.get(f"/market/feeds/{feed_id}", headers=key_headers(other_key)), 404, "not_found")
    # A supplier key is refused by the developer API.
    assert client.get("/v1/ping", headers={"Authorization": f"Bearer {key}"}).status_code == 401


def test_contract_header_and_error_envelope(client, monkeypatch):
    no_internet(monkeypatch)
    h, _sid = verified(client)
    key = supplier_key(client, h)
    ok = post_feed(client, key, FEED_CSV)
    assert ok.headers["X-Truebex-Contract"] == "marketplace-api/1.1"
    feed_id = ok.json()["feed_id"]
    got = client.get(f"/market/feeds/{feed_id}", headers=key_headers(key))
    assert got.headers["X-Truebex-Contract"] == "marketplace-api/1.1"
    # A 1.0 client is served; MAJOR 2 is 400 contract_version on each of 5.11–5.13.
    v10 = {**key_headers(key), "X-Truebex-Contract": "marketplace-api/1.0"}
    assert client.get(f"/market/feeds/{feed_id}", headers=v10).status_code == 200
    v2 = {**key_headers(key), "X-Truebex-Contract": "marketplace-api/2.0"}
    body = error_of(client.get(f"/market/feeds/{feed_id}", headers=v2), 400, "contract_version")
    assert body["data"]["supported"] == ["marketplace-api/1.1"]
    error_of(post_feed(client, key, FEED_CSV, headers=v2), 400, "contract_version")
    error_of(client.put("/market/feeds/source", json={"url": "https://x.example.com/f.csv", "format": "csv"}, headers=v2), 400, "contract_version")
    # Errors carry the envelope (code, status, request_id; detail a string).
    body = error_of(client.get(f"/market/feeds/{'f' * 32}", headers=key_headers(key)), 404, "not_found")
    assert body["retry_after_s"] is None
    error_of(post_feed(client, key, b"a,b\r\n1,2\r\n"), 422, "feed_invalid")
    body = error_of(client.post("/market/feeds", data={"format": "xml"}, files={"file": ("f.xml", b"<x/>")}, headers=key_headers(key)), 422, "validation_failed")
    assert body["data"]["fields"][0]["field"] == "format"


# --- Beyond §10 ------------------------------------------------------------------------------


def test_feed_json_matches_csv(client, monkeypatch):
    no_internet(monkeypatch)
    h1, s1 = verified(client, email="csv@example.com", name="CSV Co")
    h2, s2 = verified(client, email="json@example.com", name="JSON Co")
    a = post_feed(client, supplier_key(client, h1), FEED_CSV).json()["feed_id"]
    k2 = supplier_key(client, h2)
    b = post_feed(client, k2, FEED_JSON, fmt="json").json()["feed_id"]
    run_feeds()
    ra = client.get(f"/market/feeds/{a}", headers=key_headers(supplier_key(client, h1, "read"))).json()
    rb = client.get(f"/market/feeds/{b}", headers=key_headers(k2)).json()
    keys = ("state", "rows", "created", "updated", "unchanged", "rejected", "errors")
    assert {k: ra[k] for k in keys} == {k: rb[k] for k in keys} and rb["format"] == "json"
    assert _prices(s1) == _prices(s2) and len(_prices(s1)) == 6


def test_feed_limits_and_shape(client, monkeypatch):
    no_internet(monkeypatch)
    h, _sid = verified(client)
    key = supplier_key(client, h)
    # Over 50 MB (the cap, made small here) or 100 000 rows: 413 too_large.
    monkeypatch.setattr(importer, "MAX_BYTES", 1000)
    body = error_of(post_feed(client, key, FEED_CSV), 413, "too_large")
    assert body["data"]["max_bytes"] == 1000
    monkeypatch.setattr(importer, "MAX_BYTES", 50 * 1024 * 1024)
    monkeypatch.setattr(importer, "MAX_ROWS", 5)
    error_of(post_feed(client, key, FEED_CSV), 413, "too_large")
    monkeypatch.setattr(importer, "MAX_ROWS", 100_000)
    # A wrong header or JSON shape: 422 feed_invalid, nothing queued.
    error_of(post_feed(client, key, FEED_CSV.replace(b"category,", b"kategorie,", 1)), 422, "feed_invalid")
    error_of(post_feed(client, key, b'{"schema": "other/1", "products": []}', fmt="json"), 422, "feed_invalid")
    error_of(post_feed(client, key, b"not json", fmt="json"), 422, "feed_invalid")
    error_of(post_feed(client, key, b"\xff\xfe not utf-8"), 422, "feed_invalid")
    # A bad mode is a validation error.
    res = client.post("/market/feeds", data={"format": "csv", "mode": "merge"}, files={"file": ("f.csv", FEED_CSV)}, headers=key_headers(key))
    error_of(res, 422, "validation_failed")
    with SessionLocal() as db:
        assert db.scalars(select(FeedRun)).first() is None
    # replace mode hides what the file omits.
    assert post_feed(client, key, FEED_CSV).status_code == 202
    run_feeds()
    chair_only = csv_of([r for r in rows_of(FEED_CSV) if r["sku"] == "CHAIR-BERGEN"])
    feed_id = post_feed(client, key, chair_only, mode="replace").json()["feed_id"]
    run_feeds()
    assert client.get(f"/market/feeds/{feed_id}", headers=key_headers(key)).json()["hidden"] == 1


class _FakeFeed:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def get(self, url, etag):
        self.calls.append((url, etag))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def test_feed_source_daily_pull(client, monkeypatch):
    no_internet(monkeypatch)
    monkeypatch.setattr(feeds, "public_host", lambda host: host == "feeds.example.com")
    h, sid = verified(client)
    key = supplier_key(client, h)

    def put(url, **kw):
        return client.put("/market/feeds/source", json={"url": url, "format": "csv", "mode": "replace", **kw}, headers=key_headers(key))

    error_of(put("http://feeds.example.com/feed.csv"), 422, "validation_failed")
    error_of(put("https://10.0.0.5/feed.csv"), 422, "validation_failed")
    error_of(put("https://localhost/feed.csv"), 422, "validation_failed")
    error_of(put("https://feeds.example.com/feed.csv", format="xml"), 422, "validation_failed")
    res = put("https://feeds.example.com/feed.csv")
    assert res.status_code == 200, res.text
    src = res.json()
    assert src["url"] == "https://feeds.example.com/feed.csv" and src["mode"] == "replace"
    assert src["next_pull_at"].endswith("T02:00:00Z") and src["last_pull_at"] is None
    # The portal shows the same source.
    assert client.get("/supplier/feeds/source", headers=h).json()["source"]["url"] == src["url"]

    nxt = datetime.fromisoformat(src["next_pull_at"].replace("Z", "+00:00"))
    fake = _FakeFeed([(200, FEED_CSV, '"v1"'), (304, b"", '"v1"'), feeds.PullError("the server answered HTTP 500")])
    with SessionLocal() as db:
        assert feeds.pull_due(db, nxt - timedelta(minutes=1), fetch=fake) == 0
        assert feeds.pull_due(db, nxt + timedelta(seconds=30), fetch=fake) == 1
        row = db.get(FeedSource, sid)
        assert (row.last_status, row.etag) == ("queued", '"v1"')
        assert row.next_pull_at.replace(tzinfo=timezone.utc) == nxt + timedelta(days=1)
        run = db.get(FeedRun, row.last_feed_id)
        assert (run.state, run.source, run.mode) == ("queued", "pull", "replace")
    assert fake.calls == [("https://feeds.example.com/feed.csv", None)]
    run_feeds()
    assert client.get(f"/market/feeds/{run.feed_id}", headers=key_headers(key)).json()["created"] == 6
    with SessionLocal() as db:
        # Not again the same day; the next day sends the ETag and a 304 queues nothing.
        assert feeds.pull_due(db, nxt + timedelta(hours=5), fetch=fake) == 0
        assert feeds.pull_due(db, nxt + timedelta(days=1, seconds=5), fetch=fake) == 1
        assert db.get(FeedSource, sid).last_status == "not_modified"
        assert fake.calls[-1] == ("https://feeds.example.com/feed.csv", '"v1"')
        # A failed pull is recorded and e-mailed.
        assert feeds.pull_due(db, nxt + timedelta(days=2, seconds=5), fetch=fake) == 1
        row = db.get(FeedSource, sid)
        assert row.last_status == "failed" and "HTTP 500" in row.last_error
    assert outbox("We could not read your catalogue feed")
    # The real fetcher refuses http and private addresses after DNS resolution.
    monkeypatch.setattr(feeds, "public_host", media._public_address)
    for url in ("https://localhost/feed.csv", "https://127.0.0.1/feed.csv", "http://example.com/feed.csv"):
        with pytest.raises(feeds.PullError):
            feeds.HttpFeedFetcher().get(url, None)


def test_feed_gd1_template(client, monkeypatch):
    """Contract 1.1.0: GD1's template through 5.11, BOM-less and with a BOM,
    columns shuffled and one unknown column: 0 rejected, one product, two
    variants, three price lines; a differing name → inconsistent_product,
    a wrong check digit → bad_gtin."""
    fetcher = media.MapFetcher(
        {
            "https://cdn.example.com/catalogue/sofa-oslo-3/oat-linen.glb": (FIXTURES / "geometry" / "chair-bergen.glb"),
            "https://cdn.example.com/catalogue/sofa-oslo-3/charcoal-wool.glb": (FIXTURES / "geometry" / "chair-bergen.glb"),
            "https://cdn.example.com/catalogue/sofa-oslo-3/oat-linen-1.jpg": png(colour=(220, 210, 190)),
            "https://cdn.example.com/catalogue/sofa-oslo-3/oat-linen-2.jpg": png(colour=(200, 190, 170)),
            "https://cdn.example.com/catalogue/sofa-oslo-3/charcoal-wool-1.jpg": png(colour=(60, 60, 64)),
        }
    )
    no_internet(monkeypatch, fetcher)
    rows = rows_of(GD1)
    shuffled = list(reversed(list(rows[0]))) + ["internal_note"]
    for r in rows:
        r["internal_note"] = "ignore me"
    for n, data in enumerate((GD1, csv_of(rows, shuffled, bom=True))):
        h, sid = verified(client, email=f"gd1-{n}@example.com", name=f"GD1 Co {n}")
        key = supplier_key(client, h)
        feed_id = post_feed(client, key, data).json()["feed_id"]
        run_feeds()
        report = client.get(f"/market/feeds/{feed_id}", headers=key_headers(key)).json()
        assert report["rejected"] == 0, report["errors"]
        assert (report["rows"], report["created"]) == (3, 3)
        if n == 1:
            assert report["warnings"] == [{"column": "internal_note", "code": "unknown_column"}]
        with SessionLocal() as db:
            products = list(db.scalars(select(Product).where(Product.supplier_id == sid)))
            assert len(products) == 1
            prices = list(db.scalars(select(VariantPrice).where(VariantPrice.product_id == products[0].product_id)))
            assert len(prices) == 3 and {p.variant_id for p in prices} == {"oat-linen", "charcoal-wool"}
    bad = rows_of(GD1)
    bad[1]["name"] = "Oslo sofa"
    bad[2]["gtin"] = "9501101530011"
    h, sid = verified(client, email="gd1-bad@example.com", name="GD1 bad")
    key = supplier_key(client, h)
    feed_id = post_feed(client, key, csv_of(bad)).json()["feed_id"]
    run_feeds()
    report = client.get(f"/market/feeds/{feed_id}", headers=key_headers(key)).json()
    assert {(e["row"], e["code"]) for e in report["errors"]} == {(3, "inconsistent_product"), (4, "bad_gtin")}
    assert report["rejected"] == 2 and report["created"] == 1
