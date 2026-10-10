"""Send a request for quote or an order for the fixture's sofa, as the app's
basket will (contract marketplace-api 5.7), until MK4 exists.

    cd server
    .venv\\Scripts\\python.exe scripts\\market_try.py --email you@example.com --password ... [--kind quote|order]
        [--region AE] [--api http://127.0.0.1:8000]

Signs in with the account's e-mail and password, sends the sofa (oat-linen,
1) and four tins of paint with the prices the server quotes now, and prints
the answer: the order id, its state and, for an order, the checkout URL to
open in the browser. Run seed_market.py first.
"""

import argparse
import json
import secrets
import sys
from pathlib import Path

import httpx

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "contracts" / "marketplace"
CONTRACT = {"X-Truebex-Contract": "marketplace-api/1.1"}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--kind", choices=("quote", "order"), default="quote")
    ap.add_argument("--region", default="AE", choices=("AE", "GB"))
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    args = ap.parse_args(argv)

    supplier = json.loads((FIXTURES / "products.json").read_text(encoding="utf-8"))["supplier"]["supplier_id"]
    items = [
        {"supplier_id": supplier, "sku": "SOFA-OSLO-3", "variant_id": "oat-linen", "qty": 1},
        {"supplier_id": supplier, "sku": "PAINT-CHALK", "variant_id": "2-5l", "qty": 4},
    ]
    with httpx.Client(base_url=args.api, timeout=30) as api:
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
            "project": {"name": "Trial project", "project_id": None},
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
        if out.get("checkout_url"):
            print(f"checkout: {out['checkout_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
