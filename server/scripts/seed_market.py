"""Load the marketplace fixture into the local database (a trial catalogue).

    cd server
    .venv\\Scripts\\python.exe scripts\\seed_market.py --fixture tests\\contracts\\marketplace
        [--owner you@example.com] [--payments-ready] [--no-feed]

* The fixture's supplier (Nord Living), verified, with its regions GB and AE,
  and the products of products.json, approved, with their prices.
* Then feed-two-regions.csv is imported for that supplier (upsert): the
  sofa's rows come out unchanged and the Bergen lounge chair is new, so it
  waits in the admin review queue (Admin → Market → Products).
* `--owner` makes that account the supplier's owner; `--payments-ready`
  marks the supplier as onboarded to Stripe Connect (orders, not only
  quotes, once MARKET_PAYMENTS_ENABLED=true).

Uses server/.env like the API (DATABASE_URL, STORAGE_DIR, API_URL). Run it
again at any time: it updates the same rows.
"""

import argparse
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))

import app  # noqa: E402, F401  (before SQLAlchemy: keeps platform off WMI on Windows)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--fixture", default=str(SERVER / "tests" / "contracts" / "marketplace"))
    ap.add_argument("--owner", help="e-mail of an existing account to make the supplier's owner")
    ap.add_argument("--payments-ready", action="store_true")
    ap.add_argument("--no-feed", action="store_true", help="skip importing feed-two-regions.csv")
    args = ap.parse_args(argv)

    from sqlalchemy import func, select

    from app.database import SessionLocal, init_db
    from app.market import importer, seed
    from app.market.models import Product
    from app.models import User

    folder = Path(args.fixture).resolve()
    if not (folder / "products.json").is_file():
        print(f"no products.json in {folder}")
        return 2
    init_db()
    with SessionLocal() as db:
        owner = None
        if args.owner:
            owner = db.scalar(select(User).where(func.lower(User.email) == args.owner.lower()))
            if owner is None:
                print(f"no account {args.owner}: sign up on the site first")
                return 2
        supplier = seed.load_fixture(db, folder, payments_ready=args.payments_ready, owner=owner)
        print(f"supplier {supplier.name} ({supplier.supplier_id}): {supplier.status}")
        if not args.no_feed:
            run = importer.run_feed(
                db, supplier, (folder / "feed-two-regions.csv").read_bytes(), "csv", "upsert",
                fetcher=seed.media_fetcher(folder),
            )  # fmt: skip
            print(
                f"feed {run.feed_id}: {run.state}, {run.rows} rows, {run.created} created, "
                f"{run.updated} updated, {run.unchanged} unchanged, {run.rejected} rejected"
            )
        for p in db.scalars(select(Product).where(Product.supplier_id == supplier.supplier_id).order_by(Product.sku)):
            print(f"  {p.status:<15} {p.sku:<22} {p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
