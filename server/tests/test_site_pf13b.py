"""PF13b build checks: only the home page names https://truebex.com/ as its
canonical. A page has a canonical only when it names its own URL; a private
(noindex) page never points search engines at another one.

The root layout (`src/app/layout.tsx`) no longer gives every page
`alternates: { canonical: "/" }`: a public page names its own (`pageMetadata`
in `src/lib/seo.ts`, or explicitly), a private page names none.

The page checks read the static export in `out/` that the verify gate builds
before pytest (`scripts/autopilot-verify.ps1`); they skip when `out/` is
absent. The source checks need no build.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .test_site_pf13 import (  # noqa: F401  (built is a fixture)
    OUT,
    ROOT,
    SITE,
    Doc,
    built,
    html_files,
    page,
)

LAYOUT = ROOT / "src" / "app" / "layout.tsx"
ACCOUNT = ROOT / "src" / "app" / "account"
HOME = f"{SITE}/"
HOME_LANGUAGES = {"en": f"{SITE}/", "ar": f"{SITE}/ar/", "x-default": f"{SITE}/"}


def own_url(path: Path) -> str:
    """The URL a file in out/ is served at: index.html maps to its folder
    (trailingSlash), the home page to https://truebex.com/."""
    rel = path.relative_to(OUT).as_posix()
    if rel == "index.html":
        return HOME
    if rel.endswith("/index.html"):
        return f"{SITE}/{rel[: -len('index.html')]}"
    return f"{SITE}/{rel}"


def file_of(url: str) -> Path:
    """The file in out/ a sitemap URL is served from."""
    assert url.startswith(HOME) and url.endswith("/"), url
    return OUT / url[len(HOME):] / "index.html"


def canonicals(doc: Doc) -> list[str]:
    return [el["attrs"].get("href", "") for el in doc.all("link", rel="canonical")]


def hreflangs(doc: Doc) -> dict[str, str]:
    return {el["attrs"]["hreflang"]: el["attrs"]["href"]
            for el in doc.all("link", rel="alternate") if "hreflang" in el["attrs"]}


def robots(doc: Doc, name: str = "robots") -> list[str]:
    """Every robots meta of a page (Next adds its own `noindex` to the 404
    page, beside the layout's)."""
    return [el["attrs"].get("content", "") for el in doc.all("meta", name=name)]


def noindex(doc: Doc) -> bool:
    return any("noindex" in c for c in robots(doc))


def pages() -> list[tuple[Path, Doc]]:
    return [(p, Doc(p.read_text(encoding="utf-8"))) for p in sorted(html_files())]


# --- source ----------------------------------------------------------------------


def test_site_pf13b_root_layout_names_no_canonical():
    """The root layout's metadata carries no `alternates`: a canonical is
    each page's own, never inherited."""
    src = LAYOUT.read_text(encoding="utf-8")
    assert not re.search(r"\balternates\s*:", src), "src/app/layout.tsx sets alternates"
    assert not re.search(r"\bcanonical\s*:", src), "src/app/layout.tsx sets a canonical"


def test_site_pf13b_account_layout_noindex_source():
    """/account/ is a client redirect (no metadata of its own), so its
    layout makes it noindex; the page still sends visitors to /dashboard/."""
    layout = (ACCOUNT / "layout.tsx").read_text(encoding="utf-8")
    assert "robots: { index: false, follow: true }" in layout
    assert 'router.replace("/dashboard/")' in (ACCOUNT / "page.tsx").read_text(encoding="utf-8")


# --- build -----------------------------------------------------------------------


def test_site_pf13b_canonical_is_own_url(built):
    """A canonical, when present, is one link naming the page's own URL
    with the trailing slash."""
    wrong = {}
    for path, doc in pages():
        links = canonicals(doc)
        if links and links != [own_url(path)]:
            wrong[path.relative_to(OUT).as_posix()] = links
    assert not wrong, f"canonical not the page's own URL: {wrong}"


def test_site_pf13b_noindex_names_no_other_url(built):
    """A private page names no other URL: no canonical elsewhere, no
    hreflang alternates."""
    private = 0
    wrong = {}
    for path, doc in pages():
        if not noindex(doc):
            continue
        private += 1
        others = [u for u in canonicals(doc) if u != own_url(path)] + list(hreflangs(doc).values())
        if others:
            wrong[path.relative_to(OUT).as_posix()] = others
    assert private >= 40, f"only {private} noindex pages found in out/"
    assert not wrong, f"noindex pages naming another URL: {wrong}"


def test_site_pf13b_sitemap_urls_self_canonical(built):
    """Every URL in the sitemap has exactly one canonical, its own, and is
    indexable."""
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.parse(OUT / "sitemap.xml").getroot()
    urls = [u.find("s:loc", ns).text for u in root.findall("s:url", ns)]
    assert len(urls) >= 20
    for url in urls:
        path = file_of(url)
        assert path.exists(), f"{url}: {path} missing"
        doc = Doc(path.read_text(encoding="utf-8"))
        assert canonicals(doc) == [url], (url, canonicals(doc))
        assert not noindex(doc), url


def test_site_pf13b_account_noindex(built):
    """/account/ answers noindex (it redirects to /dashboard/), names no
    canonical, and still links to the dashboard."""
    doc = page("account/index.html")
    tags = robots(doc) + robots(doc, "googlebot")
    assert tags and all("noindex" in c for c in tags), tags
    assert canonicals(doc) == []
    assert doc.all("a", href="/dashboard/"), "the dashboard link"


def test_site_pf13b_only_home_names_root(built):
    """Only out/index.html names https://truebex.com/ as its canonical: the
    raw tag, as the human test greps for it, and the parsed link."""
    raw = '<link rel="canonical" href="https://truebex.com/"'
    named = sorted(p.relative_to(OUT).as_posix() for p in html_files()
                   if raw in p.read_text(encoding="utf-8"))
    assert named == ["index.html"], named
    parsed = sorted(p.relative_to(OUT).as_posix() for p, d in pages() if HOME in canonicals(d))
    assert parsed == ["index.html"], parsed


def test_site_pf13b_home_and_arabic_unchanged(built):
    """The home page keeps its canonical and its en/ar/x-default alternates;
    /ar/ keeps its own."""
    home = page("index.html")
    assert canonicals(home) == [HOME]
    assert hreflangs(home) == HOME_LANGUAGES
    assert not noindex(home)
    ar = page("ar/index.html")
    assert canonicals(ar) == [f"{SITE}/ar/"]
    assert hreflangs(ar) == HOME_LANGUAGES


def test_site_pf13b_private_pages_have_no_canonical(built):
    """The pages that inherited the root's canonical before PF13b name none
    now: every dashboard and supplier page, the checkouts, the SSO return,
    the invite, /account/ and the 404 pages."""
    folders = ["dashboard", "supplier", "market/checkout", "checkout", "login/sso", "invite/index.html",
               "account", "404", "_not-found", "404.html"]
    seen = 0
    for name in folders:
        target = OUT / name
        files = [target] if target.is_file() else sorted(target.rglob("index.html"))
        assert files, f"{name} missing from out/"
        for path in files:
            seen += 1
            doc = Doc(path.read_text(encoding="utf-8"))
            assert canonicals(doc) == [], (path.relative_to(OUT).as_posix(), canonicals(doc))
            assert noindex(doc), path.relative_to(OUT).as_posix()
    assert seen >= 38, seen
