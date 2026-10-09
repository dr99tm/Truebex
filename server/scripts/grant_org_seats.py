r"""Give an organisation a tier and seats by hand (PF3), as `enterprise` is
set by hand today: for Enterprise contracts arranged off-line and for local
tests before PF2's checkout sells seats.

    cd server
    .venv\Scripts\python.exe scripts\grant_org_seats.py --org studio-north --tier team --seats 2
    .venv\Scripts\python.exe scripts\grant_org_seats.py --org studio-north --tier enterprise --seats 50 --until 2027-10-31
    .venv\Scripts\python.exe scripts\grant_org_seats.py --org studio-north --revoke

Writes one `subscriptions` row with provider "manual" and organisation_id
set (updated in place when it exists), never a personal plan. A date given
with --until is a fixed term: entitlements end no later than it.
"""

import argparse
import sys
from datetime import datetime, time, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.licence import clock  # noqa: E402
from app.models import Subscription  # noqa: E402
from app.orgs import audit  # noqa: E402
from app.orgs.models import OrgMember, Organisation  # noqa: E402
from app.orgs.seats import MANUAL_PROVIDER  # noqa: E402
from app.plans import PLANS  # noqa: E402


def find_org(db: Session, ref: str) -> Organisation:
    org = db.get(Organisation, ref) or db.scalar(select(Organisation).where(Organisation.slug == ref))
    if org is None or org.deleted_at is not None:
        raise SystemExit(f"no organisation with id or slug {ref!r}")
    return org


def grant(db: Session, ref: str, *, tier: str | None, seats: int | None, until: datetime | None = None,
          revoke: bool = False) -> Subscription | None:
    org = find_org(db, ref)
    sub = db.scalar(
        select(Subscription).where(Subscription.organisation_id == org.id, Subscription.provider == MANUAL_PROVIDER)
    )
    now = clock.now()
    if revoke:
        if sub is not None:
            sub.status = "canceled"
            db.add(sub)
            audit.record(db, org.id, "subscription.revoked", target_kind="org", target_id=org.id, at=now, by="script")
            db.commit()
        return sub
    if tier not in PLANS or tier == "free":
        raise SystemExit(f"--tier must be one of {', '.join(t for t in PLANS if t != 'free')}")
    if not seats or seats < 1:
        raise SystemExit("--seats must be 1 or more")
    owner = org.created_by or db.scalar(
        select(OrgMember.user_id).where(OrgMember.org_id == org.id, OrgMember.role == "owner")
    )
    if sub is None:
        sub = Subscription(user_id=owner, organisation_id=org.id, provider=MANUAL_PROVIDER, plan=tier, status="active")
    sub.plan, sub.seats, sub.status, sub.current_period_end = tier, seats, "active", until
    db.add(sub)
    audit.record(db, org.id, "subscription.granted", target_kind="org", target_id=org.id, at=now, by="script",
                 plan=tier, seats=seats, until=clock.rfc3339(until))
    db.commit()
    return sub


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--org", required=True, help="organisation slug or id")
    ap.add_argument("--tier", help="team, studio, pro or enterprise")
    ap.add_argument("--seats", type=int)
    ap.add_argument("--until", help="YYYY-MM-DD: a fixed term ending that day (UTC)")
    ap.add_argument("--revoke", action="store_true", help="cancel the hand-made subscription")
    args = ap.parse_args(argv)
    until = None
    if args.until:
        until = datetime.combine(datetime.strptime(args.until, "%Y-%m-%d").date(), time(23, 59, 59), tzinfo=timezone.utc)
    init_db()
    with SessionLocal() as db:
        sub = grant(db, args.org, tier=args.tier, seats=args.seats, until=until, revoke=args.revoke)
        org = find_org(db, args.org)
        if args.revoke:
            print(f"{org.slug}: hand-made subscription cancelled" if sub else f"{org.slug}: nothing to cancel")
        else:
            print(f"{org.slug}: {sub.plan} x {sub.seats} seats" + (f" until {args.until}" if until else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
