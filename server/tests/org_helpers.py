"""Shared helpers for the organisation, seat and SSO tests (PF3)."""

import importlib.util
import re
from pathlib import Path

import pytest

from app import mail
from app.database import SessionLocal
from app.sso import oidc

from .conftest import signup

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


@pytest.fixture(autouse=True)
def _clean_mail_and_caches():
    mail.OUTBOX.clear()
    oidc.clear_caches()
    yield
    mail.OUTBOX.clear()
    oidc.clear_caches()


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def me(client, headers) -> dict:
    return client.get("/auth/me", headers=headers).json()


def make_org(client, headers, name="Studio North") -> dict:
    res = client.post("/orgs", json={"name": name}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def grant(org_ref: str, tier="team", seats=2, until=None):
    with SessionLocal() as db:
        return load_script("grant_org_seats").grant(db, org_ref, tier=tier, seats=seats, until=until)


def invite(client, headers, org_id, email, role="member", seat="none"):
    return client.post(f"/orgs/{org_id}/invites", json={"email": email, "role": role, "seat": seat}, headers=headers)


def token_from_mail(email: str) -> str:
    msg = next(m for m in reversed(mail.OUTBOX) if m.to == email and m.template == "org_invite")
    return re.search(r"/invite/\?t=([A-Za-z0-9_-]+)", msg.text).group(1)


def join(client, owner_headers, org_id, email, role="member", seat="none") -> dict:
    """Invite `email`, sign them up and accept: their session headers."""
    res = invite(client, owner_headers, org_id, email, role, seat)
    assert res.status_code == 201, res.text
    headers = signup(client, email)
    res = client.post("/invites/accept", json={"token": token_from_mail(email)}, headers=headers)
    assert res.status_code == 200, res.text
    return headers


def set_floating(client, headers, org_id, floating: int):
    res = client.put(f"/orgs/{org_id}/seats/settings", json={"floating": floating}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def assign(client, headers, org_id, user_id, kind):
    return client.put(f"/orgs/{org_id}/seats/{user_id}", json={"kind": kind}, headers=headers)


def envelope(res, status: int, code: str) -> dict:
    assert res.status_code == status, res.text
    body = res.json()
    assert body["code"] == code, body
    assert isinstance(body["detail"], str) and body["detail"]
    return body
