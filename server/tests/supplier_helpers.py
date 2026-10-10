"""Shared helpers for the supplier portal tests (PF8)."""

import csv
import io
import json
import struct

from sqlalchemy import select

from app import mail
from app.database import SessionLocal
from app.market import media, seed
from app.models import User
from app.supplier import feeds

from .conftest import signup
from .market_helpers import CONTRACT, FIXTURES, make_admin

FEED_CSV = (FIXTURES / "feed-two-regions.csv").read_bytes()
FEED_JSON = (FIXTURES / "feed-two-regions.json").read_bytes()
GD1 = (FIXTURES / "GD1-supplier-catalogue-template.csv").read_bytes()
FEED_REPORT = json.loads((FIXTURES / "feed-report.json").read_text(encoding="utf-8"))["body"]


def application(name: str = "Nord Living", email: str = "orders@nord.example.com", regions=("GB", "AE")) -> dict:
    return {
        "name": name,
        "legal_name": f"{name} Ltd",
        "country": "GB",
        "company_number": "01234567",
        "vat_id": "GB123456789",
        "website": "https://nord.example.com",
        "address": {"line1": "1 Mill Lane", "city": "Leeds", "postcode": "LS1 1AA", "country": "GB"},
        "regions": list(regions),
        "contact": {"name": "Ingrid Berg", "email": email, "phone": "+44 113 000 0000"},
    }


def apply(client, email: str = "owner@nord.example.com", **kw) -> tuple[dict, str]:
    """A new account applies: (its headers, the supplier id)."""
    h = signup(client, email=email)
    res = client.post("/supplier/applications", json=application(**kw), headers=h)
    assert res.status_code == 201, res.text
    return h, res.json()["supplier_id"]


def as_supplier(headers: dict, supplier_id: str) -> dict:
    return {**headers, "X-Truebex-Supplier": supplier_id}


def admin_headers(client, email: str = "admin@example.com") -> dict:
    """The admin account (made once per test)."""
    res = client.post("/auth/login", json={"email": email, "password": "password123"})
    if res.status_code == 200:
        return {"Authorization": f"Bearer {res.json()['access_token']}"}
    return make_admin(client, email)


def verify(client, supplier_id: str, admin: dict | None = None) -> dict:
    admin = admin or admin_headers(client)
    res = client.patch(f"/admin/market/suppliers/{supplier_id}", json={"status": "verified"}, headers=admin)
    assert res.status_code == 200, res.text
    return admin


def verified(client, email: str = "owner@nord.example.com", **kw) -> tuple[dict, str]:
    h, sid = apply(client, email=email, **kw)
    verify(client, sid)
    return as_supplier(h, sid), sid


def supplier_key(client, headers: dict, name: str = "ERP feed") -> str:
    res = client.post("/supplier/keys", json={"name": name}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["key"]


def key_headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", **CONTRACT}


def post_feed(client, key: str, data: bytes, fmt: str = "csv", mode: str = "upsert", headers: dict | None = None):
    files = {"file": (f"feed.{fmt}", data, "text/csv" if fmt == "csv" else "application/json")}
    return client.post(
        "/market/feeds", data={"format": fmt, "mode": mode}, files=files, headers=headers or key_headers(key)
    )


def no_internet(monkeypatch, fetcher=None) -> None:
    """Feed media come from the contract fixtures, never the internet."""
    monkeypatch.setattr(media, "HttpFetcher", lambda: fetcher or seed.media_fetcher(FIXTURES))


def run_feeds() -> list:
    with SessionLocal() as db:
        return [r.feed_id for r in feeds.run_queued(db)]


def rows_of(data: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


def csv_of(rows: list[dict], columns: list[str] | None = None, bom: bool = False) -> bytes:
    columns = columns or list(rows[0])
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=columns, lineterminator="\r\n", extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return (b"\xef\xbb\xbf" if bom else b"") + buf.getvalue().encode("utf-8")


def outbox(subject_part: str = "", to: str | None = None) -> list:
    return [
        m for m in mail.OUTBOX if subject_part in m.subject and (to is None or m.to.lower() == to.lower())
    ]


def user_id(email: str) -> int:
    with SessionLocal() as db:
        return db.scalar(select(User.id).where(User.email == email))


def pdf(size: int = 2048) -> bytes:
    body = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj << /Type /Catalog >> endobj\n"
    return body + b"0" * max(0, size - len(body) - 6) + b"\n%%EOF"


def glb(triangles: int = 12, size_m=(0.78, 0.76, 0.82), *, extensions_required=None, nodes_scale=None) -> bytes:
    """A GLB whose JSON says `triangles` and a bounding box of `size_m` metres
    (accessors without buffers: the checks read only the JSON)."""
    w, h, d = size_m
    doc = {
        "asset": {"version": "2.0", "generator": "truebex tests"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, **({"scale": nodes_scale} if nodes_scale else {})}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "mode": 4}]}],
        "accessors": [
            {"componentType": 5126, "count": 8, "type": "VEC3", "min": [-w / 2, 0, -d / 2], "max": [w / 2, h, d / 2]},
            {"componentType": 5125, "count": triangles * 3, "type": "SCALAR"},
        ],
    }
    if extensions_required:
        doc["extensionsUsed"] = list(extensions_required)
        doc["extensionsRequired"] = list(extensions_required)
    raw = json.dumps(doc).encode()
    raw += b" " * (-len(raw) % 4)
    return struct.pack("<4sII", b"glTF", 2, 20 + len(raw)) + struct.pack("<II", len(raw), 0x4E4F534A) + raw
