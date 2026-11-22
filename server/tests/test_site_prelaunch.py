"""Pre-launch build checks (the owner, 2026-11-22): while `PRELAUNCH.hidePricing`
is true in src/lib/constants.ts the public site shows no price and no plan, the
one call to action is to write to us by email or WhatsApp to join the
early-adopter or tester list, and the retired sentence is nowhere.

These read the static export (`out/`), like the other test_site files: build
first, or they skip. They skip too once pricing is public again.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
CONSTANTS = ROOT / "src" / "lib" / "constants.ts"
SITE = "https://truebex.com"

HIDDEN = bool(
    re.search(r"export const PRELAUNCH\b[^=]*=\s*\{\s*hidePricing:\s*true", CONSTANTS.read_text(encoding="utf-8"))
)
pytestmark = [
    pytest.mark.skipif(not HIDDEN, reason="pricing is public: PRELAUNCH.hidePricing is false"),
    pytest.mark.skipif(not (OUT / "index.html").exists(), reason="no build: run npm run build first"),
]

# Any amount of money, in the three currencies the catalogue has and in words.
MONEY = re.compile(r"(?:[£€]|US\$|\$)\s?\d|\d[\d,.]*\s?(?:USD|GBP|EUR|dollars|pounds|euros)\b")
RETIRED = re.compile(r"see it before (?:you build|it(?:'s| is) built)", re.I)
# Words that only belong to the plans and their prices.
PLAN_WORDS = ("Price at launch", "Founding seats", "founding price", "See all plans", "per seat", "billed annually")


class Page(HTMLParser):
    """Visible text, links, meta tags and JSON-LD of one built page."""

    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.links: list[dict[str, str]] = []
        self.meta: list[dict[str, str]] = []
        self.rel: list[dict[str, str]] = []
        self.ld: list[str] = []
        self._skip = 0
        self._ld = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        a = {k: v or "" for k, v in attrs}
        if tag in ("script", "style", "noscript", "template"):
            self._skip += 1
            self._ld = tag == "script" and a.get("type") == "application/ld+json"
            if self._ld:
                self.ld.append("")
        elif tag == "a":
            self.links.append(a)
        elif tag == "meta":
            self.meta.append(a)
        elif tag == "link":
            self.rel.append(a)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "template"):
            self._skip = max(0, self._skip - 1)
            self._ld = False

    def handle_data(self, data):
        if self._ld:
            self.ld[-1] += data
        elif not self._skip:
            self.text.append(data)

    @property
    def visible(self) -> str:
        return " ".join(" ".join(self.text).split())

    def hrefs(self) -> set[str]:
        return {a.get("href", "") for a in self.links}

    def nodes(self) -> list[dict]:
        out: list[dict] = []
        for raw in self.ld:
            data = json.loads(raw)
            out.extend(data.get("@graph", [data]) if isinstance(data, dict) else data)
        return out


def page(rel: str) -> Page:
    return Page((OUT / rel).read_text(encoding="utf-8"))


def public_pages() -> list[str]:
    """Every indexable page of the build: the sitemap's own list."""
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.parse(OUT / "sitemap.xml").getroot()
    rels = []
    for loc in root.findall("s:url/s:loc", ns):
        path = loc.text.removeprefix(SITE).strip("/")
        rels.append(f"{path}/index.html" if path else "index.html")
    return rels


def walk(node, found: list) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("offers", "price", "priceCurrency", "priceSpecification"):
                found.append(key)
            walk(value, found)
    elif isinstance(node, list):
        for item in node:
            walk(item, found)


def test_prelaunch_sitemap_has_no_pricing():
    rels = public_pages()
    assert "index.html" in rels and "ar/index.html" in rels and "download/index.html" in rels
    assert not [rel for rel in rels if "pricing" in rel or "checkout" in rel]


def test_prelaunch_no_price_on_any_public_page():
    for rel in [*public_pages(), "pricing/index.html", "404.html"]:
        if rel.startswith("developers/"):
            continue  # the API docs show request examples with $ in code, never a plan price (test_site_pf13)
        doc = page(rel)
        text = doc.visible
        assert not MONEY.search(text), (rel, MONEY.search(text).group(0))
        if rel.startswith(("terms/", "privacy/")):
            continue  # the legal terms of a subscription stay written (no amount in them, checked above)
        for words in PLAN_WORDS:
            assert words not in text, (rel, words)


def test_prelaunch_no_offer_in_structured_data():
    for rel in [*public_pages(), "pricing/index.html"]:
        found: list[str] = []
        walk(page(rel).nodes(), found)
        assert not found, (rel, found)
    app = [n for n in page("index.html").nodes() if n.get("@type") == "SoftwareApplication"]
    assert len(app) == 1 and app[0]["name"] == "Truebex", "the product is still described, without offers"


def test_prelaunch_no_link_to_pricing_or_checkout():
    for rel in [*public_pages(), "404.html"]:
        hrefs = page(rel).hrefs()
        bad = sorted(h for h in hrefs if "/pricing" in h or "#pricing" in h or h.startswith("/checkout") or "/dashboard/billing" in h)
        assert not bad, (rel, bad)


def test_prelaunch_pricing_address_is_a_noindex_note():
    doc = page("pricing/index.html")
    robots = [m.get("content", "") for m in doc.meta if m.get("name") == "robots"]
    assert robots and all("noindex" in r for r in robots), robots
    assert not [l for l in doc.rel if l.get("rel") == "canonical"], "a private page has no canonical"
    assert "Plans are published at launch" in doc.visible
    assert any(h.startswith("mailto:contact@truebex.com") for h in doc.hrefs())


def test_prelaunch_call_to_action_is_contact_only():
    """Home and /ar/: the contact section has the email button (and WhatsApp once
    the site has a number), the note on what is kept, and no form."""
    src = CONSTANTS.read_text(encoding="utf-8")
    number = re.search(r'^  whatsapp: "(\d*)",', src, re.M)
    assert number is not None, "SITE.whatsapp: digits only, or empty"
    for rel in ("index.html", "ar/index.html"):
        html = (OUT / rel).read_text(encoding="utf-8")
        section = html[html.index('id="contact"'):]
        section = section[: section.index("</section>")]
        assert 'data-contact-channel="email"' in section, rel
        assert ('data-contact-channel="whatsapp"' in section) is bool(number.group(1)), rel
        if number.group(1):
            assert f"https://wa.me/{number.group(1)}?text=" in section, rel
        assert "<form" not in section and "<input" not in section, (rel, "no form before launch")
        assert 'href="/privacy/"' in section, rel
    home = page("index.html").visible
    assert "early adopters" in home and "Request a Demo" not in home and "Request Demo" not in home


def test_prelaunch_retired_sentence_is_gone():
    for path in OUT.rglob("*.html"):
        assert not RETIRED.search(path.read_text(encoding="utf-8")), path.relative_to(OUT)
    for rel in ("src/lib/constants.ts", "docs/brand/messaging-brief.md", "docs/roadmap/40/PF13c-not-found-page.md"):
        assert not RETIRED.search((ROOT / rel).read_text(encoding="utf-8")), rel
    # The brand voice skill names it once, to forbid it.
    skill = (ROOT / ".claude/skills/truebex-brand-voice/SKILL.md").read_text(encoding="utf-8")
    assert len(RETIRED.findall(skill)) == 1 and "Retired (owner, 2026-11-22)" in skill
