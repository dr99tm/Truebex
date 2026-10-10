"""PF8 build checks: read the static export in out/ after the verify gate's
`npm run build` (skipped when out/ is absent)."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
built = pytest.mark.skipif(not (OUT / "index.html").is_file(), reason="out/ not built (the verify gate builds it first)")
NOINDEX = re.compile(r'<meta name="robots" content="[^"]*noindex')
PAGES = ("", "signup", "join", "catalogue", "catalogue/product", "prices", "imports", "inbox", "analytics", "billing", "team")


@built
def test_site_pf8_supplier_pages_noindex():
    found = sorted(p.relative_to(OUT).as_posix() for p in (OUT / "supplier").rglob("index.html"))
    assert found == sorted(f"supplier/{p}/index.html".replace("//", "/") for p in PAGES)
    for page in found:
        html = (OUT / page).read_text(encoding="utf-8")
        assert NOINDEX.search(html), page
    # The sign-up page's heading and help are in the HTML (one h1), before any script runs.
    signup = (OUT / "supplier" / "signup" / "index.html").read_text(encoding="utf-8")
    assert len(re.findall(r"<h1[\s>]", signup)) == 1 and "Sell your products in Truebex" in signup
    # Never in the sitemap; robots keep crawlers out.
    assert "/supplier/" not in (OUT / "sitemap.xml").read_text(encoding="utf-8")
    assert "Disallow: /supplier/" in (OUT / "robots.txt").read_text(encoding="utf-8")
