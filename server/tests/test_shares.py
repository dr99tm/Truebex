"""Shares (share-bundle §5.4-5.11): the contract's §10 platform tests and PF5's
per-endpoint tests: manifest rules, publish, page data, the share page and
its preview, visits, limits, expiry, revoke and purge."""

import hashlib
import io
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from PIL import Image
from sqlalchemy import inspect, select

from app import ratelimit, tasks
from app.config import get_settings
from app.database import SessionLocal, engine
from app.licence import clock
from app.shares import derivatives
from app.shares.models import Share, ShareDerivative, ShareVisit
from app.storage import get_store, local
from app.uploads.models import Blob

from .licence_helpers import Clock, error_of, ts
from .share_helpers import (
    CONTRACT,
    blobs_by_sha,
    create,
    dev,
    device_token,
    fixture_json,
    house,
    published,
    second_device,
    upload_files,
    web,
    without_sheets,
)

BUNDLE_2 = "5" * 32
# The share and upload jobs (the other features' jobs are their tests' business).
PF5_JOBS = ["shares.expire", "shares.purge", "uploads.expire"]


def _rel(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}" if parts.query else parts.path


def _meta(html: str, prop: str) -> str | None:
    m = re.search(rf'<meta (?:property|name)="{re.escape(prop)}" content="([^"]*)"', html)
    return m.group(1) if m else None


# --- contract §10 --------------------------------------------------------------------


def test_share_publish_requires_all_files(client):
    token, _ = device_token(client)
    res = create(client, token)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["share"]["state"] == "uploading" and body["share"]["url"] is None
    shas = [f["sha256"] for f in body["upload"]["files"]]
    assert len(shas) == 5 and {f["state"] for f in body["upload"]["files"]} == {"missing"}
    upload_files(client, token, body["upload"], only=shas[:2])
    res = client.post(f"/shares/{body['share']['share_id']}/publish", headers=dev(token))
    err = error_of(res, 422, "upload_incomplete")
    assert sorted(err["data"]["missing"]) == sorted(shas[2:])
    assert "3 files" in err["detail"]


def test_manifest_rules(client):
    token, _ = device_token(client)
    cases = fixture_json("manifest-invalid.json")["cases"]
    assert [c["name"] for c in cases[:3]] == ["pano-3-to-1", "hotspot-missing-target", "file-not-listed"]
    for case in cases:
        res = create(client, token, case["manifest"])
        body = error_of(res, case["expect"]["status"], case["expect"]["code"])
        got = [{"path": e["path"], "rule": e["rule"]} for e in body["data"]["errors"]]
        assert got == case["expect"]["errors"], case["name"]
        assert all(e["message"] for e in body["data"]["errors"])
    with SessionLocal() as db:
        assert db.scalars(select(Share)).all() == []
    # The valid manifest passes the same rules.
    assert create(client, token).status_code == 201


def test_share_page_data_and_signed_urls(client, monkeypatch):
    token, _ = device_token(client)
    share = published(client, token)
    res = client.get(f"/s/{share['slug']}", headers=CONTRACT)
    assert res.status_code == 200, res.text
    assert res.headers["Cache-Control"] == "no-store" and "noindex" in res.headers["X-Robots-Tag"]
    data = res.json()
    assert data["title"] == "House — client review" and data["designed_in"] == "Truebex"
    assert data["watermark"] is True and data["expires_at"] == share["expires_at"]
    m = data["manifest"]
    files = blobs_by_sha()
    assert len(m["files"]) == 5
    for f in m["files"]:
        got = client.get(_rel(f["url"]))
        assert got.status_code == 200 and got.content == files[f["sha256"]], f["name"]
    pdf = next(f for f in m["files"] if f["content_type"] == "application/pdf")
    assert "drawings.pdf" in client.get(_rel(pdf["url"])).headers["content-disposition"]
    for p in m["panoramas"]:
        assert set(p["derivatives"]) == {"pano-4096", "pano-1024"}
        small = client.get(_rel(p["derivatives"]["pano-1024"]["url"]))
        assert small.status_code == 200 and Image.open(io.BytesIO(small.content)).size == (1024, 512)
    assert m["panoramas"][0]["hotspots"][0] == {"target": "p2", "bearing_deg": 132.5, "pitch_deg": -8, "label": "Kitchen"}

    # Signed for at least an hour (ending on a 5-minute boundary), then refused.
    real = local.clock
    monkeypatch.setattr(local, "clock", lambda: real() + 3590)
    assert client.get(_rel(m["files"][0]["url"])).status_code == 200
    monkeypatch.setattr(local, "clock", lambda: real() + 3600 + 301)
    for f in m["files"]:
        assert client.get(_rel(f["url"])).status_code == 403
    assert client.get(_rel(m["panoramas"][0]["derivatives"]["pano-4096"]["url"])).status_code == 403
    # Unknown and unpublished links are 404.
    error_of(client.get("/s/AAAAAAAAAA", headers=CONTRACT), 404, "not_found")
    error_of(client.get("/s/short", headers=CONTRACT), 404, "not_found")


def test_share_expiry_and_revoke_gone(client, monkeypatch):
    clk = Clock(monkeypatch)
    token, session = device_token(client)
    first = published(client, token)
    assert ts(first["expires_at"]) == clk.at + timedelta(days=30)
    clk.advance(days=30, seconds=1)
    err = error_of(client.get(f"/s/{first['slug']}", headers=CONTRACT), 410, "share_gone")
    assert err["data"]["state"] == "expired"
    page = client.get(f"/view/{first['slug']}")
    assert page.status_code == 410 and "This link has ended" in page.text
    assert "noindex" in page.headers["X-Robots-Tag"]
    error_of(client.post(f"/s/{first['slug']}/visits", json={"visitor": "a" * 32}, headers=CONTRACT), 410, "share_gone")

    # An expired share frees its slot; revoking the next ends its page at once.
    second = published(client, token, house(BUNDLE_2))
    assert client.get(f"/s/{second['slug']}", headers=CONTRACT).status_code == 200
    res = client.delete(f"/shares/{second['share_id']}", headers=web(session))
    assert res.status_code == 200 and res.json()["state"] == "revoked"
    err = error_of(client.get(f"/s/{second['slug']}", headers=CONTRACT), 410, "share_gone")
    assert err["data"]["state"] == "revoked"
    page = client.get(f"/view/{second['slug']}")
    assert page.status_code == 410 and "This link has ended" in page.text
    assert client.get(f"/s/{second['slug']}/card.jpg").status_code == 410
    # A link that never existed says so, also with noindex.
    missing = client.get("/view/ZZZZZZZZZZ")
    assert missing.status_code == 404 and "find this share" in missing.text


def test_visits_unique_per_day(client, monkeypatch):
    fx = fixture_json("visits.json")
    clk = Clock(monkeypatch, datetime(2026, 10, 8, 9, 0, tzinfo=timezone.utc))
    token, session = device_token(client)
    share = published(client, token)
    for visit in fx["visits"]:
        clk.at = ts(visit["at"])
        res = client.post(f"/s/{share['slug']}/visits", json={"visitor": visit["visitor"]}, headers=CONTRACT)
        assert res.status_code == 204, res.text
    clk.at = ts(fx["now"])
    got = client.get(f"/shares/{share['share_id']}", headers=web(session)).json()["visits"]
    assert got == fx["expect"]
    # The list carries the same totals.
    listed = client.get("/shares", headers=dev(token)).json()["shares"][0]["visits"]
    assert listed == {k: fx["expect"][k] for k in ("total", "unique", "last_at")}
    error_of(client.post(f"/s/{share['slug']}/visits", json={"visitor": "not-hex"}, headers=CONTRACT), 422, "validation_failed")


def test_share_url_has_its_own_preview(client):
    token, _ = device_token(client)
    share = published(client, token)
    other_token, _ = device_token(client, email="other@example.com", fingerprint="b" * 64)
    other = published(client, other_token, house(BUNDLE_2), title="Flat <b>& garden</b>")

    url = urlsplit(share["url"])
    assert url.path == f"/view/{share['slug']}" and share["url"].startswith(get_settings().share_base)
    assert re.fullmatch(r"[A-Za-z0-9]{10}", share["slug"])
    res = client.get(url.path, headers={"User-Agent": "facebookexternalhit/1.1"})
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/html")
    assert res.headers["Cache-Control"] == "public, max-age=300"
    assert "noindex" in res.headers["X-Robots-Tag"] and "frame-ancestors 'none'" in res.headers["Content-Security-Policy"]
    html = res.text
    assert _meta(html, "og:title") == "House — client review — designed in Truebex"
    assert _meta(html, "og:description") == "3 panoramas, 1 render and the drawings."
    assert _meta(html, "og:url") == share["url"]
    assert _meta(html, "og:image:width") == "1200" and _meta(html, "og:image:height") == "630"
    assert _meta(html, "twitter:card") == "summary_large_image"
    assert re.search(r'<meta name="robots" content="noindex', html)
    assert f'data-slug="{share["slug"]}"' in html and "/viewer/viewer.js" in html
    preload = re.search(r'<link rel="preload" as="image" href="([^"]+)"', html).group(1)
    assert "pano-4096.jpg" in preload and "sig=" in preload  # the start panorama's 4096, signed
    image = _meta(html, "og:image")
    assert image == f"{get_settings().share_base}/s/{share['slug']}/card.jpg"
    card = client.get(urlsplit(image).path)
    assert card.status_code == 200 and card.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(card.content)).size == (1200, 630)

    # Another share previews as itself, its title escaped.
    html2 = client.get(urlsplit(other["url"]).path).text
    assert _meta(html2, "og:title") == "Flat &lt;b&gt;&amp; garden&lt;/b&gt; — designed in Truebex"
    assert "<b>" not in html2 and _meta(html2, "og:image") != image
    # Preview crawlers may read share pages; the rest of the API is closed.
    robots = client.get("/robots.txt").text
    assert "Allow: /view/" in robots and "Allow: /s/" in robots and "Disallow: /" in robots


def test_contract_header_and_error_envelope(client):
    token, session = device_token(client)
    res = client.get("/shares", headers=web(session))
    assert res.status_code == 200 and res.headers["X-Truebex-Contract"] == "share-bundle/1.0"
    assert res.json()["limits"] == {"share_links": 1, "share_days": 30, "share_bytes": 1024**3}
    for method, path in (("get", "/shares"), ("post", "/uploads"), ("get", "/s/AAAAAAAAAA")):
        res = getattr(client, method)(path, headers={**dev(token), "X-Truebex-Contract": "share-bundle/2.0"})
        body = error_of(res, 400, "contract_version")
        assert body["data"]["supported"] == ["share-bundle/1.0"]
    res = client.get("/shares/" + "0" * 32, headers=dev(token))
    body = error_of(res, 404, "not_found")
    assert set(body) == {"detail", "code", "status", "request_id", "retry_after_s", "data"}
    # A missing header reads as the current version.
    assert client.get("/shares", headers={"Authorization": f"Bearer {token}"}).status_code == 200


# --- PF5's own tests --------------------------------------------------------------------


def test_shares_quota_exceeded(client, monkeypatch):
    token, _ = device_token(client)
    assert create(client, token).status_code == 201
    # An upload in progress holds the Free tier's one slot.
    err = error_of(create(client, token, house(BUNDLE_2)), 403, "quota_exceeded")
    assert err["data"]["limit"] == 1 and err["data"]["used"] == 1 and err["data"]["kind"] == "share_links"
    other_token, _ = device_token(client, email="pro@example.com", fingerprint="c" * 64)
    published(client, other_token)
    err = error_of(create(client, other_token, house(BUNDLE_2)), 403, "quota_exceeded")
    assert err["data"]["limit"] == 1

    # Bytes over the tier's bundle limit.
    monkeypatch.setattr(get_settings(), "share_max_bytes", 1000)
    third, _ = device_token(client, email="third@example.com", fingerprint="d" * 64)
    err = error_of(create(client, third), 403, "quota_exceeded")
    assert err["data"]["kind"] == "share_bytes" and err["data"]["limit"] == 1000
    assert err["data"]["used"] == sum(f["bytes"] for f in house()["files"])
    # And the longest expiry.
    monkeypatch.setattr(get_settings(), "share_max_bytes", 1024**3)
    err = error_of(create(client, third, days=31), 422, "expiry_too_far")
    assert err["data"]["max_days"] == 30
    error_of(create(client, third, days=0), 422, "validation_failed")


def test_shares_create_idempotent_by_bundle(client):
    token, session = device_token(client)
    first = create(client, token)
    again = create(client, token)
    assert first.status_code == 201 and again.status_code == 200
    assert again.json()["share"]["share_id"] == first.json()["share"]["share_id"]
    assert again.json()["upload"]["upload_id"] == first.json()["upload"]["upload_id"]
    # Another device of the same account resumes the same share and upload.
    laptop = second_device(client, session)
    from_laptop = create(client, laptop).json()
    assert from_laptop["share"]["share_id"] == first.json()["share"]["share_id"]
    upload_files(client, laptop, from_laptop["upload"])
    share_id = first.json()["share"]["share_id"]
    live = client.post(f"/shares/{share_id}/publish", headers=dev(token))
    assert live.status_code == 200 and live.json()["share"]["state"] == "live"
    # Publishing again and creating again are safe.
    assert client.post(f"/shares/{share_id}/publish", headers=dev(token)).json()["share"]["slug"] == live.json()["share"]["slug"]
    after = create(client, token)
    assert after.status_code == 200 and after.json()["share"]["state"] == "live"
    assert {f["state"] for f in after.json()["upload"]["files"]} == {"present"}
    with SessionLocal() as db:
        assert len(db.scalars(select(Share)).all()) == 1


def test_shares_list_get_patch_revoke_auth(client, monkeypatch):
    clk = Clock(monkeypatch)
    token, session = device_token(client)
    share = published(client, token)
    sid = share["share_id"]

    listed = client.get("/shares", headers=web(session)).json()["shares"]
    assert [s["share_id"] for s in listed] == [sid]
    assert client.get("/shares?state=live", headers=dev(token)).json()["shares"][0]["share_id"] == sid
    assert client.get("/shares?state=revoked", headers=dev(token)).json()["shares"] == []
    error_of(client.get("/shares?state=bogus", headers=dev(token)), 422, "validation_failed")
    one = client.get(f"/shares/{sid}", headers=web(session)).json()
    assert one["visits"] == {"total": 0, "unique": 0, "last_at": None, "by_day": []}

    res = client.patch(f"/shares/{sid}", json={"title": "  House — final  "}, headers=dev(token))
    assert res.status_code == 200 and res.json()["title"] == "House — final"
    too_far = clk.at + timedelta(days=31)
    err = error_of(client.patch(f"/shares/{sid}", json={"expires_at": too_far.isoformat()}, headers=web(session)), 422, "expiry_too_far")
    assert ts(err["data"]["max_expires_at"]) == clk.at + timedelta(days=30)
    error_of(client.patch(f"/shares/{sid}", json={"expires_at": (clk.at - timedelta(days=1)).isoformat()}, headers=web(session)), 422, "validation_failed")
    error_of(client.patch(f"/shares/{sid}", json={}, headers=web(session)), 422, "validation_failed")
    error_of(client.patch(f"/shares/{sid}", json={"title": ""}, headers=web(session)), 422, "validation_failed")
    later = clk.at + timedelta(days=10)
    res = client.patch(f"/shares/{sid}", json={"expires_at": later.isoformat()}, headers=web(session))
    assert res.status_code == 200 and ts(res.json()["expires_at"]) == later

    # Extending an expired share brings it back while its files are kept.
    clk.advance(days=11)
    assert client.get(f"/shares/{sid}", headers=dev(token)).json()["state"] == "expired"
    res = client.patch(f"/shares/{sid}", json={"expires_at": (clk.at + timedelta(days=30)).isoformat()}, headers=web(session))
    assert res.status_code == 200 and res.json()["state"] == "live"
    assert client.get(f"/s/{share['slug']}", headers=CONTRACT).status_code == 200

    # Auth: none, an API key, a session for 5.4, another account's credentials.
    error_of(client.get("/shares", headers=CONTRACT), 401, "unauthenticated")
    error_of(client.get("/shares", headers={"Authorization": "Bearer tbx_live_x", **CONTRACT}), 401, "unauthenticated")
    error_of(client.post("/shares", json={"title": "x", "manifest": house()}, headers=web(session)), 401, "unauthenticated")
    error_of(client.post(f"/shares/{sid}/publish", headers=web(session)), 401, "unauthenticated")
    stranger, stranger_session = device_token(client, email="stranger@example.com", fingerprint="e" * 64)
    for headers in (dev(stranger), web(stranger_session)):
        error_of(client.get(f"/shares/{sid}", headers=headers), 404, "not_found")
        error_of(client.patch(f"/shares/{sid}", json={"title": "mine"}, headers=headers), 404, "not_found")
        error_of(client.delete(f"/shares/{sid}", headers=headers), 404, "not_found")
    assert client.get("/shares", headers=dev(stranger)).json()["shares"] == []

    # Revoke: final, safe to repeat; nothing changes it afterwards.
    res = client.delete(f"/shares/{sid}", headers=dev(token))
    assert res.status_code == 200 and res.json()["state"] == "revoked" and res.json()["revoked_at"]
    assert client.delete(f"/shares/{sid}", headers=web(session)).json()["state"] == "revoked"
    error_of(client.patch(f"/shares/{sid}", json={"title": "again"}, headers=dev(token)), 410, "share_gone")
    error_of(client.post(f"/shares/{sid}/publish", headers=dev(token)), 410, "share_gone")


def test_shares_card_and_derivatives_made(client):
    token, _ = device_token(client)
    share = published(client, token)
    store = get_store()
    m = house()
    with SessionLocal() as db:
        rows = db.scalars(select(ShareDerivative).where(ShareDerivative.share_id == share["share_id"])).all()
        card_key = db.get(Share, share["share_id"]).card_key
    made = {(r.source_sha256, r.kind): r for r in rows}
    assert len(made) == 2 * len(m["panoramas"])
    for p in m["panoramas"]:
        for kind, size in (("pano-4096", (2048, 1024)), ("pano-1024", (1024, 512))):
            row = made[(p["file"], kind)]
            assert row.storage_key == f"shares/{share['share_id']}/derived/{p['file']}-{kind}.jpg"
            with store.open(row.storage_key) as fh:
                assert Image.open(fh).size == size == (row.width, row.height)
    assert card_key == f"shares/{share['share_id']}/card.jpg"
    with store.open(card_key) as fh:
        card = Image.open(fh)
        assert card.size == (1200, 630) and card.format == "JPEG"

    # An 8k panorama gets the full 4096 x 2048 and 1024 x 512 derivatives.
    buf = io.BytesIO()
    Image.new("RGB", (8192, 4096), (120, 140, 160)).save(buf, format="JPEG", quality=60)
    store.put("tests/pano-8k.jpg", buf.getvalue(), content_type="image/jpeg")
    out, largest = derivatives.make(store, share_id="t" * 32, sha256="a" * 64, source_key="tests/pano-8k.jpg")
    assert [(d.kind, d.width, d.height) for d in out] == [("pano-4096", 4096, 2048), ("pano-1024", 1024, 512)]
    assert largest.size == (4096, 2048)


def test_shares_publish_checks_file_contents(client):
    token, _ = device_token(client)
    m = house()
    # Claim the render is a panorama-sized image: the stored file says otherwise.
    m["renders"][0]["width"], m["renders"][0]["height"] = 1280, 720
    res = create(client, token, m)
    upload_files(client, token, res.json()["upload"])
    err = error_of(client.post(f"/shares/{res.json()['share']['share_id']}/publish", headers=dev(token)), 422, "manifest_invalid")
    assert err["data"]["errors"][0] == {"path": "renders[0].file", "rule": "file_content", "message": err["data"]["errors"][0]["message"]}


def test_shares_files_purged_after_seven_days(client, monkeypatch):
    clk = Clock(monkeypatch)
    token, session = device_token(client)
    first = published(client, token)
    client.delete(f"/shares/{first['share_id']}", headers=web(session))
    # A second share keeps the panoramas and the render, not the PDF.
    second = published(client, token, without_sheets(house(), BUNDLE_2))
    pdf_sha = house()["sheets"]["file"]
    pano_sha = house()["panoramas"][0]["file"]
    store = get_store()
    with SessionLocal() as db:
        keys = [d.storage_key for d in db.scalars(select(ShareDerivative).where(ShareDerivative.share_id == first["share_id"]))]
        card_key = db.get(Share, first["share_id"]).card_key
        refs = {b.sha256: b.refs for b in db.scalars(select(Blob))}
    assert refs[pano_sha] == 2 and refs[pdf_sha] == 1
    assert keys and all(store.stat(k) is not None for k in keys + [card_key])

    tasks.run_due(clk.advance(days=6), only=PF5_JOBS, force=True)
    assert store.stat(card_key) is not None
    tasks.run_due(clk.advance(days=1, seconds=1), only=PF5_JOBS, force=True)
    assert all(store.stat(k) is None for k in keys + [card_key])
    with SessionLocal() as db:
        blobs = {b.sha256: b for b in db.scalars(select(Blob))}
        gone = db.get(Share, first["share_id"])
        assert gone.purged_at is not None and gone.state == "revoked"
        assert db.scalars(select(ShareDerivative).where(ShareDerivative.share_id == first["share_id"])).all() == []
    assert pdf_sha not in blobs  # only the first share held it
    assert blobs[pano_sha].refs == 1 and store.stat(blobs[pano_sha].storage_key) is not None
    # The second share still opens, files and all.
    data = client.get(f"/s/{second['slug']}", headers=CONTRACT).json()
    assert all(client.get(_rel(f["url"])).status_code == 200 for f in data["manifest"]["files"])
    error_of(client.get(f"/s/{first['slug']}", headers=CONTRACT), 410, "share_gone")


def test_shares_expire_job_marks_and_frees(client, monkeypatch):
    clk = Clock(monkeypatch)
    token, _ = device_token(client)
    share = published(client, token)
    stale = create(client, token, house(BUNDLE_2))  # over the limit while live
    assert stale.status_code == 403
    tasks.run_due(clk.advance(days=30, seconds=1), only=PF5_JOBS, force=True)
    with SessionLocal() as db:
        row = db.get(Share, share["share_id"])
        assert row.state == "expired"
        assert clock.aware(row.purge_after) == ts(share["expires_at"]) + timedelta(days=7)
    # An upload abandoned for 7 days ends too.
    abandoned = create(client, token, house(BUNDLE_2)).json()["share"]
    tasks.run_due(clk.advance(days=7, seconds=1), only=PF5_JOBS, force=True)
    with SessionLocal() as db:
        assert db.get(Share, abandoned["share_id"]).state == "expired"


def test_shares_visits_rate_limited_no_ip(client, monkeypatch):
    token, _ = device_token(client)
    share = published(client, token)
    # PF14's token bucket refills continuously (60 a minute = one a second):
    # hold its clock still so the 61st visit is refused however slow the run.
    now = [1000.0]
    monkeypatch.setattr(ratelimit, "clock", lambda: now[0])
    for i in range(60):
        res = client.post(f"/s/{share['slug']}/visits", json={"visitor": f"{i:032x}"}, headers=CONTRACT)
        assert res.status_code == 204, (i, res.text)
    res = client.post(f"/s/{share['slug']}/visits", json={"visitor": "f" * 32}, headers=CONTRACT)
    body = error_of(res, 429, "rate_limited")
    assert body["retry_after_s"] >= 1 and res.headers["Retry-After"]
    # A second later one visit is allowed again, and only one.
    now[0] += 1.0
    assert client.post(f"/s/{share['slug']}/visits", json={"visitor": "e" * 32}, headers=CONTRACT).status_code == 204
    error_of(client.post(f"/s/{share['slug']}/visits", json={"visitor": "d" * 32}, headers=CONTRACT), 429, "rate_limited")
    # No address and no user agent are kept: only these columns exist.
    columns = {c["name"] for c in inspect(engine).get_columns("share_visits")}
    assert columns == {"id", "share_id", "day", "visitor", "count", "last_at"}
    with SessionLocal() as db:
        rows = db.scalars(select(ShareVisit)).all()
        assert len(rows) == 61  # the 60, then the one a second later
        stored = " ".join(f"{r.share_id} {r.day} {r.visitor}" for r in rows)
    assert "testclient" not in stored and "python" not in stored.lower()


def test_share_fixtures_consistent():
    m = house()
    files = blobs_by_sha()
    for f in m["files"]:
        assert hashlib.sha256(files[f["sha256"]]).hexdigest() == f["sha256"] and len(files[f["sha256"]]) == f["bytes"]
    for case in fixture_json("manifest-invalid.json")["cases"]:
        assert case["manifest"]["schema"] in ("truebex-share/1", "truebex-share/2")
    visits = fixture_json("visits.json")
    assert visits["expect"]["total"] == len(visits["visits"])


def test_demo_share_script(client, monkeypatch, capsys):
    """scripts/demo_share.py (the human test's uploader) sends every part once."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("demo_share", Path(__file__).parents[1] / "scripts" / "demo_share.py")
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)

    class _Same:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return client

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(demo.httpx, "Client", _Same)
    token, _ = device_token(client)
    fixture = str(Path(__file__).parent / "contracts" / "share-bundle" / "manifest-house.json")
    argv = ["--token", token, "--fixture", fixture, "--api", "http://testserver"]
    assert demo.main(argv) == 0
    first = capsys.readouterr().out
    assert "5 parts sent" in first and "state live" in first
    assert demo.main(argv) == 0
    second = capsys.readouterr().out
    assert "0 parts sent" in second
    # Signing in instead of passing a token reaches the same share.
    client.post("/auth/register", json={"email": "demo@example.com", "password": "password123"})
    login = ["--email", "demo@example.com", "--password", "password123", "--fixture", fixture, "--api", "http://testserver"]
    assert demo.main(login) == 0
    third = capsys.readouterr().out
    assert "device token tbx_dev_" in third and "5 parts sent" in third
    url = [line for line in first.splitlines() if line.startswith("url ")]
    assert url and url == [line for line in second.splitlines() if line.startswith("url ")]
