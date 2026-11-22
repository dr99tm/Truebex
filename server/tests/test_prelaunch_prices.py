"""Pre-launch (the owner, 2026-11-22): with HIDE_PRICES the API shows no price.

GET /billing/plans names the tiers without an amount, a founding offer or a
provider, and POST /billing/checkout sells nothing. Off (the default), both
answer as before. The website's own switch is PRELAUNCH.hidePricing; the two
are set the same way at a deploy (the truebex-deploy skill).
"""

import json
import re
from pathlib import Path

import pytest

from app.config import get_settings

from .conftest import checkout_body, signup

ROOT = Path(__file__).resolve().parents[2]
MONEY = re.compile(r"amount_minor|\d{3,}")


@pytest.fixture
def hidden(monkeypatch):
    monkeypatch.setattr(get_settings(), "hide_prices", True)


def test_prelaunch_plans_carry_no_price(client, hidden):
    res = client.get("/billing/plans")
    assert res.status_code == 200
    body = res.json()
    assert [t["id"] for t in body["tiers"]] == ["free", "pro", "team", "enterprise"]
    assert all(t["prices"] == [] for t in body["tiers"])
    assert body["provider"] is None
    assert body["founding"] == {
        "enabled": False, "total": 0, "remaining": 0, "discount_percent": 0,
        "ends_at": None, "tiers": [], "intervals": [],
    }
    # No amount anywhere in the tiers or the offer, whatever field it might sit in.
    assert not MONEY.search(json.dumps({"tiers": body["tiers"], "founding": body["founding"]}))


def test_prelaunch_checkout_sells_nothing(client, hidden):
    headers = signup(client, "buyer@example.com")
    res = client.post("/billing/checkout", json=checkout_body("pro"), headers=headers)
    assert res.status_code == 503
    assert "launch" in res.json()["detail"]


def test_prices_show_again_when_the_switch_is_off(client, monkeypatch):
    # Off by default: only the deployed .env turns it on. Read from the field, not
    # from get_settings(), which also reads this PC's server/.env (the live API's).
    assert type(get_settings()).model_fields["hide_prices"].default is False
    monkeypatch.setattr(get_settings(), "hide_prices", False)
    body = client.get("/billing/plans").json()
    pro = next(t for t in body["tiers"] if t["id"] == "pro")
    assert {"interval": "month", "currency": "GBP", "amount_minor": 2400} in pro["prices"]
    assert body["founding"]["total"] == 300


def test_prelaunch_switch_is_documented_for_the_deploy():
    """The site's switch is on in this tree, so the deploy notes must say to set the API's too."""
    constants = (ROOT / "src" / "lib" / "constants.ts").read_text(encoding="utf-8")
    site_hidden = bool(re.search(r"export const PRELAUNCH\b[^=]*=\s*\{\s*hidePricing:\s*true", constants))
    example = (ROOT / "server" / ".env.example").read_text(encoding="utf-8")
    assert "HIDE_PRICES" in example
    if site_hidden:
        skill = (ROOT / ".claude" / "skills" / "truebex-deploy" / "SKILL.md").read_text(encoding="utf-8")
        assert "HIDE_PRICES=true" in skill
