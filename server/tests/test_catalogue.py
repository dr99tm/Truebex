"""The plan catalogue (server/app/catalogue.json) against licence-api.md §6.3."""

import json
from datetime import datetime, timedelta, timezone

from app.billing import service as billing
from app.database import SessionLocal
from app.models import Subscription, User
from app.plans import CATALOGUE_PATH, PLANS, get_plan, rank

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
    assert raw["schema"] == "truebex-catalogue/1" and "6.3" in raw["source"]  # placeholder until GD7
    for t in raw["tiers"]:
        assert set(t) >= {"id", "name", "rank", "purchasable", "features", "limits", "api"}
        assert set(t["api"]) == {"monthly_requests", "max_api_keys"}
        assert len(t["features"]) == len(set(t["features"])) <= 200


def test_catalogue_existing_plans_keep_working(client):
    assert get_plan("pro").price("month", "USD").amount_minor == 2900 and get_plan("pro").purchasable
    assert get_plan("nonsense").id == "free"
    assert (get_plan("free").monthly_requests, get_plan("free").max_api_keys) == (1_000, 2)
    assert (get_plan("pro").monthly_requests, get_plan("pro").max_api_keys) == (100_000, 20)
    assert get_plan("enterprise").monthly_requests == 5_000_000
    # Sold online: the tiers PF2 priced (Free and Enterprise are not), less
    # Studio, unlisted since 2026-11-10 (the same as Pro until its extras ship).
    assert [p.id for p in PLANS.values() if p.purchasable] == ["pro", "team"]
    assert all(p.prices for p in PLANS.values() if p.purchasable)
    assert [p.id for p in PLANS.values() if not p.listed] == ["studio"]
    assert get_plan("studio").prices and not get_plan("studio").purchasable

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
    assert rank("team") > rank("studio") > rank("pro") > rank("free")
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

    # The public catalogue shows the new names (PF2's /billing/plans lists
    # tiers and prices; the API limits above come from the same catalogue).
    tiers = {t["id"]: t for t in client.get("/billing/plans").json()["tiers"]}
    assert tiers["free"]["name"] == "Free" and tiers["pro"]["name"] == "Pro"
    assert [t["id"] for t in tiers.values() if t["purchasable"]] == ["pro", "team"]
    assert "studio" not in tiers


def test_catalogue_unlisted_studio_keeps_its_subscribers(client):
    """Studio is unlisted and not sold since 2026-11-10 (the same as Pro until
    its extras ship): /billing/plans leaves it out and checkout refuses it,
    while an existing Studio subscription keeps its plan, its name and its
    entitlements."""
    from app.ai.credits import plan_needed
    from app.licence.service import account_panel

    from .conftest import checkout_body

    assert "studio" not in {t["id"] for t in client.get("/billing/plans").json()["tiers"]}
    h = signup(client)
    res = client.post("/billing/checkout", json=checkout_body(tier="studio"), headers=h)
    assert res.status_code == 400 and "can't be bought" in res.json()["detail"]
    # Pro credits point at a tier on sale.
    assert plan_needed(get_plan("pro")) == "team"

    uid = client.get("/auth/me", headers=h).json()["id"]
    soon = datetime.now(timezone.utc) + timedelta(days=20)
    with SessionLocal() as db:
        db.add(Subscription(user_id=uid, plan="studio", provider="paddle", status="active",
                            interval="month", currency="GBP", current_period_end=soon))
        db.commit()
    assert client.get("/auth/me", headers=h).json()["plan"] == "studio"
    assert client.get("/billing/subscription", headers=h).json()["tier"] == "studio"
    with SessionLocal() as db:
        panel = account_panel(db, db.get(User, uid), None)
    assert (panel["plan"], panel["plan_name"]) == ("studio", "Studio")
    assert set(get_plan("studio").features) == set(get_plan("pro").features)
