"""Write the marketplace contract's §9 fixtures (marketplace-api.md v1.1.0).

    cd server
    .venv\\Scripts\\python.exe scripts\\make_market_fixtures.py [--out DIR] [--check]

The app repo's Docs/roadmap/fixtures/contracts/marketplace/ is the master copy
(the app side is authoritative); MK1 owns it, but PF7 landed first, so this
script made the first version (as PF1 did for the licence fixtures).

* Inputs, written from the tables below: `products.json` (the stub's
  catalogue: one supplier, the Oslo sofa with two variants priced in GB and
  AE, a discontinued coffee table and the coffee table that substitutes for
  it, a paint, a wallpaper and a theme that includes three of them),
  `media-map.json`, `geometry/`, `thumbs/`, `feed-two-regions.csv` and
  `.json`, and a byte copy of GD1's catalogue template.
* Answers, made by running this server in-process on a scratch database
  with a fixed clock and fixed ids: `categories.json`, `regions.json`
  (5.1, 5.2), `prices-gb.json`, `prices-ae.json` (5.5),
  `order-awaiting-payment.json` (5.7), `order-quoted.json` (5.9 after the
  supplier quoted), `feed-report.json` (5.13: the feed into an empty
  catalogue). Responses are `{request, http_status, body}`.

Pictures are written only when missing (a PNG's bytes may change with the
zlib version); `--check` regenerates everything in a scratch folder and fails
if a text file differs, image URLs masked.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import struct
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]
OUT = SERVER / "tests" / "contracts" / "marketplace"
GD1_TEMPLATE = Path(r"T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\guides\GD1-supplier-catalogue-template.csv")

AT = "2026-10-09T10:00:00Z"
CDN = "https://cdn.example.com/catalogue"


def hex32(label: str) -> str:
    return hashlib.sha256(f"truebex-market-fixture\n{label}".encode()).hexdigest()[:32]


SUPPLIER_ID = hex32("supplier nord-living")
FEED_SUPPLIER_ID = hex32("supplier feed-test")
BUYER = {"email": "buyer@example.com", "password": "password123"}


def pid(sku: str) -> str:
    return hex32(f"product {sku}")


def gbp(amount: int) -> dict:
    return {"amount": amount, "currency": "GBP", "exponent": 2, "region": "GB", "includes_tax": True, "tax_rate_bp": 2000, "at": AT}


def aed(amount: int) -> dict:
    return {"amount": amount, "currency": "AED", "exponent": 2, "region": "AE", "includes_tax": True, "tax_rate_bp": 500, "at": AT}


def delivery(currency: str, fee: int | None, lo: int | None, hi: int | None) -> dict | None:
    if fee is None and lo is None:
        return None
    return {"fee": {"amount": fee or 0, "currency": currency, "exponent": 2}, "days_min": lo, "days_max": hi}


def avail(state: str, stock: int | None = None, lead: int | None = None) -> dict:
    return {"state": state, "stock": stock, "lead_time_days": lead, "updated_at": AT}


SOFA_ASSET_OAT = {"id": hex32("asset sofa-oslo oat-linen"), "name": "Oslo 3-seater", "rev": 3, "kind": "object"}
SOFA_ASSET_CHARCOAL = {"id": hex32("asset sofa-oslo charcoal-wool"), "name": "Oslo 3-seater", "rev": 3, "kind": "object"}
SOFA_DESCRIPTION = "Three-seat sofa on a solid oak frame, with removable covers."

# (file, size, background RGB, shape RGB, shape) — drawn once, 512 px or more.
PICTURES = {
    "thumbs/sofa-oslo-oat.png": ((640, 512), (236, 229, 214), (201, 184, 150), "sofa"),
    "thumbs/sofa-oslo-charcoal.png": ((640, 512), (236, 236, 236), (70, 72, 78), "sofa"),
    "thumbs/table-aker.png": ((512, 512), (245, 240, 232), (150, 104, 64), "table"),
    "thumbs/table-fjord.png": ((512, 512), (240, 244, 246), (196, 170, 128), "table"),
    "thumbs/paint-chalk.png": ((512, 512), (210, 214, 220), (250, 248, 242), "tin"),
    "thumbs/wallpaper-lattice.png": ((512, 512), (176, 196, 170), (232, 238, 226), "lattice"),
    "thumbs/theme-nordic.png": ((768, 512), (228, 222, 210), (120, 140, 150), "room"),
    "thumbs/chair-bergen.png": ((512, 640), (232, 236, 228), (110, 124, 84), "chair"),
}


def products() -> list[dict]:
    sofa = tbxa()
    sofa_geometry = {
        "file": "geometry/sofa-oslo.tbxa",
        "format": "tbxa",
        "sha256": hashlib.sha256(sofa).hexdigest(),
        "bytes": len(sofa),
    }
    return [
        {
            "product_id": pid("SOFA-OSLO-3"),
            "sku": "SOFA-OSLO-3",
            "name": "Oslo 3-seater sofa",
            "kind": "object",
            "category": "furniture/seating/sofas",
            "description": SOFA_DESCRIPTION,
            "brand": "Nord Living",
            "classification": ["uniclass:Pr_40_50_12_81"],
            "images": ["thumbs/sofa-oslo-oat.png", "thumbs/sofa-oslo-charcoal.png"],
            "includes": [],
            "status": "approved",
            "variants": [
                {
                    "variant_id": "oat-linen",
                    "gtin": "9501101530003",
                    "options": {"size": "3-seater", "colour": "Oat", "finish": "Linen"},
                    "dims_mm": [2100, 850, 950],
                    "materials": ["linen", "oak"],
                    "geometry": {**sofa_geometry, "asset": SOFA_ASSET_OAT},
                    "geometry_url": f"{CDN}/sofa-oslo-3/sofa-oslo.tbxa",
                    "images": ["thumbs/sofa-oslo-oat.png"],
                    "image_urls": [f"{CDN}/sofa-oslo-3/oat-linen-1.png"],
                    "regions": {
                        "GB": {"price": gbp(129900), "delivery": delivery("GBP", 4900, 7, 14), "availability": avail("in_stock", 12)},
                        "AE": {"price": aed(129900), "delivery": delivery("AED", 15000, 7, 14), "availability": avail("in_stock", 4)},
                    },
                },
                {
                    "variant_id": "charcoal-wool",
                    "gtin": "9501101530010",
                    "options": {"size": "3-seater", "colour": "Charcoal", "finish": "Wool"},
                    "dims_mm": [2100, 850, 950],
                    "materials": ["wool", "oak"],
                    "geometry": {**sofa_geometry, "asset": SOFA_ASSET_CHARCOAL},
                    "geometry_url": f"{CDN}/sofa-oslo-3/sofa-oslo.tbxa",
                    "images": ["thumbs/sofa-oslo-charcoal.png"],
                    "image_urls": [f"{CDN}/sofa-oslo-3/charcoal-wool-1.png"],
                    "regions": {
                        "GB": {"price": gbp(144900), "delivery": delivery("GBP", 4900, 7, 14), "availability": avail("made_to_order", None, 42)},
                        "AE": {"price": aed(144900), "delivery": delivery("AED", 15000, 7, 14), "availability": avail("made_to_order", None, 42)},
                    },
                },
            ],
        },
        {
            "product_id": pid("TABLE-AKER-CT"),
            "sku": "TABLE-AKER-CT",
            "name": "Aker coffee table",
            "kind": "object",
            "category": "furniture/tables/coffee-tables",
            "description": "Low oak coffee table with a lower shelf. No longer made.",
            "brand": "Nord Living",
            "images": ["thumbs/table-aker.png"],
            "status": "approved",
            "variants": [
                {
                    "variant_id": "default",
                    "options": {"colour": "Oak"},
                    "dims_mm": [1200, 420, 600],
                    "materials": ["oak"],
                    "status": "discontinued",
                    "images": ["thumbs/table-aker.png"],
                    "regions": {
                        "GB": {"price": gbp(24900), "delivery": delivery("GBP", 2900, 5, 10), "availability": avail("discontinued")},
                        "AE": {"price": aed(114900), "delivery": delivery("AED", 9000, 7, 14), "availability": avail("discontinued")},
                    },
                }
            ],
        },
        {
            "product_id": pid("TABLE-FJORD-CT"),
            "sku": "TABLE-FJORD-CT",
            "name": "Fjord coffee table",
            "kind": "object",
            "category": "furniture/tables/coffee-tables",
            "description": "Ash coffee table with rounded corners.",
            "brand": "Nord Living",
            "images": ["thumbs/table-fjord.png"],
            "status": "approved",
            "variants": [
                {
                    "variant_id": "default",
                    "options": {"colour": "Ash"},
                    "dims_mm": [1100, 400, 550],
                    "materials": ["ash"],
                    "images": ["thumbs/table-fjord.png"],
                    "regions": {
                        "GB": {"price": gbp(27900), "delivery": delivery("GBP", 2900, 5, 10), "availability": avail("in_stock", 20)},
                        "AE": {"price": aed(119900), "delivery": delivery("AED", 9000, 7, 14), "availability": avail("in_stock", 8)},
                    },
                }
            ],
        },
        {
            "product_id": pid("PAINT-CHALK"),
            "sku": "PAINT-CHALK",
            "name": "Chalk White matt emulsion",
            "kind": "finish",
            "category": "finishes/paint/interior",
            "description": "Water-based matt emulsion for interior walls and ceilings.",
            "brand": "Nord Living",
            "images": ["thumbs/paint-chalk.png"],
            "status": "approved",
            "variants": [
                {
                    "variant_id": "2-5l",
                    "options": {"size": "2.5 L", "colour": "Chalk White", "finish": "Matt"},
                    "dims_mm": None,
                    "materials": ["acrylic emulsion"],
                    "images": ["thumbs/paint-chalk.png"],
                    "regions": {
                        "GB": {"price": gbp(4200), "delivery": delivery("GBP", 495, 2, 4), "availability": avail("in_stock", 120)},
                        "AE": {"price": aed(18900), "delivery": delivery("AED", 2500, 3, 5), "availability": avail("in_stock", 60)},
                    },
                }
            ],
        },
        {
            "product_id": pid("WP-LATTICE"),
            "sku": "WP-LATTICE",
            "name": "Lattice wallpaper",
            "kind": "finish",
            "category": "finishes/wallpaper/patterned",
            "description": "Non-woven wallpaper with a fine lattice pattern, 10 m roll.",
            "brand": "Nord Living",
            "images": ["thumbs/wallpaper-lattice.png"],
            "status": "approved",
            "variants": [
                {
                    "variant_id": "sage",
                    "options": {"size": "10 m roll", "colour": "Sage"},
                    "dims_mm": None,
                    "materials": ["non-woven paper"],
                    "images": ["thumbs/wallpaper-lattice.png"],
                    "regions": {
                        "GB": {"price": gbp(6500), "delivery": delivery("GBP", 495, 2, 4), "availability": avail("low_stock", 3)},
                        "AE": {"price": aed(29900), "delivery": delivery("AED", 2500, 3, 5), "availability": avail("in_stock", 40)},
                    },
                }
            ],
        },
        {
            "product_id": pid("THEME-NORDIC-LIVING"),
            "sku": "THEME-NORDIC-LIVING",
            "name": "Nordic calm living room",
            "kind": "theme",
            "category": "decoration/themes",
            "description": "A calm living-room theme: the Oslo sofa, Chalk White walls and a sage lattice feature wall.",
            "brand": "Nord Living",
            "images": ["thumbs/theme-nordic.png"],
            "includes": [
                {"supplier_id": SUPPLIER_ID, "sku": "SOFA-OSLO-3", "variant_id": "oat-linen"},
                {"supplier_id": SUPPLIER_ID, "sku": "PAINT-CHALK", "variant_id": "2-5l"},
                {"supplier_id": SUPPLIER_ID, "sku": "WP-LATTICE", "variant_id": "sage"},
            ],
            "status": "approved",
            "variants": [
                {
                    "variant_id": "default",
                    "options": {},
                    "dims_mm": None,
                    "materials": [],
                    "images": ["thumbs/theme-nordic.png"],
                    "regions": {
                        "GB": {"price": gbp(1900), "delivery": None, "availability": avail("in_stock")},
                        "AE": {"price": aed(8900), "delivery": None, "availability": avail("in_stock")},
                    },
                }
            ],
        },
    ]


def catalogue() -> dict:
    return {
        "schema": "truebex-market-fixture/1",
        "note": (
            "The stub's catalogue (contract marketplace-api §9). Each variant carries its §6.3 price, delivery and "
            "availability per region under `regions`; the stub answers 5.3-5.5 for the asked region from them. "
            "`images` and `geometry.file` are files beside this one; `geometry_url` and `image_urls` are the URLs "
            "the feed files give for the same files (media-map.json). Fixture data, never public copy."
        ),
        "at": AT,
        "supplier": {
            "supplier_id": SUPPLIER_ID,
            "name": "Nord Living",
            "legal_name": "Nord Living Ltd",
            "country": "GB",
            "company_number": "00000000",
            "vat_id": "GB000000000",
            "website": "https://nordliving.example.com",
            "contact_email": "orders@nordliving.example.com",
            "regions": ["GB", "AE"],
            "verified": True,
        },
        "products": products(),
    }


# --- The feed (6 rows: the sofa's two variants and the Bergen chair, GB and AE) -------------

FEED_COLUMNS = [
    "sku", "variant_id", "name", "category", "kind", "option_size", "option_colour", "option_finish", "materials",
    "width_mm", "height_mm", "depth_mm", "geometry_url", "image_urls", "region", "currency", "price",
    "price_includes_tax", "tax_rate_percent", "delivery_fee", "delivery_days_min", "delivery_days_max", "stock",
    "lead_time_days", "status", "description", "brand", "gtin", "classification", "availability",
]  # fmt: skip


def gtin_with_check(body: str) -> str:
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return body + str((10 - total % 10) % 10)


BERGEN_GTIN = gtin_with_check("950110153002")


def feed_rows() -> list[dict]:
    sofa = {
        "sku": "SOFA-OSLO-3", "name": "Oslo 3-seater sofa", "category": "furniture/seating/sofas", "kind": "object",
        "option_size": "3-seater", "width_mm": "2100", "height_mm": "850", "depth_mm": "950",
        "geometry_url": f"{CDN}/sofa-oslo-3/sofa-oslo.tbxa", "price_includes_tax": "true",
        "status": "active", "description": SOFA_DESCRIPTION, "brand": "Nord Living",
        "classification": "uniclass:Pr_40_50_12_81", "availability": "",
    }  # fmt: skip
    oat = {**sofa, "variant_id": "oat-linen", "option_colour": "Oat", "option_finish": "Linen", "materials": "linen;oak",
           "image_urls": f"{CDN}/sofa-oslo-3/oat-linen-1.png", "gtin": "9501101530003", "lead_time_days": ""}  # fmt: skip
    charcoal = {**sofa, "variant_id": "charcoal-wool", "option_colour": "Charcoal", "option_finish": "Wool",
                "materials": "wool;oak", "image_urls": f"{CDN}/sofa-oslo-3/charcoal-wool-1.png",
                "gtin": "9501101530010", "stock": "", "lead_time_days": "42"}  # fmt: skip
    chair = {
        "sku": "CHAIR-BERGEN", "variant_id": "olive-boucle", "name": "Bergen lounge chair",
        "category": "furniture/seating/armchairs", "kind": "object", "option_size": "", "option_colour": "Olive",
        "option_finish": "Boucle", "materials": "boucle;beech", "width_mm": "780", "height_mm": "760",
        "depth_mm": "820", "geometry_url": f"{CDN}/chair-bergen/olive-boucle.glb",
        "image_urls": f"{CDN}/chair-bergen/olive-boucle-1.png", "price_includes_tax": "true", "status": "active",
        "description": "Lounge chair in olive boucle on a beech frame.", "brand": "Nord Living",
        "gtin": BERGEN_GTIN, "classification": "uniclass:Pr_40_50_12_02", "availability": "", "lead_time_days": "",
    }  # fmt: skip
    gb = {"region": "GB", "currency": "GBP", "tax_rate_percent": "20"}
    ae = {"region": "AE", "currency": "AED", "tax_rate_percent": "5"}
    rows = [
        {**oat, **gb, "price": "1299.00", "delivery_fee": "49.00", "delivery_days_min": "7", "delivery_days_max": "14", "stock": "12"},
        {**oat, **ae, "price": "1299.00", "delivery_fee": "150.00", "delivery_days_min": "7", "delivery_days_max": "14", "stock": "4"},
        {**charcoal, **gb, "price": "1449.00", "delivery_fee": "49.00", "delivery_days_min": "7", "delivery_days_max": "14"},
        {**charcoal, **ae, "price": "1449.00", "delivery_fee": "150.00", "delivery_days_min": "7", "delivery_days_max": "14"},
        {**chair, **gb, "price": "649.00", "delivery_fee": "39.00", "delivery_days_min": "5", "delivery_days_max": "10", "stock": "7"},
        {**chair, **ae, "price": "2999.00", "delivery_fee": "120.00", "delivery_days_min": "7", "delivery_days_max": "14", "stock": "3"},
    ]
    return [{c: r.get(c, "") for c in FEED_COLUMNS} for r in rows]


def feed_csv() -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(FEED_COLUMNS)
    for row in feed_rows():
        writer.writerow([row[c] for c in FEED_COLUMNS])
    return buf.getvalue().encode("utf-8")


def feed_json() -> dict:
    """The same rows nested as contract §6.4's JSON feed."""
    out: dict[str, dict] = {}
    for r in feed_rows():
        p = out.setdefault(r["sku"], {
            "sku": r["sku"], "name": r["name"], "category": r["category"], "kind": r["kind"],
            "description": r["description"], "brand": r["brand"], "classification": r["classification"].split(";"),
            "variants": [],
        })  # fmt: skip
        v = next((x for x in p["variants"] if x["variant_id"] == r["variant_id"]), None)
        if v is None:
            v = {
                "variant_id": r["variant_id"], "gtin": r["gtin"],
                "options": {k: r[f"option_{k}"] for k in ("size", "colour", "finish") if r[f"option_{k}"]},
                "materials": r["materials"].split(";"),
                "dims_mm": [int(r["width_mm"]), int(r["height_mm"]), int(r["depth_mm"])],
                "geometry_url": r["geometry_url"], "image_urls": r["image_urls"].split(";"), "prices": [],
            }  # fmt: skip
            p["variants"].append(v)
        price = {k: r[k] for k in ("region", "currency", "price", "tax_rate_percent", "delivery_fee") if r[k]}
        price["price_includes_tax"] = r["price_includes_tax"] == "true"
        for k in ("delivery_days_min", "delivery_days_max", "stock", "lead_time_days"):
            if r[k]:
                price[k] = int(r[k])
        v["prices"].append(price)
    return {"schema": "truebex-feed/1", "products": list(out.values())}


def media_map() -> dict:
    return {
        "note": "The https URLs the feed files and products.json name, and the fixture file each stands for (tests and the seed script fetch nothing from the internet).",
        "urls": {
            f"{CDN}/sofa-oslo-3/sofa-oslo.tbxa": "geometry/sofa-oslo.tbxa",
            f"{CDN}/sofa-oslo-3/oat-linen-1.png": "thumbs/sofa-oslo-oat.png",
            f"{CDN}/sofa-oslo-3/charcoal-wool-1.png": "thumbs/sofa-oslo-charcoal.png",
            f"{CDN}/chair-bergen/olive-boucle.glb": "geometry/chair-bergen.glb",
            f"{CDN}/chair-bergen/olive-boucle-1.png": "thumbs/chair-bergen.png",
        },
    }


def tbxa() -> bytes:
    doc = {
        "assetVersion": 1,
        "note": "Fixture stand-in for the Oslo sofa's O1 object asset (MK1 replaces it with the real asset; the platform only stores, hashes and serves the file).",
        "assetDef": {
            "id": SOFA_ASSET_OAT["id"],
            "name": "Oslo 3-seater",
            "revision": 3,
            "kind": "object",
            "category": "furniture/seating",
            "bounds_mm": [2100, 850, 950],
        },
    }
    return (json.dumps(doc, indent=2) + "\n").encode("utf-8")


def glb() -> bytes:
    """The smallest valid binary glTF (a header and a JSON chunk)."""
    body = json.dumps({"asset": {"version": "2.0", "generator": "truebex market fixtures"}}, separators=(",", ":")).encode()
    body += b" " * (-len(body) % 4)
    return b"glTF" + struct.pack("<II", 2, 12 + 8 + len(body)) + struct.pack("<I", len(body)) + b"JSON" + body


def picture(size, background, colour, shape) -> bytes:
    from PIL import Image, ImageDraw

    w, h = size
    img = Image.new("RGB", size, background)
    d = ImageDraw.Draw(img)
    if shape == "sofa":
        d.rectangle([w * 0.12, h * 0.40, w * 0.88, h * 0.70], fill=colour)
        d.rectangle([w * 0.12, h * 0.28, w * 0.88, h * 0.45], fill=tuple(max(0, c - 25) for c in colour))
        d.rectangle([w * 0.08, h * 0.36, w * 0.16, h * 0.72], fill=colour)
        d.rectangle([w * 0.84, h * 0.36, w * 0.92, h * 0.72], fill=colour)
    elif shape == "table":
        d.rectangle([w * 0.15, h * 0.42, w * 0.85, h * 0.50], fill=colour)
        for x in (0.20, 0.76):
            d.rectangle([w * x, h * 0.50, w * (x + 0.04), h * 0.72], fill=colour)
    elif shape == "tin":
        d.ellipse([w * 0.30, h * 0.20, w * 0.70, h * 0.32], fill=colour)
        d.rectangle([w * 0.30, h * 0.26, w * 0.70, h * 0.78], fill=colour)
    elif shape == "lattice":
        for i in range(0, w, 48):
            d.line([(i, 0), (i + h, h)], fill=colour, width=6)
            d.line([(i, h), (i + h, 0)], fill=colour, width=6)
    elif shape == "room":
        d.rectangle([0, h * 0.70, w, h], fill=(196, 170, 128))
        d.rectangle([w * 0.25, h * 0.45, w * 0.75, h * 0.70], fill=(201, 184, 150))
        d.rectangle([w * 0.78, h * 0.10, w * 0.95, h * 0.70], fill=colour)
    elif shape == "chair":
        d.rectangle([w * 0.25, h * 0.30, w * 0.75, h * 0.62], fill=colour)
        d.rectangle([w * 0.28, h * 0.62, w * 0.34, h * 0.80], fill=(150, 120, 80))
        d.rectangle([w * 0.66, h * 0.62, w * 0.72, h * 0.80], fill=(150, 120, 80))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


README = """# Marketplace contract fixtures (marketplace-api.md v1.1.0, §9)

Made by PF7 on 2026-10-09 with `server/scripts/make_market_fixtures.py` (deterministic: re-running
reproduces the text files; `--check` compares them). From the merge on, the master copy is the app repo's
`Docs/roadmap/fixtures/contracts/marketplace/` (MK1 owns it); the platform keeps a copy here, copied,
never edited. Fixture data, never public copy.

| File | Holds |
|---|---|
| `products.json` | the stub's catalogue: supplier Nord Living (verified, GB and AE) and its products — the Oslo sofa (`oat-linen`, `charcoal-wool`), the discontinued Aker coffee table, the Fjord coffee table that substitutes for it, a paint, a wallpaper and a theme that includes the sofa, the paint and the wallpaper; each variant's §6.3 price, delivery and availability per region under `regions` |
| `geometry/sofa-oslo.tbxa`, `geometry/chair-bergen.glb` | the sofa's object asset (a stand-in with an S1 id until MK1 writes the real one) and the smallest valid GLB for the feed's chair |
| `thumbs/*.png` | one picture per product (≥ 512 px, as §6.4 asks) |
| `media-map.json` | the https URLs the feeds name → these files (nothing is fetched from the internet) |
| `categories.json`, `regions.json` | 5.1 and 5.2 after loading `products.json` |
| `prices-gb.json`, `prices-ae.json` | 5.5 for the sofa's two variants, the Aker table (discontinued: substitutes) and the paint |
| `order-awaiting-payment.json` | 5.7: an order in AE (sofa and paint), payments on and the supplier onboarded |
| `order-quoted.json` | 5.9: a request for quote in AE after the supplier quoted AED 1,180.00 for the sofa |
| `feed-two-regions.csv`, `feed-two-regions.json` | a feed with GB and AE price lists: the sofa's two variants and the Bergen lounge chair (6 rows) |
| `feed-report.json` | 5.13 for `feed-two-regions.csv` imported into an empty catalogue |
| `GD1-supplier-catalogue-template.csv` | a byte copy of `guides/GD1-supplier-catalogue-template.csv` (contract 1.1.0) |

Answers are `{request, http_status, body}` as this server gives them (fixed clock `2026-10-09T10:00:00Z`,
fixed ids). Image URLs carry the SHA-256 of the stored JPEG and are masked when `--check` compares.
"""


# --- Answers from the server -----------------------------------------------------------------


def answers(folder: Path) -> dict[str, dict]:
    """Run this server in-process against `folder`'s inputs; return the
    answer fixtures. Must run in a fresh process (settings are read once)."""
    scratch = Path(tempfile.mkdtemp(prefix="truebex-market-fixtures-"))
    os.environ.update(
        {
            "DATABASE_URL": f"sqlite:///{scratch.as_posix()}/fixtures.db",
            "STORAGE_DIR": str(scratch / "storage"),
            "SECRET_KEY": "market-fixtures-secret-key-0123456789abcdef",
            "STORAGE_URL_SECRET": "market-fixtures-storage",
            "API_URL": "https://api.truebex.com",
            "SITE_URL": "https://truebex.com",
            "BACKGROUND_TASKS": "off",
            "MARKET_PAYMENTS_ENABLED": "true",
            "STRIPE_SECRET_KEY": "sk_test_fixtures",
            "EMBEDDING_MODEL": "",
            "LICENCE_SIGNING_KEY": "",
        }
    )
    sys.path.insert(0, str(SERVER))
    from fastapi.testclient import TestClient

    from app.database import SessionLocal
    from app.licence import clock
    from app.main import app
    from app.market import catalogue as m_catalogue
    from app.market import commissions as m_commissions
    from app.market import importer as m_importer
    from app.market import orders as m_orders
    from app.market import reviews as m_reviews
    from app.market import seed as m_seed
    from app.market.schemas import SupplierQuoteIn

    fixed = datetime(2026, 10, 9, 10, 0, 0, tzinfo=timezone.utc)
    clock.now = lambda: fixed
    counter = iter(range(1, 10_000))

    def next_id() -> str:
        return hex32(f"id {next(counter)}")

    for mod in (m_catalogue, m_orders, m_importer, m_reviews, m_commissions):
        mod.new_id = next_id

    out: dict[str, dict] = {}
    contract = {"X-Truebex-Contract": "marketplace-api/1.1"}
    with TestClient(app) as client:
        token = client.post("/auth/register", json=BUYER).json()["access_token"]
        session = {"Authorization": f"Bearer {token}", **contract}
        with SessionLocal() as db:
            m_seed.load_fixture(db, folder, payments_ready=True)

        def answer(method: str, path: str, *, body=None, headers=None, request=None):
            res = client.request(method, path, json=body, headers={**contract, **(headers or {})})
            entry = {"request": request or {"method": method, "path": path, **({"body": body} if body is not None else {})}}
            entry.update({"http_status": res.status_code, "body": res.json()})
            return entry

        out["categories"] = answer("GET", "/market/categories")
        out["regions"] = answer("GET", "/market/regions")
        items = [
            {"supplier_id": SUPPLIER_ID, "sku": "SOFA-OSLO-3", "variant_id": "oat-linen", "qty": 1},
            {"supplier_id": SUPPLIER_ID, "sku": "SOFA-OSLO-3", "variant_id": "charcoal-wool", "qty": 1},
            {"supplier_id": SUPPLIER_ID, "sku": "TABLE-AKER-CT", "variant_id": "default", "qty": 1},
            {"supplier_id": SUPPLIER_ID, "sku": "PAINT-CHALK", "variant_id": "2-5l", "qty": 4},
        ]
        out["prices-gb"] = answer("POST", "/market/prices", body={"region": "GB", "items": items})
        out["prices-ae"] = answer("POST", "/market/prices", body={"region": "AE", "items": items})

        order = {
            "kind": "order",
            "region": "AE",
            "project": {"name": "House", "project_id": None},
            "contact": {"name": "Layla Haddad", "email": BUYER["email"], "phone": None, "message": "Delivery after 1 Dec"},
            "delivery": {"country": "AE", "city": "Dubai", "postcode": None},
            "lines": [
                {"supplier_id": SUPPLIER_ID, "sku": "SOFA-OSLO-3", "variant_id": "oat-linen", "qty": 1,
                 "price_seen": aed(129900)},
                {"supplier_id": SUPPLIER_ID, "sku": "PAINT-CHALK", "variant_id": "2-5l", "qty": 4,
                 "price_seen": aed(18900)},
            ],
        }  # fmt: skip
        key = hex32("idempotency order")
        res = client.post("/market/orders", json=order, headers={**session, "Idempotency-Key": key})
        out["order-awaiting-payment"] = {
            "request": {"method": "POST", "path": "/market/orders", "headers": {"Idempotency-Key": key}, "body": order},
            "http_status": res.status_code,
            "body": res.json(),
        }

        quote = {**order, "kind": "quote", "lines": [{**order["lines"][0]}]}
        res = client.post("/market/orders", json=quote, headers={**session, "Idempotency-Key": hex32("idempotency quote")})
        quote_id = res.json()["order_id"]
        with SessionLocal() as db:
            row = m_orders.get_owned(db, _user(db, BUYER["email"]), quote_id)
            m_orders.supplier_quote(
                db,
                row,
                SUPPLIER_ID,
                SupplierQuoteIn(
                    lines=[{"sku": "SOFA-OSLO-3", "variant_id": "oat-linen", "unit_amount": 118000}],
                    delivery_fee=15000,
                    valid_days=30,
                    message="Delivered and assembled in Dubai within 10 days.",
                ),
            )
        res = client.get(f"/market/orders/{quote_id}", headers=session)
        out["order-quoted"] = {
            "request": {"method": "GET", "path": f"/market/orders/{quote_id}", "note": "after the supplier quoted"},
            "http_status": res.status_code,
            "body": res.json(),
        }

        with SessionLocal() as db:
            supplier = m_catalogue.create_supplier(db, supplier_id=FEED_SUPPLIER_ID, name="Feed Test Supplier", country="GB")
            supplier.status = "verified"
            db.commit()
            run = m_importer.run_feed(
                db, supplier, (folder / "feed-two-regions.csv").read_bytes(), "csv", "upsert",
                fetcher=m_seed.media_fetcher(folder),
            )  # fmt: skip
            out["feed-report"] = {
                "request": {"method": "GET", "path": f"/market/feeds/{run.feed_id}", "note": "feed-two-regions.csv (upsert) into an empty catalogue"},
                "http_status": 200,
                "body": m_importer.report_json(run),
            }
    shutil.rmtree(scratch, ignore_errors=True)
    return out


def _user(db, email):
    from sqlalchemy import select

    from app.models import User

    return db.scalar(select(User).where(User.email == email))


# --- Writing and checking ---------------------------------------------------------------------


def text_files() -> dict[str, bytes]:
    files = {
        "products.json": catalogue(),
        "media-map.json": media_map(),
        "feed-two-regions.json": feed_json(),
    }
    out = {name: (json.dumps(v, indent=2, ensure_ascii=False) + "\n").encode("utf-8") for name, v in files.items()}
    out["feed-two-regions.csv"] = feed_csv()
    out["geometry/sofa-oslo.tbxa"] = tbxa()
    out["README.md"] = README.encode("utf-8")
    return out


def binary_files(existing: Path) -> dict[str, bytes]:
    """Pictures and the GLB: kept when present (their bytes may differ by
    zlib version), made when missing. The GD1 template is copied."""
    out = {}
    for name, spec in PICTURES.items():
        out[name] = (existing / name).read_bytes() if (existing / name).is_file() else picture(*spec)
    out["geometry/chair-bergen.glb"] = glb()
    template = existing / "GD1-supplier-catalogue-template.csv"
    if GD1_TEMPLATE.is_file():
        out["GD1-supplier-catalogue-template.csv"] = GD1_TEMPLATE.read_bytes()
    elif template.is_file():
        out["GD1-supplier-catalogue-template.csv"] = template.read_bytes()
    return out


def build(existing: Path) -> dict[str, bytes]:
    stage = Path(tempfile.mkdtemp(prefix="truebex-market-stage-"))
    files = {**text_files(), **binary_files(existing)}
    for name, data in files.items():
        (stage / name).parent.mkdir(parents=True, exist_ok=True)
        (stage / name).write_bytes(data)
    for name, value in answers(stage).items():
        files[f"{name}.json"] = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    shutil.rmtree(stage, ignore_errors=True)
    return files


_MEDIA = re.compile(rb"/market/media/(images|thumbs)/[0-9a-f]{64}\.jpg")


def comparable(name: str, data: bytes) -> bytes:
    return _MEDIA.sub(rb"/market/media/\1/<sha>.jpg", data) if name.endswith(".json") else data


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--check", action="store_true", help="fail if the folder's text files differ from a fresh build")
    args = ap.parse_args(argv)
    out = Path(args.out)
    files = build(out)
    if args.check:
        text = {n: d for n, d in files.items() if not n.endswith((".png", ".glb"))}
        stale = [
            n for n, d in text.items()
            if not (out / n).is_file() or comparable(n, (out / n).read_bytes()) != comparable(n, d)
        ]  # fmt: skip
        if stale:
            print("differs: " + ", ".join(sorted(stale)))
            return 1
        print(f"{len(text)} fixture text files up to date")
        return 0
    for name, data in files.items():
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_bytes(data)
    print(f"wrote {len(files)} files to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
