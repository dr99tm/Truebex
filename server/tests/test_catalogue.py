"""The plan catalogue (server/app/catalogue.json) against licence-api.md §6.3."""

import json
from datetime import datetime, timedelta, timezone

from app.billing import service as billing
from app.database import SessionLocal
from app.models import Subscription, User
from app.plans import CATALOGUE_PATH, PLANS, get_plan, plan_rank

from .conftest import signup

FREE_FEATURES = {"export.pdf", "export.dxf", "lighting.full", "render.panorama"}
FREE_LIMITS = {"storeys": 1, "devices": 2, "share_links": 1, "cloud_cu_month": 0, "ai_credits_month": 0}
GATE_KEYS = {
    "export.clean", "export.dwg", "export.ifc", "assets.library", "share.links", "vr.pc", "mep",
    "analysis.reports", "market.cost", "cloud.sync", "cloud.panoramas", "collab.live", "ai.byok", "ai.metered",
}


def test_catalogue_matches_contract_placeholder():
    assert list(PLANS) == ["free", "pro", "studio", "team", "enterprise"]
    assert [p.rank for p in PLANS.values()] == sorted(p.rank for p in PLANS.values())
    assert [p.name for p in PLANS.values()] == ["Free", "Pro", "Studio", "Team", "Enterprise"]

    free = PLANS["free"]
    assert set(free.features) == FREE_FEATURES and "export.clean" not in free.features  # watermarked
    assert dict(free.limits) == FREE_LIMITS
    for tier in list(PLANS.values())[1:]:
        assert set(tier.features) == FREE_FEATURES | GATE_KEYS, tier.id
        assert dict(tier.limits) == {**FREE_LIMITS, "storeys": None}, tier.id
        assert list(tier.features) == sorted(set(tier.features))

    raw = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
    assert "GD7" in raw["source"]  # the TODO until GD7's matrix is copied in
    for t in raw["tiers"]:
        assert set(t) >= {"id", "name", "rank", "purchasable", "features", "limits", "api"}
        assert set(t["api"]) == {"monthly_requests", "max_api_keys"}
        assert len(t["features"]) == len(set(t["features"])) <= 200


def test_catalogue_existing_plans_keep_working(client):
    assert get_plan("pro").price_usd_cents == 9900 and get_plan("pro").purchasable
    assert get_plan("nonsense").id == "free"
    assert (get_plan("free").monthly_requests, get_plan("free").max_api_keys) == (1_000, 2)
    assert (get_plan("pro").monthly_requests, get_plan("pro").max_api_keys) == (100_000, 20)
    assert get_plan("enterprise").monthly_requests == 5_000_000
    assert [p for p in PLANS.values() if p.purchasable] == [PLANS["pro"]]

    h = signup(client)
    uid = client.get("/auth/me", headers=h).json()["id"]
    soon = datetime.now(timezone.utc) + timedelta(days=10)
    with SessionLocal() as db:
        db.add(Subscription(user_id=uid, plan="pro", provider="wayl", status="active", current_period_end=soon))
        db.commit()
    assert client.get("/auth/me", headers=h).json()["plan"] == "pro"
    assert client.get("/usage", headers=h).json()["limit"] == 100_000

    # Ranks come from the catalogue: a team row outranks pro (the old _RANK
    # read every id it did not know as free).
    assert plan_rank("team") > plan_rank("studio") > plan_rank("pro") > plan_rank("free")
    with SessionLocal() as db:
        db.add(Subscription(user_id=uid, plan="team", provider="stripe", status="active", current_period_end=soon))
        db.commit()
        user = db.get(User, uid)
        assert billing.effective_plan(db, user) == "team"
        assert billing.live_subscription(db, user).plan == "team"

    # On a tie a paid row beats the trial.
    with SessionLocal() as db:
        for sub in db.query(Subscription).filter_by(user_id=uid):
            db.delete(sub)
        db.add(Subscription(user_id=uid, plan="pro", provider="trial", status="active", current_period_end=soon))
        db.add(Subscription(user_id=uid, plan="pro", provider="stripe", status="active", current_period_end=soon))
        db.commit()
        assert billing.live_subscription(db, db.get(User, uid)).provider == "stripe"

    # The public catalogue shows the new names, the API limits are unchanged.
    plans = {p["id"]: p for p in client.get("/billing/plans").json()["plans"]}
    assert plans["free"]["name"] == "Free" and plans["pro"]["name"] == "Pro"
    assert plans["free"]["monthly_requests"] == 1000 and plans["free"]["max_api_keys"] == 2
