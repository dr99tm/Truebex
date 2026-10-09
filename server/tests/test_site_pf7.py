"""PF7 build checks: read the static export in out/ after the verify gate's
`npm run build` (skipped when out/ is absent)."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
built = pytest.mark.skipif(not (OUT / "index.html").is_file(), reason="out/ not built (the verify gate builds it first)")
NOINDEX = re.compile(r'<meta name="robots" content="[^"]*noindex')


def _html(page: str) -> str:
    return (OUT / page / "index.html").read_text(encoding="utf-8")


@built
def test_site_pf7_checkout_noindex():
    html = _html("market/checkout")
    assert NOINDEX.search(html)
    assert len(re.findall(r"<h1[\s>]", html)) == 1 and ">Checkout</h1>" in html
    # The order is read on the client (static export): the shell carries no order data.
    assert "awaiting_payment" not in html
    for page in ("dashboard/orders", "dashboard/admin/market"):
        assert NOINDEX.search(_html(page)), page
    sitemap = (OUT / "sitemap.xml").read_text(encoding="utf-8")
    assert "/market/" not in sitemap and "/dashboard/" not in sitemap
