"""PF7 build checks: read the static export in out/ after the verify gate's
`npm run build` (skipped when out/ is absent)."""

import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

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
    # (PF12: /developers/market/ is a public docs page; no /market/… page is.)
    assert not re.search(r"<loc>[^<]*\.com/market/", sitemap) and "/dashboard/" not in sitemap


# --- PF7e: an order's web_url (/dashboard/orders/?order=<id>) --------------------------------------

CONSTANTS = ROOT / "src" / "lib" / "constants.ts"


def _order_link_copy() -> dict[str, str]:
    m = re.search(r"export const MARKET_ORDER_LINK = \{(.*?)\n\} as const;", CONSTANTS.read_text(encoding="utf-8"), re.S)
    assert m, "MARKET_ORDER_LINK not found in constants.ts"
    return dict(re.findall(r'(\w+):\s*"([^"]*)"', m.group(1)))


def _render_orders(cases: list[dict], tmp_path: Path) -> list[dict]:
    """server/tests/orders_render.cjs: the orders list as /dashboard/orders/ shows it for a link."""
    import json
    import shutil
    import subprocess

    exe = shutil.which("node")
    if not exe:
        pytest.skip("node not on PATH")
    if not (ROOT / "node_modules" / "typescript").exists():
        pytest.skip("node_modules not installed")
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    res = subprocess.run(
        [exe, str(ROOT / "server" / "tests" / "orders_render.cjs"), str(path)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=180,
    )  # fmt: skip
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def test_site_pf7e_orders_page_shows_the_linked_order(client, monkeypatch, tmp_path):
    """The orders page with ?order=<id> (5.7's web_url) shows that order first
    and highlighted: listed on 5.8's first page, or fetched with 5.9 when it
    is not; an unknown or another account's order, or a malformed id, shows
    MARKET_ORDER_LINK.notFound. Real 5.8 / 5.9 answers, rendered by the page's
    own components in Node (orders_render.cjs)."""
    from .market_helpers import payments_on, with_contract
    from .conftest import signup
    from .test_pf7e_marketplace_1_2 import fixture, load_stub, mk4_request

    payments_on(monkeypatch)
    load_stub(payments_ready=True)
    h = with_contract(signup(client, email="buyer@example.com"))
    want = fixture("order-awaiting-payment.json")
    placed = [
        client.post("/market/orders", json=mk4_request(kind, want), headers=h).json() for kind in ("order", "quote", "order")
    ]
    listed = client.get("/market/orders", headers=h).json()["orders"]
    assert [o["order_id"] for o in listed] == [o["order_id"] for o in reversed(placed)]
    oldest = placed[0]
    web = oldest["web_url"]
    assert web == f"https://truebex.com/dashboard/orders/?order={oldest['order_id']}"
    link = parse_qs(urlsplit(web).query)["order"][0]
    fetched = client.get(f"/market/orders/{link}", headers=h).json()
    stranger = with_contract(signup(client, email="other@example.com"))
    assert client.get(f"/market/orders/{link}", headers=stranger).status_code == 403
    copy = _order_link_copy()
    assert copy["notFound"] and copy["linked"]

    first_page = listed[:2]  # as if the oldest order were past 5.8's first page
    cases = [
        {"orders": listed, "link": None},
        {"orders": listed, "link": link},
        {"orders": first_page, "link": link},
        {"orders": first_page, "link": link, "fetched": fetched},
        {"orders": first_page, "link": link, "fetched": None},  # 404 / 403: not this account's
        {"orders": listed, "link": "../not-an-order"},
        {"orders": listed, "link": link.upper()},
    ]
    plain, listed_link, asking, from_59, missing, malformed, upper = _render_orders(cases, tmp_path)

    def shown(case: dict) -> list[str]:
        return re.findall(r'data-order="([0-9a-f]{32})"', case["html"])

    assert plain["fetch"] is None and plain["focused"] is None and not plain["note"]
    assert shown(plain) == plain["ids"] == [o["order_id"] for o in listed] and "data-focused" not in plain["html"]
    assert (listed_link["fetch"], upper["fetch"], from_59["fetch"]) == (None, None, link)
    for case in (listed_link, from_59, upper):
        assert case["focused"] == link and not case["note"]
        assert shown(case)[0] == link and len(shown(case)) == len(set(shown(case)))
        assert re.search(rf'data-order="{link}"[^>]*data-focused="true"', case["html"]), case["html"][:400]
        assert case["html"].count('data-focused="true"') == 1 and copy["linked"] in case["html"]
        assert copy["notFound"] not in case["html"]
    assert sorted(shown(listed_link)) == sorted(o["order_id"] for o in listed)
    assert shown(from_59) == [link, *[o["order_id"] for o in first_page]]
    # Not on the first page: the page asks 5.9 for it, and shows the list meanwhile.
    assert asking["fetch"] == link and asking["focused"] is None and not asking["note"]
    for case in (missing, malformed):
        assert case["focused"] is None and case["note"] and copy["notFound"] in case["html"]
        assert "data-focused" not in case["html"]
    assert malformed["fetch"] is None and shown(malformed) == [o["order_id"] for o in listed]


@built
def test_site_pf7e_orders_page_built_with_the_link_note():
    """The built /dashboard/orders/ page ships the link's copy (read on the
    client: the static export cannot know the order)."""
    html = _html("dashboard/orders")
    assert NOINDEX.search(html)
    chunks = set(re.findall(r'"(/_next/static/chunks/[^"]+\.js)"', html))
    assert chunks
    text = "".join((OUT / c.lstrip("/")).read_text(encoding="utf-8", errors="replace") for c in chunks if (OUT / c.lstrip("/")).is_file())
    copy = _order_link_copy()
    assert copy["notFound"] in text and copy["linked"] in text
