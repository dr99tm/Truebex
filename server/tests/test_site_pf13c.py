"""PF13c: Truebex's own not-found page, and the local static server answering
a missing path with it as GitHub Pages does.

`src/app/not-found.tsx` replaces Next's default not-found page: one title
(`Page not found · Truebex`), robots tags that only say noindex (no
googlebot `index`), no canonical, the site's heading and a way back home.
Next exports it three times: `out/404.html` (what GitHub Pages answers a
missing path with, status 404), `out/404/` and `out/_not-found/`.

`scripts/serve-out.py` answers a missing path with the served folder's
`404.html` and status 404, keeping `Access-Control-Allow-Origin: *`.

The page checks read the static export in `out/` that the verify gate builds
before pytest (`scripts/autopilot-verify.ps1`); they skip when `out/` is
absent. The source and server checks need no build.
"""

import importlib.util
import re
import threading
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from email.message import Message
from pathlib import Path

from .test_site_pf13 import (  # noqa: F401  (built is a fixture)
    CONSTANTS,
    OUT,
    ROOT,
    SITE,
    Doc,
    built,
)
from .test_site_pf13b import canonicals, robots

NOT_FOUND_TSX = ROOT / "src" / "app" / "not-found.tsx"
SERVE_OUT = ROOT / "scripts" / "serve-out.py"
# The three files Next exports for the not-found page (trailingSlash).
NOT_FOUND_FILES = ["404.html", "404/index.html", "_not-found/index.html"]
# Next's default not-found page, which the site's own replaces.
NEXT_DEFAULT = "This page could not be found"
# A robots directive that says index (not noindex).
SAYS_INDEX = re.compile(r"(?<![a-z])index\b")


def not_found_copy() -> dict:
    """`NOT_FOUND` in src/lib/constants.ts: its strings and its links."""
    src = CONSTANTS.read_text(encoding="utf-8")
    m = re.search(r"^export const NOT_FOUND = \{(.*?)^\} as const;", src, re.M | re.S)
    assert m, "NOT_FOUND missing from src/lib/constants.ts"
    body = m.group(1)
    strings = dict(re.findall(r'^  (\w+):\s*"([^"]*)",', body, re.M))
    links = re.findall(r'\{ label: "([^"]+)", href: "([^"]+)" \}', body)
    return {**strings, "links": links}


def tags(doc: Doc) -> list[str]:
    return robots(doc) + robots(doc, "googlebot")


def not_found_pages() -> list[tuple[str, str, Doc]]:
    out = []
    for rel in NOT_FOUND_FILES:
        path = OUT / rel
        assert path.exists(), f"{rel} missing from out/"
        html = path.read_text(encoding="utf-8")
        out.append((rel, html, Doc(html)))
    return out


# --- source ----------------------------------------------------------------------


def test_site_pf13c_not_found_source():
    """The page is a server component with its own metadata: the title
    through the root template and robots noindex; its words come from
    `NOT_FOUND` in constants.ts."""
    src = NOT_FOUND_TSX.read_text(encoding="utf-8")
    assert '"use client"' not in src, "not-found.tsx must stay a server component (metadata)"
    assert "export const metadata" in src
    assert "robots: { index: false }" in src
    assert "NOT_FOUND" in src
    copy = not_found_copy()
    assert "not found" in copy["title"].lower(), copy
    for key in ("eyebrow", "heading", "intro", "home"):
        assert copy.get(key), key
    hrefs = [href for _, href in copy["links"]]
    assert hrefs and all(h.startswith("/") and h.endswith("/") for h in hrefs), hrefs
    assert "/" not in hrefs, "the home link is its own button"


# --- build -----------------------------------------------------------------------


def test_site_pf13c_one_title(built):
    """Exactly one <title>, naming the page as not found, through the root
    template (`… · Truebex`)."""
    for rel, _, doc in not_found_pages():
        titles = [Doc.text(el) for el in doc.all("title")]
        assert len(titles) == 1, (rel, titles)
        assert "not found" in titles[0].lower(), (rel, titles)
        assert titles == [f"{not_found_copy()['title']} · Truebex"], (rel, titles)


def test_site_pf13c_robots_noindex_only(built):
    """Every robots and googlebot tag says noindex; none says index (the
    root layout's `index, follow` and googlebot tags are gone)."""
    for rel, _, doc in not_found_pages():
        found = tags(doc)
        assert found, (rel, "no robots tag")
        assert all("noindex" in c for c in found), (rel, found)
        assert not [c for c in found if SAYS_INDEX.search(c)], (rel, found)


def test_site_pf13c_no_canonical(built):
    for rel, _, doc in not_found_pages():
        assert canonicals(doc) == [], (rel, canonicals(doc))


def test_site_pf13c_heading_and_way_back(built):
    """The site's heading (one h1) and line, a link home and the page's
    other links, all in the served HTML."""
    for rel, _, doc in not_found_pages():
        h1 = [Doc.text(el) for el in doc.all("h1")]
        assert len(h1) == 1 and h1 != ["404"], (rel, h1)  # Next's default h1 is "404"
        copy = not_found_copy()
        assert h1 == [copy["heading"]], (rel, h1)
        main = doc.all("main")
        assert len(main) == 1, (rel, "one <main>")
        assert copy["intro"] in Doc.text(main[0]), rel
        home = [el for el in doc.all("a", href="/") if Doc.text(el) == copy["home"]]
        assert home, (rel, "no link home")
        hrefs = {el["attrs"].get("href") for el in doc.all("a")}
        for label, href in copy["links"]:
            assert href in hrefs, (rel, label, href)


def test_site_pf13c_next_default_gone(built):
    """Next's default '404 | This page could not be found.' is not on the
    page, in its body or in its title."""
    for rel, html, doc in not_found_pages():
        assert NEXT_DEFAULT not in html, rel
        assert not doc.all("h1", class_="next-error-h1"), rel


def test_site_pf13c_not_in_sitemap(built):
    """None of the three files is in the sitemap."""
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.parse(OUT / "sitemap.xml").getroot()
    urls = [u.find("s:loc", ns).text for u in root.findall("s:url", ns)]
    assert len(urls) >= 20
    for url in urls:
        assert "404" not in url and "_not-found" not in url, url
    for rel in NOT_FOUND_FILES:
        own = f"{SITE}/{rel[: -len('index.html')] if rel.endswith('/index.html') else rel}"
        assert own not in urls, own


# --- scripts/serve-out.py --------------------------------------------------------


def serve_out():
    spec = importlib.util.spec_from_file_location("serve_out", SERVE_OUT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def serving(directory: Path):
    module = serve_out()
    server = module.make_server("127.0.0.1", 0, str(directory))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def fetch(url: str, method: str = "GET") -> tuple[int, Message, bytes]:
    """Status, headers (names in any case) and body; follows redirects."""
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.status, res.headers, res.read()
    except urllib.error.HTTPError as err:
        with err:
            return err.code, err.headers, err.read()


def test_site_pf13c_serve_out_answers_404_page(tmp_path):
    """A missing path answers the folder's 404.html with status 404 and
    `Access-Control-Allow-Origin: *`, as GitHub Pages does; a folder
    without 404.html still answers the standard error page."""
    site = tmp_path / "site"
    (site / "pricing").mkdir(parents=True)
    index = b"<!DOCTYPE html><html><body>home</body></html>"
    not_found = "<!DOCTYPE html><html><head><title>Page not found</title></head><body>gone ·</body></html>".encode()
    (site / "index.html").write_bytes(index)
    (site / "pricing" / "index.html").write_bytes(b"<p>pricing</p>")
    (site / "404.html").write_bytes(not_found)
    (site / "app.js").write_text("export {};", encoding="utf-8")

    with serving(site) as base:
        status, headers, body = fetch(f"{base}/")
        assert (status, body) == (200, index)
        assert headers["Access-Control-Allow-Origin"] == "*"
        # Existing behaviour: a folder's index.html, the slash-less redirect, the web types.
        assert fetch(f"{base}/pricing/")[::2] == (200, b"<p>pricing</p>")
        assert fetch(f"{base}/pricing")[::2] == (200, b"<p>pricing</p>")
        status, headers, body = fetch(f"{base}/app.js")
        assert status == 200 and headers["Content-Type"].startswith("text/javascript")

        for path in ("/no-such-page/", "/no-such-page", "/ar/old-link/", "/pricing/gone.html", "/x.js?v=1"):
            status, headers, body = fetch(f"{base}{path}")
            assert status == 404, path
            assert body == not_found, path
            assert headers["Access-Control-Allow-Origin"] == "*", path
            assert headers["Content-Type"].startswith("text/html"), path
            assert headers["Content-Length"] == str(len(not_found)), path

        status, headers, body = fetch(f"{base}/no-such-page/", "HEAD")
        assert (status, body) == (404, b"")
        assert headers["Content-Length"] == str(len(not_found))

    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / "index.html").write_bytes(index)
    with serving(bare) as base:
        status, headers, body = fetch(f"{base}/no-such-page/")
        assert status == 404
        assert body != not_found
        assert b"Error response" in body and b"404" in body, body
        assert headers["Access-Control-Allow-Origin"] == "*"


def test_site_pf13c_serve_out_keeps_backlog():
    """The listen backlog stays 128 (PF5a)."""
    assert serve_out().Server.request_queue_size >= 128
