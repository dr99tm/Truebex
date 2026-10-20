"""Send a request for quote or an order for the fixture's sofa, as the app's
basket will (contract marketplace-api 5.7), until MK4 exists.

    cd server
    .venv\\Scripts\\python.exe scripts\\market_try.py --email you@example.com --password ... [--kind quote|order]
        [--region AE] [--api http://127.0.0.1:8000] [--search "Oslo sofa"] [--basket mk4] [--json]

Signs in with the account's e-mail and password, sends the sofa (oat-linen,
1) and four tins of paint with the prices the server quotes now, and prints
the answer: the order id, its state and, for an order, the checkout URL to
open in the browser. Run seed_market.py first, or (PF8) pass --search to send
the first product a catalogue search finds in the region, from whichever
supplier sells it (e.g. one that uploaded feed-two-regions.csv in the portal).

PF7e: `--basket mk4` sends the app's MK4 basket instead (the app's catalogue,
seed_market.py --fixture tests\\contracts\\marketplace: two Oslo sofas, Oat,
and the Fjord coffee table from Nord Living, the Arc wall light from Atelier
Lumen, region AE, the project as order-awaiting-payment.json names it), and
`--json` prints the whole 5.7 answer (contract 1.2.0: `web_url`, each
supplier's `name`, `days_min` / `days_max` and `items`).
"""

import argparse
import json
import secrets
import sys
from pathlib import Path

import httpx

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "market"  # PF7's catalogue (seed_market.py's default)
APP_FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "contracts" / "marketplace"  # the app's (PF7c)
CONTRACT = {"X-Truebex-Contract": "marketplace-api/1.2"}


def mk4_basket() -> tuple[list[dict], dict]:
    """MK4's human-test basket, as order-awaiting-payment.json lists it, and its project."""
    want = json.loads((APP_FIXTURES / "order-awaiting-payment.json").read_text(encoding="utf-8"))
    items = [
        {"supplier_id": s["supplier_id"], "sku": i["sku"], "variant_id": i["variant_id"], "qty": i["qty"]}
        for s in want["suppliers"]
        for i in s["items"]
    ]
    return items, want["project"]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--kind", choices=("quote", "order"), default="quote")
    ap.add_argument("--region", default="AE", choices=("AE", "GB"))
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--search", help="send the first product this text finds in the region instead (PF8)")
    ap.add_argument("--basket", choices=("mk4",), help="send the app's MK4 basket (AE) instead (PF7e)")
    ap.add_argument("--json", action="store_true", help="print the whole answer")
    args = ap.parse_args(argv)

    supplier = json.loads((FIXTURES / "products.json").read_text(encoding="utf-8"))["supplier"]["supplier_id"]
    items = [
        {"supplier_id": supplier, "sku": "SOFA-OSLO-3", "variant_id": "oat-linen", "qty": 1},
        {"supplier_id": supplier, "sku": "PAINT-CHALK", "variant_id": "2-5l", "qty": 4},
    ]
    project = {"name": "Trial project", "project_id": None}
    if args.basket == "mk4":
        if args.region != "AE":
            print("the MK4 basket is priced in AE: leave --region out or pass AE")
            return 2
        items, project = mk4_basket()
    with httpx.Client(base_url=args.api, timeout=30) as api:
        if args.search:
            found = api.get("/market/search", params={"q": args.search, "region": args.region}, headers=CONTRACT).json()
            if not found.get("results"):
                print(f"nothing found for {args.search!r} in {args.region}")
                return 1
            first = found["results"][0]
            product = api.get(f"/market/products/{first['product_id']}", params={"region": args.region}, headers=CONTRACT).json()
            variant = first.get("variant_id") or product["variants"][0]["variant_id"]
            items = [{"supplier_id": product["supplier_id"], "sku": product["sku"], "variant_id": variant, "qty": 1}]
            print(f"{product['name']} ({product['sku']} / {variant}) from {product['supplier_name']}")
        res = api.post("/auth/login", json={"email": args.email, "password": args.password})
        if res.status_code != 200:
            print(f"sign-in failed: {res.status_code} {res.text}")
            return 1
        auth = {"Authorization": f"Bearer {res.json()['access_token']}", **CONTRACT}
        # The prices the person sees in the app (5.5), sent back as price_seen.
        prices = api.post("/market/prices", json={"region": args.region, "items": items}, headers=CONTRACT).json()["items"]
        lines = [{**item, "price_seen": p["price"]} for item, p in zip(items, prices)]
        body = {
            "kind": args.kind,
            "region": args.region,
            "project": project,
            "contact": {"name": "Trial buyer", "email": args.email, "phone": None, "message": "Sent by market_try.py"},
            "delivery": {"country": args.region, "city": "Dubai" if args.region == "AE" else "London", "postcode": None},
            "lines": lines,
        }
        res = api.post("/market/orders", json=body, headers={**auth, "Idempotency-Key": secrets.token_hex(16)})
        out = res.json()
        if res.status_code != 201:
            print(f"{res.status_code} {out.get('code')}: {out.get('detail')}")
            if out.get("data"):
                print(json.dumps(out["data"], indent=2))
            return 1
        total = out["total"]
        print(f"{out['kind']} {out['order_id']}: {out['state']}, total {total['currency']} {total['amount'] / 10 ** total['exponent']:,.{total['exponent']}f}")
        for s in out.get("suppliers", []):
            print(f"  {s.get('name')}: {s['state']}, {s['lines']} lines, delivery in {s.get('days_min')}-{s.get('days_max')} days")
        if out.get("checkout_url"):
            print(f"checkout: {out['checkout_url']}")
        if out.get("web_url"):
            print(f"web: {out['web_url']}")
        if args.json:
            print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
