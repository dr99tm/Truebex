"""The website's password reset (2026-11-10): the "Forgot password?" link on
Log in, /forgot-password/ and /reset-password/. The source checks need no
build; the page checks read `out/` and skip without it (the verify gate builds
first).

The reset link's token rides in the URL fragment: the page reads it from
`location.hash` (never a query string), wipes it from the address bar, loads no
analytics beacon, and neither page is indexed or in the sitemap.
"""

import re
from pathlib import Path

import pytest

from .test_site_pf13 import BEACON, OUT, ROOT, Doc, page

SRC = ROOT / "src"


def _src(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


def test_reset_password_source_reads_the_fragment_only():
    form = _src("components/auth/ResetPasswordForm.tsx")
    assert "window.location.hash" in form
    assert "replaceState" in form, "the token is wiped from the address bar and the history"
    for leak in ("useSearchParams", "location.search", "searchParams", "console.", "localStorage", "sessionStorage"):
        assert leak not in form, leak
    page_src = _src("app/reset-password/page.tsx")
    assert "<Footer" not in page_src and "layout/Footer" not in page_src, "no Footer: no analytics beacon"
    assert "index: false" in page_src
    for rel in ("app/forgot-password/page.tsx", "app/reset-password/page.tsx"):
        assert "alternates" not in _src(rel), rel  # no canonical (PF13b)
    # The API mails the same address the page reads.
    reset_py = (ROOT / "server" / "app" / "password_reset.py").read_text(encoding="utf-8")
    assert "/reset-password/#token=" in reset_py


def test_login_links_to_forgot_password_and_sitemap_skips_both():
    auth = _src("components/auth/AuthForm.tsx")
    assert 'href="/forgot-password/"' in auth and "PASSWORD_RESET.forgotLink" in auth
    sitemap = _src("app/sitemap.ts")
    assert "forgot-password" not in sitemap and "reset-password" not in sitemap


@pytest.fixture(scope="module")
def built() -> Path:
    if not (OUT / "index.html").exists():
        pytest.skip("out/ not built (the verify gate builds it before pytest)")
    return OUT


@pytest.mark.parametrize("rel", ["forgot-password/index.html", "reset-password/index.html"])
def test_reset_pages_private(built, rel):
    doc = page(rel)
    robots = [e["attrs"].get("content", "") for e in doc.all("meta") if e["attrs"].get("name") == "robots"]
    assert robots and all("noindex" in c for c in robots), robots
    assert doc.canonical() is None
    assert BEACON not in doc.html
    assert len(doc.all("h1")) == 1
    assert "token" not in "".join(e["attrs"].get("href", "") for e in doc.all("a"))
    sitemap = (OUT / "sitemap.xml").read_text(encoding="utf-8")
    assert f"/{rel.split('/')[0]}/" not in sitemap


def test_reset_page_has_no_referrer(built):
    html = page("reset-password/index.html").html
    assert re.search(r'<meta name="referrer" content="no-referrer"', html)
    assert isinstance(Doc(html), Doc)
