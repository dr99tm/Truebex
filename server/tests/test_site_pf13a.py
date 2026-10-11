"""PF13a build checks: the public "Sell on Truebex" page (/suppliers/) that
leads suppliers to the supplier portal's sign-up (/supplier/signup/).

The page checks read the static export in `out/` that the verify gate builds
before pytest (`scripts/autopilot-verify.ps1`); they skip when `out/` is
absent. The constants check needs no build.
"""

import json
import re
import xml.etree.ElementTree as ET

from .test_site_pf13 import (  # noqa: F401  (built is a fixture)
    CONSTANTS,
    DENY_NAMES,
    OUT,
    PLACEHOLDER_WORDS,
    SITE,
    Doc,
    built,
    page,
)

PATH = "/suppliers/"
URL = f"{SITE}{PATH}"
SIGNUP = "/supplier/signup/"
NOINDEX = re.compile(r'<meta name="robots" content="[^"]*noindex')
# What the page may never print: a date, a fee, a price or a share
# (GD7's fees are not set; nothing on the roadmap has a date).
DATES = re.compile(
    r"\b(?:19|20)\d{2}\b|\bQ[1-4]\b|\b(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\b|coming soon|next (?:week|month|year)|this (?:month|year)",
    re.I,
)
FEES = re.compile(r"[£$€]\s?\d|\d\s?%|\bcommission|\bfees?\b|\blisting plan|\bper cent\b", re.I)
# Internal plan and guide ids never reach public copy.
INTERNAL_IDS = re.compile(r"\b(?:GD|PF|MK|CL|LC|DC)\d{1,2}[a-z]?\b")
# The brand-voice skill's words to avoid, and hype.
HYPE = re.compile(
    r"revolutionary|next-gen|seamless|synergy|metaverse|unified ecosystem|single source of truth|"
    r"walkthrough|AI-powered|game.?changer|world.?class|!",
    re.I,
)


def _main(doc: Doc) -> dict:
    mains = doc.all("main")
    assert len(mains) == 1
    return mains[0]


def _section(doc: Doc, name: str) -> Doc:
    """One `<section data-sell="name">` of the page, parsed on its own
    (the page's sections are not nested)."""
    assert len(doc.all("section", data_sell=name)) == 1, name
    start = doc.html.index(f'data-sell="{name}"')
    start = doc.html.rindex("<section", 0, start)
    return Doc(doc.html[start: doc.html.index("</section>", start) + len("</section>")])


def _ld(doc: Doc, kind: str) -> dict:
    nodes = [n for n in doc.json_ld() if n.get("@type") == kind]
    assert len(nodes) == 1, kind
    return nodes[0]


def _page_text(doc: Doc) -> str:
    """The page's own copy: main, the meta description and the JSON-LD."""
    return " ".join([doc.text(_main(doc)), doc.meta("description") or "", json.dumps(doc.json_ld())])


# --- the page -------------------------------------------------------------------


def test_site_pf13a_page_built(built):
    """Metadata, one h1, a canonical with a trailing slash, the text in the
    HTML and the JSON-LD in step with it (truebex-seo per-page checklist)."""
    doc = page("suppliers/index.html")
    h1 = doc.all("h1")
    assert len(h1) == 1
    heading = doc.text(h1[0])
    assert heading.startswith("Sell") and "on Truebex" in heading, heading
    title = doc.title()
    assert len(title) <= 60 and "Sell on Truebex" in title, title
    others = {page(rel).title() for rel in ("index.html", "pricing/index.html", "features/marketplace/index.html")}
    assert title not in others
    desc = doc.meta("description")
    assert desc and 140 <= len(desc) <= 160, (len(desc or ""), desc)
    assert "Sell on Truebex" in desc
    assert doc.canonical() == URL
    assert doc.meta("og:url") == URL and doc.meta("og:image") and doc.meta("og:title")
    assert doc.meta("twitter:card") == "summary_large_image"

    # Server-rendered: every section's copy is in the HTML before any script runs.
    for name, least in (("offer", 5), ("onboarding", 4), ("roadmap", 2)):
        section = _section(doc, name)
        assert len(section.all("h2")) == 1, name
        items = [el for el in section.all("h3") if section.text(el)]
        assert len(items) >= least, (name, len(items))
        assert all(section.text(el) for el in section.all("p")), name
    h2 = [doc.text(el) for el in doc.all("h2")]
    assert {"What you get", "How onboarding works", "On the roadmap", "Questions"} <= set(h2), h2
    assert all(len(t.split()) <= 6 for t in h2 if t), h2

    # JSON-LD: WebPage, BreadcrumbList and FAQPage, matching the visible page.
    web = _ld(doc, "WebPage")
    assert web["url"] == URL and web["@id"] == f"{URL}#webpage"
    assert web["name"] == heading and web["description"] == desc
    crumbs = _ld(doc, "BreadcrumbList")["itemListElement"]
    assert [c["item"] for c in crumbs] == [f"{SITE}/", URL]
    assert [c["position"] for c in crumbs] == [1, 2]
    trail = doc.all("nav", aria_label="Breadcrumb")
    assert trail and crumbs[-1]["name"] in doc.text(trail[0])
    assert doc.faq_visible() and doc.faq_visible() == doc.faq_ld()
    for img in doc.all("img"):
        a = img["attrs"]
        assert a.get("alt") and a.get("width") and a.get("height"), a


def test_site_pf13a_sitemap_and_robots(built):
    """In the sitemap with a trailing slash, crawlable, and not noindex; the
    portal itself stays out of the sitemap and noindex."""
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.parse(OUT / "sitemap.xml").getroot()
    locs = [u.find("s:loc", ns).text for u in root.findall("s:url", ns)]
    assert locs.count(URL) == 1
    assert not [u for u in locs if "/supplier/" in u]
    html = (OUT / "suppliers" / "index.html").read_text(encoding="utf-8")
    assert not NOINDEX.search(html)
    doc = Doc(html)
    robots_meta = doc.meta("robots")
    assert robots_meta is None or "noindex" not in robots_meta
    robots = (OUT / "robots.txt").read_text(encoding="utf-8")
    disallowed = re.findall(r"^Disallow:\s*(\S+)", robots, re.M)
    assert "/supplier/" in disallowed
    assert not [d for d in disallowed if PATH.startswith(d)], disallowed
    signup = (OUT / "supplier" / "signup" / "index.html").read_text(encoding="utf-8")
    assert NOINDEX.search(signup), "the portal stays noindex"


def test_site_pf13a_links_to_supplier_signup(built):
    """One call to action, to the portal's sign-up; no mailto: on the page."""
    doc = page("suppliers/index.html")
    _main(doc)
    main_html = doc.html[doc.html.index("<main"): doc.html.index("</main>") + len("</main>")]
    main = Doc(main_html)
    ctas = main.all("a", data_cta=True)
    assert ctas, "the call to action"
    assert {a["attrs"]["data-cta"] for a in ctas} == {"supplier-signup"}
    assert {a["attrs"]["href"] for a in ctas} == {SIGNUP}
    assert len({main.text(a) for a in ctas}) == 1, "one call to action, one label"
    assert "mailto:" not in main_html
    # Nothing else in the page body asks for an action: no app download,
    # account sign-up or demo button beside the supplier sign-up.
    for other in ('href="/signup/"', 'href="/download/"', 'href="/#contact"', 'data-cta="download"'):
        assert other not in main_html, other
    # The portal's sign-up page exists in the build, so the button lands.
    assert (OUT / "supplier" / "signup" / "index.html").is_file()


def test_site_pf13a_marketplace_button_and_footer(built):
    """The marketplace page's supplier button leads to the new page, and the
    footer links to it from every public English page."""
    market = page("features/marketplace/index.html")
    buttons = market.all("a", data_cta="supplier")
    assert len(buttons) == 2, "the header and the closing call to action"
    for a in buttons:
        assert a["attrs"]["href"] == PATH, a["attrs"]
        assert not a["attrs"]["href"].startswith("mailto:")
        assert market.text(a) == "Sell on Truebex"
    for rel in ("index.html", "pricing/index.html", "features/marketplace/index.html",
                "roadmap/index.html", "suppliers/index.html"):
        doc = page(rel)
        footer = doc.all("footer")
        assert footer, rel
        footer_html = doc.html[doc.html.rindex("<footer"):]
        assert f'href="{PATH}"' in footer_html, rel


def test_site_pf13a_supplier_cta_has_no_mailto():
    """The marketplace feature page's supplierCta in constants.ts names the
    page, never a mailto: (no build needed)."""
    text = CONSTANTS.read_text(encoding="utf-8")
    ctas = re.findall(r"supplierCta:\s*\{(.*?)\}", text, re.S)
    assert ctas, "FEATURE_PAGES has a supplierCta"
    for body in ctas:
        assert "mailto:" not in body, body
        assert f'"{PATH}"' in body, body


def test_site_pf13a_brand_words(built):
    """truebex-brand-voice: no other product named, no placeholders, internal
    ids, hype, dates or fees; roadmap work labelled "On the roadmap" in the
    future tense, card payments among it; shipped work in the present tense."""
    doc = page("suppliers/index.html")
    text = _page_text(doc)
    names = re.compile(r"(?<![\w-])(" + "|".join(re.escape(n) for n in DENY_NAMES) + r")(?![\w])")
    for pattern in (names, PLACEHOLDER_WORDS, INTERNAL_IDS, HYPE, DATES, FEES):
        m = pattern.search(text)
        assert not m, f"{pattern.pattern[:40]}…: {m.group(0) if m else ''}"

    roadmap = _section(doc, "roadmap")
    items = roadmap.all("li", data_roadmap="true")
    assert len(items) >= 2
    for item in items:
        body = roadmap.text(item)
        assert "On the roadmap" in body, body
        assert re.search(r"\bwill\b", body), f"future tense: {body}"
    assert any("payment" in roadmap.text(i).lower() for i in items), "card payments are on the roadmap"
    assert "quote-only" in roadmap.visible_text()

    offer = _section(doc, "offer").visible_text()
    assert not re.search(r"\bwill\b", offer), "what ships is in the present tense"
    assert "On the roadmap" not in offer
    for words in ("catalogue", "region", "spreadsheet", "feed", "request for quote", "order"):
        assert words in offer.lower(), words
    onboarding = _section(doc, "onboarding").visible_text().lower()
    assert "by hand" in onboarding and "every product" in onboarding
    for claim in ("available now", "now available", "live today", "in truebex today", "buy now", "order now"):
        assert claim not in text.lower(), claim
