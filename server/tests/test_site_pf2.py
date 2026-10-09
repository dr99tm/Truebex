"""PF2 build checks: read the static export in out/ (the verify gate builds it
before pytest runs). Skipped when out/ is absent."""

import re
from functools import cache
from pathlib import Path

import pytest

OUT = Path(__file__).resolve().parents[2] / "out"

pytestmark = pytest.mark.skipif(
    not (OUT / "index.html").exists(), reason="needs the static build in out/ (npm run build)"
)

PADDLE_JS = "cdn.paddle.com"


@cache
def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _pages() -> list[Path]:
    return sorted(OUT.rglob("*.html"))


def _loads(page: Path, needle: str) -> bool:
    """The page names `needle` itself or through a script chunk it loads."""
    html = _text(page)
    if needle in html:
        return True
    for src in set(re.findall(r"/_next/static/[\w./-]+\.js", html)):
        chunk = OUT / src.lstrip("/")
        if chunk.exists() and needle in _text(chunk):
            return True
    return False


def test_site_pf2_checkout_noindex():
    page = OUT / "checkout" / "index.html"
    assert page.exists()
    html = _text(page)
    assert re.search(r'<meta name="robots" content="noindex, nofollow"', html)
    assert html.count("<h1") == 1
    assert _loads(page, PADDLE_JS)
    others = [p.relative_to(OUT).as_posix() for p in _pages() if p != page and _loads(p, PADDLE_JS)]
    assert others == []


def test_site_pf2_no_wayl_in_public_pages():
    files = _pages() + sorted(OUT.rglob("*.txt"))
    hits = [
        (f.relative_to(OUT).as_posix(), word)
        for f in files
        for word in ("Wayl", "QiCard", "IQD")
        if word in _text(f)
    ]
    assert hits == []


def test_site_pf2_terms_and_privacy_name_the_reseller():
    terms = _text(OUT / "terms" / "index.html")
    assert "Paddle.com" in terms and "Merchant of Record" in terms
    assert "14 days" in terms
    privacy = _text(OUT / "privacy" / "index.html")
    assert "Paddle" in privacy and "postcode" in privacy


def test_site_pf2_billing_page_noindex():
    html = _text(OUT / "dashboard" / "billing" / "index.html")
    assert re.search(r'<meta name="robots" content="noindex, nofollow"', html)
