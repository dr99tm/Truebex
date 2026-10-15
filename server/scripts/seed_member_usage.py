r"""Give an account cloud storage, panoramas and AI credits this month, for
trying the organisation console's Member usage tab (PF3b) on a local API
before the desktop app uploads, renders and asks the assistant for real.

    cd server
    .venv\Scripts\python.exe scripts\seed_member_usage.py --email member@example.com
    .venv\Scripts\python.exe scripts\seed_member_usage.py --email member@example.com --bytes 1610612736 --panoramas 3 --credits 12500

Writes through each feature's own models, now (UTC): a project of --bytes
(PF4, `projects` + its owner row; no snapshot, so nothing recounts it),
--panoramas `panorama` render jobs that succeeded (PF6, with their cost
units metered) and two assistant turns spending --credits (PF11's balance
and ledger; a top-up covers what the balance lacks, so it never goes below
zero). Each run adds to what is there. Prints what the tab shows for the
account this month.
"""

import argparse
import secrets
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app  # noqa: E402, F401  (before SQLAlchemy: keeps platform off WMI on Windows)
from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import metering  # noqa: E402
from app.ai import credits as ai_credits  # noqa: E402
from app.ai.models import AiUsage  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.licence import clock  # noqa: E402
from app.licence.ids import uuid7_hex  # noqa: E402
from app.models import User  # noqa: E402
from app.orgs import usage  # noqa: E402
from app.projects import quotas  # noqa: E402
from app.projects.models import Project, ProjectMember  # noqa: E402
from app.render import quotas as render_quotas  # noqa: E402
from app.render.models import RenderJob  # noqa: E402

VIEW = "aee49319c0d48a7a953f247b52c948be"  # the app's render-jobs fixtures' "living" (PR3)
JOB_CU = Decimal("0.2")


def seed(db: Session, email: str, *, nbytes: int = 256 * 1024 * 1024, panoramas: int = 2, credits: int = 1250) -> dict:
    user = db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    if user is None:
        raise SystemExit(f"no account with the address {email}")
    now = clock.now()

    # Cloud storage (PF4): one project the account owns.
    project = Project(
        project_id=uuid7_hex(), name="Seeded usage", owner_user_id=user.id, doc_version=1, head_seq=0, bytes=nbytes,
        server_replica_id=secrets.token_hex(16), created_at=now, updated_at=now,
    )
    db.add(project)
    db.flush()
    db.add(
        ProjectMember(
            project_id=project.project_id, user_id=user.id, email=user.email, role="owner", state="active",
            invited_at=now, accepted_at=now,
        )
    )

    # Panoramas (PF6): succeeded jobs of one view, metered as a completion is.
    started = now - timedelta(minutes=1)
    for _ in range(panoramas):
        db.add(
            RenderJob(
                job_id=secrets.token_hex(16), account_kind=render_quotas.ACCOUNT_KIND, account_id=user.id,
                kind="panorama", worker_class="gpu-std", state="succeeded", project_id=project.project_id,
                views=[VIEW], progress=1.0, created_at=started, queued_at=started, claimed_at=started,
                started_at=started, finished_at=now, updated_at=now,
                cost_units_estimate=JOB_CU, cost_units=JOB_CU, wall_s=45.0, used_class="gpu-std",
            )
        )
        metering.record(db, render_quotas.ACCOUNT_KIND, user.id, render_quotas.METRIC, JOB_CU, metering.utc_day(now))
        metering.record(db, render_quotas.ACCOUNT_KIND, user.id, f"{render_quotas.METRIC}.panorama", JOB_CU, metering.utc_day(now))

    # AI credits (PF11): two turns, as the proxy charges them.
    if credits > 0:
        row = ai_credits.ensure(db, user, now)
        short = credits - ai_credits.remaining(row)
        if short > 0:
            ai_credits.adjust(db, user, short, f"seed-member-usage:{secrets.token_hex(6)}", bucket="top_up", now=now)
        first = credits * 4 // 5
        for charged in (first, credits - first):
            if charged <= 0:
                continue
            turn_id = secrets.token_hex(16)
            ai_credits.spend(db, row, charged, turn_id, now)
            db.add(
                AiUsage(
                    turn_id=turn_id, at=now, account_kind=ai_credits.ACCOUNT_KIND, account_id=user.id,
                    alias="truebex-assist", provider_model="seeded", served_by="anthropic", stream=True,
                    stop_reason="end_turn", credits=charged, tool_names=[], outcome="ok",
                )
            )
    db.commit()

    m_start, m_end = usage.window(now.date().replace(day=1))
    return {
        "storage_bytes": quotas.bytes_used(db, user.id),
        "panoramas": usage.panoramas(db, [user.id], m_start, m_end).get(user.id, 0),
        "ai_credits": usage.ai_credits(db, [user.id], m_start, m_end).get(user.id, 0),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--email", required=True, help="the member's sign-in address")
    ap.add_argument("--bytes", type=int, default=256 * 1024 * 1024, help="project size in bytes (default 256 MiB)")
    ap.add_argument("--panoramas", type=int, default=2, help="succeeded panorama jobs (default 2)")
    ap.add_argument("--credits", type=int, default=1250, help="AI credits spent over two turns (default 1250)")
    args = ap.parse_args(argv)
    if args.bytes < 0 or args.panoramas < 0 or args.credits < 0:
        raise SystemExit("--bytes, --panoramas and --credits must be 0 or more")
    init_db()
    with SessionLocal() as db:
        shown = seed(db, args.email, nbytes=args.bytes, panoramas=args.panoramas, credits=args.credits)
    print(
        f"{args.email} this month: storage {shown['storage_bytes']} bytes, "
        f"{shown['panoramas']} panoramas, {shown['ai_credits']} AI credits"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
