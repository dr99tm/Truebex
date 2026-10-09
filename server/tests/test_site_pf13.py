"""PF13 build checks: the website's pricing, feature pages, roadmap, Arabic
page, changelog, analytics, verification and social links.

The checks read the static export in `out/` that the verify gate builds
before it runs pytest (`scripts/autopilot-verify.ps1`); they skip when `out/`
is absent. The script checks (sync-roadmap, IndexNow) need Node and skip
without it.

A build made with `TRUEBEX_CATALOGUE_FILE=<json>` (a sample catalogue with
prices) is checked against that file instead of `server/app/catalogue.json`.
"""

import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
SITE = "https://truebex.com"
CATALOGUE = ROOT / "server" / "app" / "catalogue.json"
CONTENT = ROOT / "src" / "content"
CONSTANTS = ROOT / "src" / "lib" / "constants.ts"

TIER_IDS = ["free", "pro", "studio", "team", "enterprise"]
FEATURE_SLUGS = ["daylight", "surfaces", "assets", "sheets", "marketplace"]
# The cluster phrase each feature page's h1 must carry (SEO keyword map).
FEATURE_PHRASES = {
    "daylight": "daylight",
    "surfaces": "wall panel",
    "assets": "asset",
    "sheets": "drawing sheets",
    "marketplace": "marketplace",
}
PUBLIC_PAGES = [
    "index.html",
    "pricing/index.html",
    "roadmap/index.html",
    "changelog/index.html",
    "ar/index.html",
    "developers/index.html",
    "privacy/index.html",
    "terms/index.html",
    *[f"features/{s}/index.html" for s in FEATURE_SLUGS],
]
# Entitlement keys that describe what the desktop app does today (the
# brand-voice skill's shipped list). Everything else in the matrix is
# roadmap and must say so on /pricing/. Kept here, apart from constants.ts,
# so a wrong flag in the copy cannot pass its own test.
SHIPPED_KEYS = {
    "export.pdf",
    "export.dxf",
    "export.clean",
    "lighting.full",
    "assets.library",
    "storeys",
    "devices",
    "api.monthly_requests",
}
BEACON = "static.cloudflareinsights.com/beacon.min.js"
# Brand rule 1: no other design software, engine or engine feature named.
DENY_NAMES = [
    "Revit", "AutoCAD", "Autodesk", "ArchiCAD", "Archicad", "Graphisoft",
    "SketchUp", "Trimble", "Rhino", "Grasshopper", "Vectorworks",
    "Chief Architect", "MicroStation", "Bentley Systems", "Allplan",
    "BricsCAD", "Enscape", "Lumion", "Twinmotion", "V-Ray", "D5 Render",
    "Unreal", "Unity", "Epic Games", "Lumen", "Nanite", "DLSS", "Blender",
    "3ds Max", "Cinema 4D", "Planner 5D", "Floorplanner", "Homestyler",
    "ريفيت", "أوتوكاد", "سكتش أب",
]
PLACEHOLDER_WORDS = re.compile(r"GD7|GD6|TODO|placeholder|lorem ipsum", re.I)
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "source", "track", "wbr"}


# --- helpers -------------------------------------------------------------------


class Doc(HTMLParser):
    """Every element with its attributes and full text content."""

    def __init__(self, html: str):
        super().__init__(convert_charrefs=True)
        self.elements: list[dict] = []
        self._stack: list[dict] = []
        self.html = html
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        el = {"tag": tag, "attrs": {k: (v or "") for k, v in attrs}, "text": []}
        self.elements.append(el)
        if tag not in VOID:
            self._stack.append(el)

    def handle_startendtag(self, tag, attrs):
        self.elements.append({"tag": tag, "attrs": {k: (v or "") for k, v in attrs}, "text": []})

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i]["tag"] == tag:
                del self._stack[i:]
                return

    def handle_data(self, data):
        for el in self._stack:
            el["text"].append(data)

    # queries
    def all(self, tag: str | None = None, **attrs) -> list[dict]:
        out = []
        for el in self.elements:
            if tag and el["tag"] != tag:
                continue
            ok = True
            for k, v in attrs.items():
                k = k.replace("_", "-")
                if v is True:
                    ok = ok and k in el["attrs"]
                else:
                    ok = ok and el["attrs"].get(k) == v
            if ok:
                out.append(el)
        return out

    @staticmethod
    def text(el: dict) -> str:
        return re.sub(r"\s+", " ", "".join(el["text"])).strip()

    def title(self) -> str:
        return self.text(self.all("title")[0])

    def meta(self, name: str) -> str | None:
        for el in self.all("meta"):
            if el["attrs"].get("name") == name or el["attrs"].get("property") == name:
                return el["attrs"].get("content")
        return None

    def canonical(self) -> str | None:
        for el in self.all("link", rel="canonical"):
            return el["attrs"].get("href")
        return None

    def json_ld(self) -> list[dict]:
        nodes = []
        for el in self.all("script", type="application/ld+json"):
            data = json.loads("".join(el["text"]))
            for node in data.get("@graph", [data]) if isinstance(data, dict) else data:
                nodes.append(node)
        return nodes

    def ld_types(self) -> set[str]:
        return {n.get("@type") for n in self.json_ld()}

    def visible_text(self) -> str:
        """Text a visitor or a crawler reads: no script/style bodies, plus
        meta descriptions, alt and title attributes and the JSON-LD."""
        parts = []
        skip_depth = 0

        class P(HTMLParser):
            def handle_starttag(self, tag, attrs):
                nonlocal skip_depth
                a = dict(attrs)
                if tag in ("script", "style") and a.get("type") != "application/ld+json":
                    skip_depth += 1
                for k in ("alt", "title", "aria-label"):
                    if a.get(k):
                        parts.append(a[k])
                if tag == "meta" and a.get("content") and (
                    a.get("name") in ("description", "twitter:title", "twitter:description")
                    or (a.get("property") or "").startswith("og:")
                ):
                    parts.append(a["content"])

            def handle_endtag(self, tag):
                nonlocal skip_depth
                if tag in ("script", "style") and skip_depth:
                    skip_depth -= 1

            def handle_data(self, data):
                if not skip_depth:
                    parts.append(data)

        P(convert_charrefs=True).feed(self.html)
        return " ".join(parts)

    def faq_visible(self) -> list[str]:
        return [self.text(el) for el in self.all(data_faq_question=True)]

    def faq_ld(self) -> list[str]:
        for node in self.json_ld():
            if node.get("@type") == "FAQPage":
                return [q["name"] for q in node["mainEntity"]]
        return []


def page(rel: str) -> Doc:
    path = OUT / rel
    assert path.exists(), f"{rel} missing from out/"
    return Doc(path.read_text(encoding="utf-8"))


def catalogue_path() -> Path:
    override = os.environ.get("TRUEBEX_CATALOGUE_FILE")
    return (ROOT / override) if override else CATALOGUE


def public_view(cat: dict) -> dict:
    """What the public pages show (src/lib/catalogue.ts publicCatalogue):
    prices and the founding offer only once `prices_final` is not false."""
    if cat.get("prices_final") is not False:
        return cat
    return {**cat, "tiers": [{**t, "prices": []} for t in cat["tiers"]], "founding": None}


def catalogue() -> dict:
    return public_view(json.loads(catalogue_path().read_text(encoding="utf-8")))


SYMBOL = {"GBP": "£", "USD": "$", "EUR": "€"}


def fmt_money(amount_minor: int, currency: str) -> str:
    """What the site prints: the symbol, grouped digits, pence only when
    the amount has them (src/lib/catalogue.ts formatMinor)."""
    value = amount_minor / 100
    body = f"{value:,.0f}" if amount_minor % 100 == 0 else f"{value:,.2f}"
    return f"{SYMBOL[currency]}{body}"


def priced(cat: dict) -> list[tuple[dict, dict]]:
    return [(t, p) for t in cat["tiers"] for p in (t.get("prices") or [])]


def founding_live(cat: dict) -> bool:
    f = cat.get("founding") or {}
    return bool(f.get("total")) and f.get("discount_percent") is not None


def constants_text() -> str:
    return CONSTANTS.read_text(encoding="utf-8")


def const_block(name: str) -> str:
    m = re.search(rf"export const {name}\b.*?\n\}}( as const)?;", constants_text(), re.S)
    if not m:
        m = re.search(rf"export const {name}\b.*?\n\]( as const)?;", constants_text(), re.S)
    assert m, f"{name} not found in constants.ts"
    return m.group(0)


def verification_tokens() -> dict[str, str]:
    block = const_block("VERIFICATION")
    google = re.search(r'google:\s*"([^"]*)"', block).group(1)
    bing = re.search(r'bing:\s*"([^"]*)"', block).group(1)
    return {
        "google": os.environ.get("TRUEBEX_GOOGLE_SITE_VERIFICATION", google),
        "bing": os.environ.get("TRUEBEX_BING_SITE_VERIFICATION", bing),
    }


def analytics_token() -> str:
    block = const_block("ANALYTICS")
    token = re.search(r'cloudflareToken:\s*"([^"]*)"', block).group(1)
    return os.environ.get("TRUEBEX_ANALYTICS_TOKEN", token)


def social_urls() -> set[str]:
    return {u for u in re.findall(r'url:\s*"([^"]*)"', const_block("SOCIAL")) if u}


@pytest.fixture(scope="module")
def built():
    if not (OUT / "index.html").exists():
        pytest.skip("out/ not built (the verify gate builds it before pytest)")
    return OUT


def node() -> str:
    exe = shutil.which("node")
    if not exe:
        pytest.skip("node not on PATH")
    return exe


def html_files() -> list[Path]:
    return [p for p in OUT.rglob("*.html") if "_next" not in p.parts]


# --- catalogue (no build needed) ----------------------------------------------


def test_site_pf13_catalogue_placeholder_shape():
    """`server/app/catalogue.json` is the licence contract's §6.3 placeholder
    in PF1's schema plus PF2's price fields; PF2's prices and founding offer
    are placeholders marked `prices_final: false` until GD7."""
    cat = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    tiers = cat["tiers"]
    assert [t["id"] for t in tiers] == TIER_IDS
    assert [t["rank"] for t in tiers] == sorted(t["rank"] for t in tiers)
    assert [t["name"] for t in tiers] == ["Free", "Pro", "Studio", "Team", "Enterprise"]
    free = tiers[0]
    assert free["features"] == sorted(["export.pdf", "export.dxf", "lighting.full", "render.panorama"])
    assert free["limits"] == {"storeys": 1, "devices": 2, "share_links": 1,
                              "cloud_cu_month": 0, "ai_credits_month": 0}
    gates = {"export.clean", "export.dwg", "export.ifc", "assets.library", "share.links",
             "vr.pc", "mep", "analysis.reports", "market.cost", "cloud.sync",
             "cloud.panoramas", "collab.live", "ai.byok", "ai.metered"}
    for t in tiers[1:]:
        assert t["features"] == sorted(set(free["features"]) | gates), t["id"]
        assert t["limits"] == {**free["limits"], "storeys": None}, t["id"]
        assert t["features"] == sorted(set(t["features"]))
    assert cat["prices_final"] is False, "prices wait for GD7"
    for t in tiers:
        assert isinstance(t["prices"], list)
        assert isinstance(t["per_seat"], bool) and t["min_seats"] >= 1
    assert cat["founding"] is None or {"total", "discount_percent", "ends_at"} <= set(cat["founding"])
    assert [t["purchasable"] for t in tiers] == [False, True, True, True, False]


def test_site_pf13_catalogue_api_quotas_match_plans():
    """Until PF1 makes plans.py read the catalogue, the two stay in step."""
    from app.plans import PLANS

    cat = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    for t in cat["tiers"]:
        if t["id"] in PLANS:
            plan = PLANS[t["id"]]
            assert t["api"] == {"monthly_requests": plan.monthly_requests,
                                "max_api_keys": plan.max_api_keys}, t["id"]


def test_site_pf13_content_files_valid():
    roadmap = json.loads((CONTENT / "roadmap.json").read_text(encoding="utf-8"))
    ids = [i["id"] for i in roadmap["items"]]
    assert len(ids) == len(set(ids)) and len(ids) >= 8
    for item in roadmap["items"]:
        assert item["title"] and item["description"] and item["icon"] and item["theme"]
        assert item["status"] in {"planned", "in_progress", "shipped"}
        assert item["plan_ids"] and all(re.fullmatch(r"[A-Z]{2}\d{1,2}", p) for p in item["plan_ids"])
        assert item["theme"] in {t["id"] for t in roadmap["themes"]}
    history = json.loads((CONTENT / "history.json").read_text(encoding="utf-8"))
    hids = [h["id"] for h in history]
    assert len(hids) == len(set(hids)) and len(history) >= 8
    for h in history:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", h["date"]) and h["title"] and h["summary"]
        assert re.fullmatch(r"[a-z0-9][a-z0-9.-]*", h["id"])
    assert [h["date"] for h in history] == sorted((h["date"] for h in history), reverse=True)
    releases = json.loads((CONTENT / "releases.json").read_text(encoding="utf-8"))
    assert releases["schema"] == "truebex-releases/1"


# --- pricing ---------------------------------------------------------------------


def test_site_pf13_pricing_page(built):
    doc = page("pricing/index.html")
    assert len(doc.all("h1")) == 1
    assert doc.canonical() == f"{SITE}/pricing/"
    assert len(doc.title()) <= 60 and doc.title().startswith("Pricing")
    desc = doc.meta("description")
    assert desc and 140 <= len(desc) <= 160, (len(desc or ""), desc)
    cat = catalogue()
    for tier in cat["tiers"]:
        cards = doc.all("article", data_tier=tier["id"])
        assert len(cards) == 1, tier["id"]
        assert tier["name"] in doc.text(cards[0])
    group = doc.all(role="radiogroup", aria_label="Billing interval")
    assert group, "monthly / annual toggle"
    labels = doc.text(group[0])
    assert "Monthly" in labels and "Annual" in labels
    currencies = doc.all(role="radiogroup", aria_label="Currency")
    assert currencies and all(c in doc.text(currencies[0]) for c in ("GBP", "USD", "EUR"))
    assert {"FAQPage", "SoftwareApplication", "BreadcrumbList"} <= doc.ld_types()
    # Calls to action: Start free -> sign-up, Enterprise -> contact.
    free_card = doc.all("article", data_tier="free")[0]
    assert "Start free" in doc.text(free_card)
    hrefs = {el["attrs"].get("href") for el in doc.all("a")}
    assert "/signup/" in hrefs and "/#contact" in hrefs
    for tier, _ in priced(cat):
        if tier["purchasable"]:
            assert any(h and h.startswith(f"/dashboard/billing/?tier={tier['id']}&interval=") for h in hrefs)
    # The founding block shows only when the catalogue has the numbers.
    assert bool(doc.all(data_founding=True)) == founding_live(cat)
    # The per-seat note on per-seat tiers.
    for tier in cat["tiers"]:
        card = doc.text(doc.all("article", data_tier=tier["id"])[0])
        if tier["per_seat"] and tier.get("prices"):
            assert "per seat" in card, tier["id"]


def test_site_pf13_pricing_matches_catalogue(built):
    cat = catalogue()
    table = {(t["id"], p["interval"], p["currency"]): p["amount_minor"] for t, p in priced(cat)}
    for rel in ("pricing/index.html", "index.html"):
        doc = page(rel)
        shown = doc.all(data_amount_minor=True)
        for el in shown:
            a = el["attrs"]
            key = (a["data-tier"], a["data-interval"], a["data-currency"])
            assert key in table, (rel, key)
            assert int(a["data-amount-minor"]) == table[key], (rel, key)
            assert doc.text(el) == fmt_money(table[key], a["data-currency"]), (rel, key)
        # Every priced tier shows its default (monthly, GBP) price.
        for (tid, interval, currency), amount in table.items():
            if interval == "month" and currency == "GBP" and doc.all("article", data_tier=tid):
                assert any(e["attrs"]["data-tier"] == tid for e in shown), (rel, tid)
        for tier in cat["tiers"]:
            cards = doc.all("article", data_tier=tier["id"])
            if not cards:
                continue
            text = doc.text(cards[0])
            if tier["purchasable"] and not tier.get("prices"):
                assert "Price at launch" in text, (rel, tier["id"])
            if tier.get("prices"):
                assert "Price at launch" not in text, (rel, tier["id"])
    # JSON-LD: one Offer per priced tier, interval and currency (+ Free at 0).
    doc = page("pricing/index.html")
    app = next(n for n in doc.json_ld() if n.get("@type") == "SoftwareApplication")
    got = {
        (o["priceCurrency"], o["price"], (o.get("priceSpecification") or {}).get("unitCode"))
        for o in app["offers"]
        if o["price"] != "0"
    }
    want = {
        (p["currency"], f"{p['amount_minor'] / 100:.2f}", {"month": "MON", "year": "ANN"}[p["interval"]])
        for _, p in priced(cat)
    }
    assert got == want
    assert any(o["price"] == "0" for o in app["offers"]), "the Free offer"


def test_site_pf13_placeholder_prices_stay_private(built):
    """PF2's placeholder prices (`prices_final: false`) stay off the public
    pages: no amounts, no priced JSON-LD offers, no founding block, and every
    paid tier says "Price at launch". The billing page lists them from the API."""
    raw = json.loads(catalogue_path().read_text(encoding="utf-8"))
    if raw.get("prices_final") is not False:
        pytest.skip("this catalogue's prices are final")
    assert priced(raw), "PF2's placeholder prices are in the catalogue"
    for rel in ("pricing/index.html", "index.html", "ar/index.html"):
        doc = page(rel)
        assert not doc.all(data_amount_minor=True), rel
        assert not doc.all(data_founding=True), rel
        for app in (n for n in doc.json_ld() if n.get("@type") == "SoftwareApplication"):
            assert all(o["price"] == "0" for o in app["offers"]), rel
    doc = page("pricing/index.html")
    for tier in raw["tiers"]:
        if tier["purchasable"]:
            assert "Price at launch" in doc.text(doc.all("article", data_tier=tier["id"])[0]), tier["id"]


def test_site_pf13_roadmap_rows_labelled(built):
    doc = page("pricing/index.html")
    rows = doc.all("tr", data_feature=True)
    keys = {r["attrs"]["data-feature"] for r in rows}
    cat = catalogue()
    matrix = {k for t in cat["tiers"] for k in t["features"]} | {
        k for t in cat["tiers"] for k in t["limits"]
    }
    assert matrix <= keys, f"matrix rows missing: {matrix - keys}"
    for row in rows:
        key = row["attrs"]["data-feature"]
        text = doc.text(row)
        if key in SHIPPED_KEYS:
            assert "On the roadmap" not in text, key
        else:
            assert "On the roadmap" in text, key
            assert row["attrs"].get("data-roadmap") == "true", key


# --- feature pages ---------------------------------------------------------------


def test_site_pf13_feature_pages(built):
    titles = set()
    for slug in FEATURE_SLUGS:
        doc = page(f"features/{slug}/index.html")
        h1 = doc.all("h1")
        assert len(h1) == 1, slug
        assert FEATURE_PHRASES[slug] in doc.text(h1[0]).lower(), (slug, doc.text(h1[0]))
        title = doc.title()
        assert len(title) <= 60 and title not in titles, (slug, title)
        titles.add(title)
        desc = doc.meta("description")
        assert desc and 140 <= len(desc) <= 160, (slug, len(desc or ""), desc)
        assert doc.canonical() == f"{SITE}/features/{slug}/"
        assert {"WebPage", "BreadcrumbList", "FAQPage"} <= doc.ld_types(), slug
        assert doc.meta("og:url") == f"{SITE}/features/{slug}/"
        assert doc.meta("og:image"), slug
        for img in doc.all("img"):
            a = img["attrs"]
            assert a.get("alt") and a.get("width") and a.get("height"), (slug, a)
        hrefs = {el["attrs"].get("href") for el in doc.all("a")}
        assert "/signup/" in hrefs, slug
        assert doc.all("a", data_cta="download"), slug
        assert doc.faq_visible(), slug


def test_site_pf13_marketplace_page_future_tense(built):
    doc = page("features/marketplace/index.html")
    text = doc.visible_text()
    assert "On the roadmap" in text
    for claim in ("available now", "now available", "shipping today", "live today",
                  "in Truebex today", "Buy now", "Order now", "all shipping"):
        assert claim.lower() not in text.lower(), claim
    assert not doc.all("img"), "no capture of a feature that does not exist yet"
    hrefs = [el["attrs"].get("href", "") for el in doc.all("a")]
    assert any("Supplier" in h or "supplier" in h for h in hrefs), "supplier interest link"


# --- roadmap -----------------------------------------------------------------


def test_site_pf13_roadmap_page(built):
    roadmap = json.loads((CONTENT / "roadmap.json").read_text(encoding="utf-8"))
    doc = page("roadmap/index.html")
    assert len(doc.all("h1")) == 1
    assert doc.canonical() == f"{SITE}/roadmap/"
    assert {"WebPage", "BreadcrumbList"} <= doc.ld_types()
    labels = {"planned": "Planned", "in_progress": "In progress", "shipped": "Shipped"}
    for item in roadmap["items"]:
        el = doc.all(data_roadmap_item=item["id"])
        assert len(el) == 1, item["id"]
        assert el[0]["attrs"]["data-status"] == item["status"]
        assert item["title"] in doc.text(el[0]) and labels[item["status"]] in doc.text(el[0])
    for theme in roadmap["themes"]:
        if any(i["theme"] == theme["id"] for i in roadmap["items"]):
            assert any(doc.text(h) == theme["title"] for h in doc.all("h2")), theme["id"]
    home = page("index.html")
    assert home.all("a", href="/roadmap/")
    assert home.all(data_roadmap_item=True), "the home roadmap block reads roadmap.json"


def test_site_pf13_sync_roadmap_script(tmp_path):
    exe = node()
    app = tmp_path / "app.md"
    app.write_text(
        "| Done | Feature | Needs | Ver | Prio | Code today | Notes |\n"
        "|---|---|---|---|---|---|---|\n"
        "| [x] | [IO1](IO1.md) DXF import | — | — | 1 | `main` | |\n"
        "| [ ] | [IO2](IO2.md) IFC export | CL0 | v40 | 2 | `ap/t3-io2` | |\n"
        "| [ ] | [IO4](IO4.md) DWG | IO1 | — | 2 | — | |\n"
        "| [x] | [LO1](LO1.md) Arabic UI | — | — | 1 | `main` | |\n",
        encoding="utf-8",
    )
    platform = tmp_path / "platform.md"
    platform.write_text(
        "| Done | Feature | Needs | Prio | Code today | Notes |\n"
        "|---|---|---|---|---|---|\n"
        "| [ ] | [PF5](PF5.md) share pages | PF1 | 1 | — | |\n",
        encoding="utf-8",
    )
    road = tmp_path / "roadmap.json"
    road.write_text(json.dumps({"themes": [{"id": "x", "title": "X"}], "items": [
        {"id": "exchange", "title": "t", "description": "d", "icon": "FileInput", "theme": "x",
         "plan_ids": ["IO1", "IO2", "IO4"], "status": "planned"},
        {"id": "arabic", "title": "t", "description": "d", "icon": "Languages", "theme": "x",
         "plan_ids": ["LO1"], "status": "planned"},
        {"id": "dwg", "title": "t", "description": "d", "icon": "FileInput", "theme": "x",
         "plan_ids": ["IO4", "PF5"], "status": "shipped"},
        {"id": "dxf", "title": "t", "description": "d", "icon": "FileInput", "theme": "x",
         "plan_ids": ["IO1"], "status": "planned"},
    ]}), encoding="utf-8")
    res = subprocess.run(
        [exe, str(ROOT / "scripts" / "sync-roadmap.mjs"), str(app), str(platform), "--roadmap", str(road)],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert res.returncode == 0, res.stderr
    items = {i["id"]: i for i in json.loads(road.read_text(encoding="utf-8"))["items"]}
    assert items["exchange"]["status"] == "in_progress"  # one merged, one on a branch
    assert items["arabic"]["status"] == "shipped"
    assert items["dwg"]["status"] == "planned"  # nothing started, whatever it said before
    assert items["dxf"]["status"] == "shipped"
    assert items["exchange"]["title"] == "t", "only statuses are written"
    # Unknown plan ids fail loudly instead of guessing.
    bad = json.loads(road.read_text(encoding="utf-8"))
    bad["items"][0]["plan_ids"] = ["ZZ9"]
    road.write_text(json.dumps(bad), encoding="utf-8")
    res = subprocess.run(
        [exe, str(ROOT / "scripts" / "sync-roadmap.mjs"), str(app), str(platform), "--roadmap", str(road)],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert res.returncode != 0 and "ZZ9" in res.stderr


# --- Arabic -----------------------------------------------------------------------


def test_site_pf13_arabic_page(built):
    raw = (OUT / "ar" / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<html[^>]*\blang="ar"[^>]*\bdir="rtl"', raw), "post-build lang/dir"
    doc = Doc(raw)
    assert len(re.findall(r"[؀-ۿ]", doc.visible_text())) > 1500
    assert len(doc.all("h1")) == 1
    assert doc.canonical() == f"{SITE}/ar/"

    def alternates(d: Doc) -> dict[str, str]:
        return {el["attrs"]["hreflang"]: el["attrs"]["href"]
                for el in d.all("link", rel="alternate") if "hreflang" in el["attrs"]}

    want = {"en": f"{SITE}/", "ar": f"{SITE}/ar/", "x-default": f"{SITE}/"}
    assert alternates(doc) == want
    assert alternates(page("index.html")) == want
    assert any(n.get("inLanguage") == "ar" for n in doc.json_ld())
    # The language switch both ways, in the navbar and the footer.
    assert len(page("index.html").all("a", href="/ar/", hreflang="ar")) >= 2
    assert len(doc.all("a", href="/", hreflang="en")) >= 2
    # The English home stays English.
    assert re.search(r'<html[^>]*\blang="en"', (OUT / "index.html").read_text(encoding="utf-8"))
    # The Arabic web font is loaded on /ar/ only.
    def css_of(d: Doc) -> str:
        out = []
        for el in d.all("link", rel="stylesheet"):
            href = el["attrs"]["href"].lstrip("/")
            out.append((OUT / href).read_text(encoding="utf-8"))
        return "".join(out)

    assert "Noto Sans Arabic" in css_of(doc)
    assert "Noto Sans Arabic" not in css_of(page("index.html"))


# --- sitemap, changelog ------------------------------------------------------


def test_site_pf13_sitemap_complete(built):
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9", "x": "http://www.w3.org/1999/xhtml"}
    root = ET.parse(OUT / "sitemap.xml").getroot()
    urls = {u.find("s:loc", ns).text: u for u in root.findall("s:url", ns)}
    for path in ["/", "/pricing/", "/roadmap/", "/ar/", "/changelog/",
                 *[f"/features/{s}/" for s in FEATURE_SLUGS]]:
        assert f"{SITE}{path}" in urls, path
    for path in ("/", "/ar/"):
        links = {l.get("hreflang"): l.get("href") for l in urls[f"{SITE}{path}"].findall("x:link", ns)}
        assert links == {"en": f"{SITE}/", "ar": f"{SITE}/ar/", "x-default": f"{SITE}/"}, path
    assert all(u.endswith("/") for u in urls), "trailing slashes"
    robots = (OUT / "robots.txt").read_text(encoding="utf-8")
    assert "Disallow: /dashboard/" in robots and f"Sitemap: {SITE}/sitemap.xml" in robots


def test_site_pf13_changelog_feed(built):
    atom = "{http://www.w3.org/2005/Atom}"
    root = ET.parse(OUT / "changelog" / "feed.xml").getroot()
    assert root.tag == f"{atom}feed"
    for tag in ("id", "title", "updated", "author"):
        assert root.find(f"{atom}{tag}") is not None, tag
    self_link = [l for l in root.findall(f"{atom}link") if l.get("rel") == "self"]
    assert self_link and self_link[0].get("href") == f"{SITE}/changelog/feed.xml"
    releases = json.loads((CONTENT / "releases.json").read_text(encoding="utf-8"))["releases"]
    versions = {r["manifest"]["version"] for r in releases}
    history = [h for h in json.loads((CONTENT / "history.json").read_text(encoding="utf-8"))
               if h["id"] not in versions]
    entries = root.findall(f"{atom}entry")
    assert len(entries) == len(releases) + len(history)
    ids = [e.find(f"{atom}id").text for e in entries]
    assert len(ids) == len(set(ids))
    for e in entries:
        for tag in ("title", "updated", "id", "content"):
            assert e.find(f"{atom}{tag}") is not None and (e.find(f"{atom}{tag}").text or "").strip(), tag
        href = e.find(f"{atom}link").get("href")
        assert href.startswith(f"{SITE}/changelog/#")
    doc = page("changelog/index.html")
    assert len(doc.all("h1")) == 1
    assert doc.canonical() == f"{SITE}/changelog/"
    assert "BreadcrumbList" in doc.ld_types()
    for r in releases:
        assert doc.all(id=r["manifest"]["version"]), r["manifest"]["version"]
    for h in history:
        assert doc.all(id=h["id"]), h["id"]
    feed_links = [el for el in doc.all("link", rel="alternate")
                  if el["attrs"].get("type") == "application/atom+xml"]
    assert feed_links and feed_links[0]["attrs"]["href"].endswith("/changelog/feed.xml")
    for rel in ("index.html", "pricing/index.html"):
        hrefs = {el["attrs"].get("href") for el in page(rel).all("a")}
        assert "/changelog/" in hrefs and "/roadmap/" in hrefs, rel


# --- analytics, verification, social ------------------------------------------


def test_site_pf13_analytics_public_only(built):
    token = analytics_token()
    for rel in PUBLIC_PAGES:
        html = (OUT / rel).read_text(encoding="utf-8")
        assert (BEACON in html) == bool(token), rel
        if token:
            assert token in html, rel
    for area in ("dashboard", "app", "supplier", "login", "signup", "account"):
        for p in (OUT / area).rglob("*.html") if (OUT / area).exists() else []:
            assert BEACON not in p.read_text(encoding="utf-8"), p
    # No analytics cookie and no other tracker anywhere.
    for p in html_files():
        html = p.read_text(encoding="utf-8")
        for tracker in ("googletagmanager", "google-analytics", "gtag(", "fbq(", "hotjar"):
            assert tracker not in html, (p, tracker)
    privacy = page("privacy/index.html")
    text = privacy.visible_text()
    assert any(privacy.text(h) == "Website analytics" for h in privacy.all("h2"))
    assert "Cloudflare Web Analytics" in text and "cookies" in text


def test_site_pf13_verification_and_social(built):
    doc = page("index.html")
    tokens = verification_tokens()
    assert (doc.meta("google-site-verification") or "") == tokens["google"]
    assert (doc.meta("msvalidate.01") or "") == tokens["bing"]
    urls = social_urls()
    shown = {el["attrs"]["href"] for el in doc.all("a", data_social=True)}
    assert shown == urls
    assert all(el["attrs"]["href"] for el in doc.all("a", data_social=True)), "no empty links"
    org = next(n for n in doc.json_ld() if n.get("@type") == "Organization")
    assert set(org.get("sameAs", [])) == urls
    footer_heads = [doc.text(h) for h in doc.all("h2")]
    assert ("Follow" in footer_heads) == bool(urls)
    # IndexNow: the key file is served from the site root.
    keys = [p for p in (ROOT / "public").glob("*.txt") if re.fullmatch(r"[0-9a-f]{32}", p.stem)]
    assert len(keys) == 1
    key = keys[0].stem
    assert keys[0].read_text(encoding="utf-8").strip() == key
    assert (OUT / f"{key}.txt").read_text(encoding="utf-8").strip() == key


def test_site_pf13_indexnow_dry_run():
    exe = node()
    res = subprocess.run(
        [exe, str(ROOT / "scripts" / "indexnow.mjs"), "--dry-run", "/pricing/", f"{SITE}/features/daylight/"],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert res.returncode == 0, res.stderr
    body = json.loads(res.stdout)
    assert body["host"] == "truebex.com"
    assert re.fullmatch(r"[0-9a-f]{32}", body["key"])
    assert body["keyLocation"] == f"{SITE}/{body['key']}.txt"
    assert body["urlList"] == [f"{SITE}/pricing/", f"{SITE}/features/daylight/"]
    bad = subprocess.run(
        [exe, str(ROOT / "scripts" / "indexnow.mjs"), "--dry-run", "https://example.com/x/"],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert bad.returncode != 0, "only truebex.com URLs"


# --- brand rules, JSON-LD ------------------------------------------------------


def test_site_pf13_no_placeholder_text(built):
    for p in [*html_files(), OUT / "changelog" / "feed.xml"]:
        if p.suffix == ".html":
            text = Doc(p.read_text(encoding="utf-8")).visible_text()
        else:
            text = p.read_text(encoding="utf-8")
        m = PLACEHOLDER_WORDS.search(text)
        assert not m, f"{p.relative_to(OUT)}: {m.group(0) if m else ''}"


def test_site_pf13_no_competitor_names(built):
    pattern = re.compile(r"(?<![\w-])(" + "|".join(re.escape(n) for n in DENY_NAMES) + r")(?![\w])")
    for p in [*html_files(), OUT / "changelog" / "feed.xml", OUT / "sitemap.xml"]:
        if p.suffix == ".html":
            text = Doc(p.read_text(encoding="utf-8")).visible_text()
        else:
            text = p.read_text(encoding="utf-8")
        m = pattern.search(text)
        assert not m, f"{p.relative_to(OUT)} names {m.group(0) if m else ''}"


def test_site_pf13_json_ld_in_step(built):
    cat = catalogue()
    home = page("index.html")
    app = next(n for n in home.json_ld() if n.get("@type") == "SoftwareApplication")
    got = sorted(
        (o["name"], o["price"], o["priceCurrency"]) for o in app["offers"]
    )
    want = sorted(
        [("Free", "0", "GBP")]
        + [
            (f"{t['name']} ({'monthly' if p['interval'] == 'month' else 'annual'})",
             f"{p['amount_minor'] / 100:.2f}", p["currency"])
            for t, p in priced(cat)
        ]
    )
    assert got == want
    pricing_app = next(n for n in page("pricing/index.html").json_ld()
                       if n.get("@type") == "SoftwareApplication")
    assert sorted((o["name"], o["price"], o["priceCurrency"]) for o in pricing_app["offers"]) == want
    for rel in ["index.html", "pricing/index.html", "ar/index.html",
                *[f"features/{s}/index.html" for s in FEATURE_SLUGS]]:
        doc = page(rel)
        assert doc.faq_visible() == doc.faq_ld(), rel
        assert doc.faq_visible(), rel


def test_site_pf13_home_teaser_and_nav(built):
    home = page("index.html")
    cards = home.all("article", data_tier=True)
    assert len(cards) == 3
    assert home.all("a", href="/pricing/"), "Pricing nav link and See all plans"
    assert any(home.text(a) == "See all plans" and a["attrs"]["href"] == "/pricing/" for a in home.all("a"))
    for slug in FEATURE_SLUGS[:4]:
        assert home.all("a", href=f"/features/{slug}/"), slug
