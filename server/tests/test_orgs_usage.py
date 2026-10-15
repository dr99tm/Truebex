"""Member usage: cloud storage, panoramas and AI credits (PF3b). The three
columns of `/orgs/{id}/usage` read PF4's project bytes, PF6's render jobs and
PF11's credit ledger, each member's own account, for the month asked."""

import re
import secrets
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import event

from app.ai.models import AiBalance, AiCreditLedger, AiUsage
from app.database import SessionLocal, engine
from app.licence.ids import uuid7_hex
from app.projects import quotas
from app.projects.models import Project
from app.render.models import RenderJob

from .conftest import signup
from .licence_helpers import Clock
from .org_helpers import (  # noqa: F401  (_clean_mail_and_caches is an autouse fixture)
    _clean_mail_and_caches,
    envelope,
    join,
    load_script,
    make_org,
    me,
)

UTC = timezone.utc


def _mid_month(monkeypatch) -> Clock:
    """The API's clock at noon on the 15th of this month, so 'this month' and
    'last month' never straddle a real month end while the test runs."""
    at = datetime.now(UTC).replace(day=15, hour=12, minute=0, second=0, microsecond=0)
    return Clock(monkeypatch, at)


def _month_start(at: datetime) -> datetime:
    return datetime.combine(at.date().replace(day=1), time.min, tzinfo=UTC)


def _project(db, owner_id: int, nbytes: int, *, deleted_at: datetime | None = None) -> None:
    db.add(
        Project(
            project_id=uuid7_hex(), name="House", owner_user_id=owner_id, doc_version=1, bytes=nbytes,
            server_replica_id=secrets.token_hex(16), deleted_at=deleted_at,
        )
    )


def _job(db, account_id: int, kind: str, state: str, finished_at: datetime | None, *,
         account_kind: str = "user", created_at: datetime | None = None, follow: bool = False) -> None:
    created = created_at or finished_at or datetime.now(UTC)
    db.add(
        RenderJob(
            job_id=secrets.token_hex(16), account_kind=account_kind, account_id=account_id, kind=kind,
            worker_class="gpu-std", state=state, follow=follow, created_at=created, queued_at=created,
            updated_at=finished_at or created, finished_at=finished_at,
        )
    )


def _ledger(db, account_id: int, kind: str, delta: int, at: datetime, *, bucket: str = "allowance",
            account_kind: str = "user") -> None:
    db.add(
        AiCreditLedger(
            account_kind=account_kind, account_id=account_id, delta=delta, kind=kind, bucket=bucket,
            ref=secrets.token_hex(8), balance_after=0, at=at,
        )
    )


def _org_with_usage(client, monkeypatch):
    """An owner, member m (usage this month and last) and member n (none)."""
    clk = _mid_month(monkeypatch)
    now = clk.at
    this_month = _month_start(now)
    last_month_end = this_month - timedelta(microseconds=1)
    last_month = _month_start(last_month_end)

    h = signup(client, "owner@example.com")
    org = make_org(client, h)
    m = join(client, h, org["id"], "m@example.com")
    n = join(client, h, org["id"], "n@example.com")
    owner_id, m_id, n_id = me(client, h)["id"], me(client, m)["id"], me(client, n)["id"]

    with SessionLocal() as db:
        # Cloud storage (PF4): m owns two live projects; a deleted one is not counted.
        _project(db, m_id, 150_000_000)
        _project(db, m_id, 2_500_000)
        _project(db, m_id, 9_999, deleted_at=now - timedelta(days=2))
        _project(db, owner_id, 1_000)

        # Panoramas (PF6): finished_at decides the month. This month: two
        # succeeded (one queued last month and finished in this month's first
        # second, one followed), one failed, one still running, a followed
        # set's tiles update and a pack (neither counts).
        _job(db, m_id, "panorama", "succeeded", this_month, created_at=last_month_end - timedelta(hours=1))
        _job(db, m_id, "panorama", "succeeded", now - timedelta(days=3), follow=True)
        _job(db, m_id, "panorama", "failed", now - timedelta(days=2))
        _job(db, m_id, "panorama", "running", None, created_at=now - timedelta(hours=1))
        _job(db, m_id, "tiles", "succeeded", now - timedelta(days=1))
        _job(db, m_id, "pack", "succeeded", now - timedelta(days=1))
        # Last month: one succeeded, in its last second.
        _job(db, m_id, "panorama", "succeeded", last_month_end)
        # An organisation account's job with the same number is not m's.
        _job(db, m_id, "panorama", "succeeded", now - timedelta(days=1), account_kind="org")

        # AI credits (PF11): usage rows minus refunds. This month 900 + 400 - 50.
        _ledger(db, m_id, "grant", 2000, this_month)
        _ledger(db, m_id, "usage", -900, now - timedelta(days=4))
        _ledger(db, m_id, "top_up", 5000, now - timedelta(days=3), bucket="top_up")
        _ledger(db, m_id, "usage", -400, now - timedelta(days=2), bucket="top_up")
        _ledger(db, m_id, "refund", 50, now - timedelta(days=1))
        _ledger(db, m_id, "adjust", -77, now - timedelta(hours=5))
        _ledger(db, m_id, "usage", -999, now - timedelta(days=1), account_kind="org")
        # Last month: 300 used, 20 refunded; its unused allowance expired at the turn.
        _ledger(db, m_id, "usage", -300, last_month_end)
        _ledger(db, m_id, "refund", 20, last_month + timedelta(days=3))
        _ledger(db, m_id, "expire", -1700, this_month)
        db.commit()

    return {
        "org": org, "owner": h, "m": m, "n": n, "owner_id": owner_id, "m_id": m_id, "n_id": n_id,
        "this": now.strftime("%Y-%m"), "last": last_month.strftime("%Y-%m"),
    }


def _rows(client, ctx, month: str | None = None) -> dict:
    q = f"?month={month}" if month else ""
    res = client.get(f"/orgs/{ctx['org']['id']}/usage{q}", headers=ctx["owner"])
    assert res.status_code == 200, res.text
    return {r["email"]: r for r in res.json()}


def _three(row: dict) -> tuple:
    return row["storage_bytes"], row["panoramas"], row["ai_credits"]


def test_orgs_usage_storage_panoramas_ai_credits(client, monkeypatch):
    ctx = _org_with_usage(client, monkeypatch)
    rows = _rows(client, ctx)
    assert _three(rows["m@example.com"]) == (152_500_000, 2, 1250)
    assert _three(rows["owner@example.com"]) == (1_000, 0, 0)
    # The month named explicitly is the same answer.
    assert _rows(client, ctx, ctx["this"])["m@example.com"] == rows["m@example.com"]
    # Storage is PF4's own figure, the `cloud_bytes` quota's.
    with SessionLocal() as db:
        assert rows["m@example.com"]["storage_bytes"] == quotas.bytes_used(db, ctx["m_id"])
    # Same keys as before (a platform route, no contract change).
    assert set(rows["m@example.com"]) == {
        "user_id", "email", "name", "role", "devices", "last_active_at", "api_requests", "floating_hours",
        "storage_bytes", "panoramas", "ai_credits",
    }


def test_orgs_usage_earlier_month_storage_null(client, monkeypatch):
    ctx = _org_with_usage(client, monkeypatch)
    rows = _rows(client, ctx, ctx["last"])
    assert _three(rows["m@example.com"]) == (None, 1, 280)
    assert _three(rows["n@example.com"]) == (None, 0, 0)
    assert _three(rows["owner@example.com"]) == (None, 0, 0)
    # Storage is a level with no history: null for any month but this one.
    assert _rows(client, ctx, "2020-01")["m@example.com"]["storage_bytes"] is None


def test_orgs_usage_no_usage_is_zero(client, monkeypatch):
    ctx = _org_with_usage(client, monkeypatch)
    assert _three(_rows(client, ctx)["n@example.com"]) == (0, 0, 0)


def test_orgs_usage_plain_member_forbidden(client, monkeypatch):
    ctx = _org_with_usage(client, monkeypatch)
    oid = ctx["org"]["id"]
    envelope(client.get(f"/orgs/{oid}/usage", headers=ctx["m"]), 403, "forbidden")
    envelope(client.get(f"/orgs/{oid}/usage?month={ctx['last']}", headers=ctx["n"]), 403, "forbidden")
    envelope(client.get(f"/orgs/{oid}/usage"), 401, "unauthenticated")
    envelope(client.get(f"/orgs/{oid}/usage?month=2026-1", headers=ctx["owner"]), 422, "validation_failed")


def test_orgs_usage_one_query_per_column(client, monkeypatch):
    ctx = _org_with_usage(client, monkeypatch)
    seen: list[str] = []

    def spy(conn, cursor, statement, parameters, context, executemany):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", spy)
    try:
        assert len(_rows(client, ctx)) == 3
    finally:
        event.remove(engine, "before_cursor_execute", spy)
    for table in ("projects", "render_jobs", "ai_credit_ledger"):
        hits = [s for s in seen if re.search(rf"\bFROM {table}\b", s)]
        assert len(hits) == 1, (table, hits)


def test_seed_member_usage_script(client, monkeypatch):
    clk = _mid_month(monkeypatch)
    h = signup(client, "owner@example.com")
    org = make_org(client, h)
    m = join(client, h, org["id"], "m@example.com")
    join(client, h, org["id"], "n@example.com")
    seed = load_script("seed_member_usage")
    with SessionLocal() as db:
        shown = seed.seed(db, "m@example.com", nbytes=268_435_456, panoramas=2, credits=1250)
    assert shown == {"storage_bytes": 268_435_456, "panoramas": 2, "ai_credits": 1250}
    rows = {r["email"]: r for r in client.get(f"/orgs/{org['id']}/usage", headers=h).json()}
    assert _three(rows["m@example.com"]) == (268_435_456, 2, 1250)
    assert _three(rows["n@example.com"]) == (0, 0, 0)
    last = (_month_start(clk.at) - timedelta(days=1)).strftime("%Y-%m")
    rows = {r["email"]: r for r in client.get(f"/orgs/{org['id']}/usage?month={last}", headers=h).json()}
    assert _three(rows["m@example.com"]) == (None, 0, 0)
    # Written through PF11's credits: the turns are on the balance, which never goes below zero.
    with SessionLocal() as db:
        balance = db.get(AiBalance, ("user", rows["m@example.com"]["user_id"]))
        assert balance is not None and balance.allowance_remaining + balance.top_up_remaining >= 0
        assert db.query(AiUsage).filter(AiUsage.account_id == balance.account_id).count() == 2
    # The member's own pages read the seeded rows: projects, jobs, cost units and AI turns.
    projects = client.get("/projects", headers={**m, "X-Truebex-Contract": "project-log/1.0"})
    assert projects.status_code == 200, projects.text
    assert [p["name"] for p in projects.json()["projects"]] == ["Seeded usage"]
    rj = {**m, "X-Truebex-Contract": "render-jobs/1.1"}
    jobs = client.get("/jobs?limit=20", headers=rj)
    assert jobs.status_code == 200, jobs.text
    assert [(j["kind"], j["state"]) for j in jobs.json()["jobs"]] == [("panorama", "succeeded")] * 2
    assert client.get("/jobs/usage", headers=rj).json()["used_cu"] == 0.4
    ai = client.get("/account/ai", headers=m)
    assert ai.status_code == 200, ai.text
    # An unknown address is refused.
    with SessionLocal() as db:
        try:
            seed.seed(db, "nobody@example.com")
        except SystemExit as exc:
            assert "nobody@example.com" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("an unknown address was seeded")
