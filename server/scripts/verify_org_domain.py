"""Mark an organisation's e-mail domain verified by hand (PF3), for a local
test domain such as example.test that no DNS server answers for. Real
domains are verified on the SSO tab with a DNS TXT record.

    cd server
    .venv\Scripts\python.exe scripts\verify_org_domain.py --org studio-north --domain example.test
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402
from app.licence import clock  # noqa: E402
from app.orgs import audit  # noqa: E402
from app.sso import domains  # noqa: E402

from grant_org_seats import find_org  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Mark an organisation's e-mail domain verified by hand.")
    ap.add_argument("--org", required=True, help="organisation slug or id")
    ap.add_argument("--domain", required=True)
    args = ap.parse_args(argv)
    init_db()
    with SessionLocal() as db:
        org = find_org(db, args.org)
        row, _ = domains.add(db, org, None, args.domain, clock.now())
        if row.verified_at is None:
            row.verified_at = clock.now()
            db.add(row)
            audit.record(db, org.id, "domain.verified", target_kind="domain", target_id=row.domain, by="script")
            db.commit()
        print(f"{org.slug}: {row.domain} verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
