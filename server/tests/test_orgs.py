"""Organisations, members, roles, invites, usage per member and the audit log
(PF3): a test per endpoint (happy path, auth failure, validation failure)."""

import csv
import io
from datetime import timedelta

from sqlalchemy import select

from app import mail, tasks
from app.database import SessionLocal
from app.licence import clock
from app.models import ApiKey, Subscription, UsageDaily, User
from app.orgs.models import AuditEvent, OrgInvite
from app.usage import utc_today

from .conftest import signup
from .licence_helpers import FP1, FP2, Clock, activated, refresh
from .org_helpers import (  # noqa: F401  (_clean_mail_and_caches is an autouse fixture)
    _clean_mail_and_caches,
    assign,
    envelope,
    grant,
    invite,
    join,
    load_script,
    make_org,
    me,
    set_floating,
    token_from_mail,
)


def test_orgs_create_and_list(client):
    h = signup(client, "owner@example.com")
    res = client.post("/orgs", json={"name": "  Studio North  "}, headers=h)
    assert res.status_code == 201
    org = res.json()
    assert org["role"] == "owner" and org["name"] == "Studio North" and org["slug"] == "studio-north"
    assert len(org["id"]) == 32 and int(org["id"], 16) >= 0
    # Slugs stay unique.
    assert make_org(client, h, "Studio North")["slug"] == "studio-north-2"

    listed = client.get("/orgs", headers=h).json()
    assert [o["slug"] for o in listed] == ["studio-north", "studio-north-2"]
    assert listed[0] == {"id": org["id"], "name": "Studio North", "slug": "studio-north", "role": "owner", "seat_kind": "none"}
    detail = client.get(f"/orgs/{org['id']}", headers=h).json()
    assert detail["members"] == 1 and detail["subscription"] is None and detail["seats"]["total"] == 0

    # Rename (admin), and someone else cannot even see it.
    assert client.patch(f"/orgs/{org['id']}", json={"name": "North Studio"}, headers=h).json()["name"] == "North Studio"
    other = signup(client, "stranger@example.com")
    envelope(client.get(f"/orgs/{org['id']}", headers=other), 404, "not_found")
    assert client.get("/orgs", headers=other).json() == []

    envelope(client.post("/orgs", json={"name": "Studio"}), 401, "unauthenticated")
    envelope(client.get("/orgs"), 401, "unauthenticated")
    envelope(client.post("/orgs", json={"name": "   "}, headers=h), 422, "validation_failed")
    envelope(client.post("/orgs", json={"name": "x" * 101}, headers=h), 422, "validation_failed")
    envelope(client.patch(f"/orgs/{org['id']}", json={"name": ""}, headers=h), 422, "validation_failed")


def test_orgs_delete_blocked_by_subscription(client):
    h = signup(client, "owner@example.com")
    org = make_org(client, h)
    admin = join(client, h, org["id"], "admin@example.com", role="admin")
    envelope(client.delete(f"/orgs/{org['id']}", headers=admin), 403, "forbidden")

    grant(org["slug"], "team", 3)
    body = envelope(client.delete(f"/orgs/{org['id']}", headers=h), 409, "live_subscription")
    assert body["data"] == {"plan": "team"}

    with SessionLocal() as db:
        load_script("grant_org_seats").grant(db, org["slug"], tier=None, seats=None, revoke=True)
    assert client.delete(f"/orgs/{org['id']}", headers=h).status_code == 204
    envelope(client.get(f"/orgs/{org['id']}", headers=h), 404, "not_found")
    assert client.get("/orgs", headers=admin).json() == []
    # The slug is free again; the audit trail keeps the deletion.
    assert make_org(client, h)["slug"] == "studio-north"
    with SessionLocal() as db:
        assert db.scalar(select(AuditEvent).where(AuditEvent.org_id == org["id"], AuditEvent.kind == "org.deleted"))
    envelope(client.delete(f"/orgs/{org['id']}"), 401, "unauthenticated")


def test_orgs_member_roles_and_last_owner(client):
    h = signup(client, "owner@example.com")
    org = make_org(client, h)
    oid = org["id"]
    admin = join(client, h, oid, "admin@example.com", role="admin")
    member = join(client, h, oid, "member@example.com")
    owner_id, admin_id, member_id = me(client, h)["id"], me(client, admin)["id"], me(client, member)["id"]

    members = client.get(f"/orgs/{oid}/members", headers=member).json()
    assert {(m["email"], m["role"]) for m in members} == {
        ("owner@example.com", "owner"), ("admin@example.com", "admin"), ("member@example.com", "member"),
    }
    assert set(members[0]) >= {"user_id", "email", "name", "role", "seat_kind", "last_active_at", "devices"}

    # An admin changes roles below owner.
    res = client.patch(f"/orgs/{oid}/members/{member_id}", json={"role": "billing"}, headers=admin)
    assert res.status_code == 200 and res.json()["role"] == "billing"
    # A member cannot; only an owner touches the owner role.
    envelope(client.patch(f"/orgs/{oid}/members/{admin_id}", json={"role": "member"}, headers=member), 403, "forbidden")
    envelope(client.patch(f"/orgs/{oid}/members/{owner_id}", json={"role": "admin"}, headers=admin), 403, "forbidden")
    envelope(client.patch(f"/orgs/{oid}/members/{member_id}", json={"role": "owner"}, headers=admin), 403, "forbidden")
    envelope(client.delete(f"/orgs/{oid}/members/{owner_id}", headers=admin), 403, "forbidden")

    # The last owner can neither be demoted nor leave.
    envelope(client.patch(f"/orgs/{oid}/members/{owner_id}", json={"role": "admin"}, headers=h), 409, "last_owner")
    envelope(client.delete(f"/orgs/{oid}/members/{owner_id}", headers=h), 409, "last_owner")
    # With a second owner the first may step down.
    assert client.patch(f"/orgs/{oid}/members/{admin_id}", json={"role": "owner"}, headers=h).status_code == 200
    assert client.patch(f"/orgs/{oid}/members/{owner_id}", json={"role": "member"}, headers=h).json()["role"] == "member"

    # A member leaves; an admin (now owner) removes someone, who gets an e-mail.
    mail.OUTBOX.clear()
    assert client.delete(f"/orgs/{oid}/members/{member_id}", headers=member).status_code == 204
    assert not [m for m in mail.OUTBOX if m.template == "org_removed"]
    assert client.delete(f"/orgs/{oid}/members/{owner_id}", headers=admin).status_code == 204
    removed = [m for m in mail.OUTBOX if m.template == "org_removed"]
    assert [m.to for m in removed] == ["owner@example.com"] and "Studio North" in removed[0].subject
    assert [m["email"] for m in client.get(f"/orgs/{oid}/members", headers=admin).json()] == ["admin@example.com"]

    envelope(client.patch(f"/orgs/{oid}/members/{admin_id}", json={"role": "boss"}, headers=admin), 422, "validation_failed")
    envelope(client.get(f"/orgs/{oid}/members"), 401, "unauthenticated")
    envelope(client.patch(f"/orgs/{oid}/members/999", json={"role": "member"}, headers=admin), 404, "not_found")


def test_orgs_invite_accept_flow(client):
    h = signup(client, "owner@example.com")
    org = make_org(client, h)
    grant(org["slug"], "team", 2)
    res = invite(client, h, org["id"], "A@Example.com", role="admin", seat="named")
    assert res.status_code == 201
    inv = res.json()
    assert inv["email"] == "a@example.com" and inv["status"] == "pending" and inv["seat_kind"] == "named"
    left = clock.parse_rfc3339(inv["expires_at"]) - clock.now()
    assert timedelta(days=6, hours=23) < left <= timedelta(days=7)

    # The console mail holds the link; only the token's hash is stored.
    msg = mail.OUTBOX[-1]
    assert msg.to == "a@example.com" and msg.template == "org_invite" and "Studio North" in msg.subject
    token = token_from_mail("a@example.com")
    assert f"https://truebex.com/invite/?t={token}" in msg.text and token in msg.html
    assert len(token) >= 43
    with SessionLocal() as db:
        row = db.get(OrgInvite, inv["id"])
        assert row.token_hash != token and len(row.token_hash) == 64

    # The invite page can show it before signing in.
    preview = client.post("/invites/preview", json={"token": token}).json()
    assert preview["org_name"] == "Studio North" and preview["email"] == "a@example.com" and preview["status"] == "pending"

    a = signup(client, "a@example.com")
    res = client.post("/invites/accept", json={"token": token}, headers=a)
    assert res.status_code == 200
    assert res.json() == {"org_id": org["id"], "role": "admin", "seat_kind": "named"}
    # Accepting again is harmless.
    assert client.post("/invites/accept", json={"token": token}, headers=a).status_code == 200
    members = {m["email"]: m for m in client.get(f"/orgs/{org['id']}/members", headers=h).json()}
    assert members["a@example.com"]["role"] == "admin" and members["a@example.com"]["seat_kind"] == "named"
    assert [o["role"] for o in client.get("/orgs", headers=a).json()] == ["admin"]
    seat_mail = [m for m in mail.OUTBOX if m.template == "org_seat_assigned"]
    assert [m.to for m in seat_mail] == ["a@example.com"]
    statuses = {i["email"]: i["status"] for i in client.get(f"/orgs/{org['id']}/invites", headers=h).json()}
    assert statuses == {"a@example.com": "accepted"}

    # Duplicates: a member, a pending invite.
    envelope(invite(client, h, org["id"], "a@example.com"), 409, "already_member")
    assert invite(client, h, org["id"], "b@example.com").status_code == 201
    dup = envelope(invite(client, h, org["id"], "b@example.com"), 409, "already_invited")
    assert dup["data"]["invite_id"]
    # Named seats: 2 bought, 1 assigned and 0 float, so one more pending named invite fills them.
    assert invite(client, h, org["id"], "c@example.com", seat="named").status_code == 201
    envelope(invite(client, h, org["id"], "d@example.com", seat="named"), 409, "no_seat_left")
    envelope(invite(client, h, org["id"], "e@example.com", seat="floating"), 409, "no_seat_left")
    envelope(invite(client, h, org["id"], "not-an-email"), 422, "validation_failed")
    envelope(invite(client, h, org["id"], "f@example.com", role="king"), 422, "validation_failed")
    envelope(client.post(f"/orgs/{org['id']}/invites", json={"email": "g@example.com"}), 401, "unauthenticated")
    member = join(client, h, org["id"], "m@example.com")
    envelope(invite(client, member, org["id"], "h@example.com"), 403, "forbidden")
    envelope(client.get(f"/orgs/{org['id']}/invites", headers=member), 403, "forbidden")


def test_orgs_invite_rejects_mismatch_and_expiry(client, monkeypatch):
    clk = Clock(monkeypatch)
    h = signup(client, "owner@example.com")
    org = make_org(client, h)
    assert invite(client, h, org["id"], "a@example.com").status_code == 201
    token = token_from_mail("a@example.com")

    envelope(client.post("/invites/accept", json={"token": token}), 401, "unauthenticated")
    other = signup(client, "other@example.com")
    body = envelope(client.post("/invites/accept", json={"token": token}, headers=other), 403, "email_mismatch")
    assert body["data"] == {"email": "a@example.com"}
    envelope(client.post("/invites/accept", json={"token": "x" * 43}, headers=other), 404, "not_found")
    envelope(client.post("/invites/accept", json={"token": "short"}, headers=other), 422, "validation_failed")

    # 7 days later the link has expired.
    a = signup(client, "a@example.com")
    clk.advance(days=7, seconds=1)
    envelope(client.post("/invites/accept", json={"token": token}, headers=a), 410, "invite_expired")
    assert client.get(f"/orgs/{org['id']}/members", headers=a).status_code == 404

    # Resend: a fresh link, and the old one no longer works.
    inv_id = client.get(f"/orgs/{org['id']}/invites", headers=h).json()[0]["id"]
    assert client.post(f"/orgs/{org['id']}/invites/{inv_id}/resend", headers=h).json()["status"] == "pending"
    fresh = token_from_mail("a@example.com")
    assert fresh != token
    envelope(client.post("/invites/accept", json={"token": token}, headers=a), 404, "not_found")
    # Revoke: the fresh link is refused too.
    assert client.delete(f"/orgs/{org['id']}/invites/{inv_id}", headers=h).status_code == 204
    envelope(client.post("/invites/accept", json={"token": fresh}, headers=a), 410, "invite_expired")
    envelope(client.delete(f"/orgs/{org['id']}/invites/{inv_id}"), 401, "unauthenticated")
    envelope(client.delete(f"/orgs/{org['id']}/invites/nope", headers=h), 404, "not_found")


def test_orgs_usage_per_member(client, monkeypatch):
    h = signup(client, "owner@example.com")
    org = make_org(client, h)
    grant(org["slug"], "team", 2)
    set_floating(client, h, org["id"], 1)
    b = join(client, h, org["id"], "b@example.com", seat="floating")
    owner_id, b_id = me(client, h)["id"], me(client, b)["id"]

    # API requests from usage_daily: 7 by the owner this month (and some last month).
    with SessionLocal() as db:
        key = ApiKey(user_id=owner_id, name="k", prefix="tbx_live_x", key_hash="0" * 64)
        db.add(key)
        db.flush()
        today = utc_today()
        db.add(UsageDaily(user_id=owner_id, api_key_id=key.id, day=today, endpoint="/v1/ping", count=7))
        db.add(UsageDaily(user_id=owner_id, api_key_id=key.id, day=today.replace(day=1) - timedelta(days=1),
                          endpoint="/v1/ping", count=100))
        db.commit()

    # Floating hours from b's lease: 90 minutes held, then released.
    clk = Clock(monkeypatch)
    dev = activated(client, b, FP2, "Test PC 2")
    clk.advance(minutes=90)
    assert client.post("/licence/release", headers={"Authorization": f"Bearer {dev['device_token']}"}).status_code == 204

    rows = {r["email"]: r for r in client.get(f"/orgs/{org['id']}/usage", headers=h).json()}
    assert rows["owner@example.com"]["api_requests"] == 7
    assert rows["b@example.com"]["floating_hours"] == 1.5 and rows["b@example.com"]["devices"] == 1
    assert rows["b@example.com"]["last_active_at"] is not None
    assert rows["owner@example.com"]["devices"] == 0 and rows["owner@example.com"]["floating_hours"] == 0
    for row in rows.values():
        assert row["storage_bytes"] is None and row["panoramas"] is None and row["ai_credits"] is None
    month = clock.now().strftime("%Y-%m")
    by_month = {r["email"]: r["api_requests"] for r in client.get(f"/orgs/{org['id']}/usage?month={month}", headers=h).json()}
    assert by_month == {"owner@example.com": 7, "b@example.com": 0}
    assert client.get(f"/orgs/{org['id']}/usage?month=2020-01", headers=h).json()[0]["api_requests"] == 0

    envelope(client.get(f"/orgs/{org['id']}/usage", headers=b), 403, "forbidden")
    envelope(client.get(f"/orgs/{org['id']}/usage"), 401, "unauthenticated")
    envelope(client.get(f"/orgs/{org['id']}/usage?month=2026-13", headers=h), 422, "validation_failed")
    assert b_id != owner_id


def test_orgs_audit_log_and_csv(client, monkeypatch):
    h = signup(client, "owner@example.com")
    org = make_org(client, h)
    oid = org["id"]
    grant(org["slug"], "team", 2)
    set_floating(client, h, oid, 1)
    a = join(client, h, oid, "a@example.com")
    a_id = me(client, a)["id"]
    assert assign(client, h, oid, a_id, "floating").status_code == 200  # seat change
    dev = activated(client, a, FP1)  # licence event (device.activated) + lease.taken
    assert refresh(client, dev["device_token"]).status_code == 200

    # An SSO sign-in is logged as sso.signin (the protocols are in test_sso.py).
    from app.orgs import audit
    with SessionLocal() as db:
        audit.record(db, oid, "sso.signin", actor=a_id, target_kind="user", target_id=a_id, protocol="oidc")
        db.commit()

    page = client.get(f"/orgs/{oid}/audit", headers=h).json()
    kinds = [e["kind"] for e in page["events"]]
    for kind in ("org.created", "invite.created", "invite.accepted", "member.joined", "seat.assigned",
                 "seats.floating_changed", "lease.taken", "device.activated", "sso.signin"):
        assert kind in kinds, kind
    assert page["next"] is None
    at = [e["at"] for e in page["events"]]
    assert at == sorted(at, reverse=True)
    lease = next(e for e in page["events"] if e["kind"] == "lease.taken")
    assert lease["actor"] == {"user_id": a_id, "email": "a@example.com"} and lease["target"]["kind"] == "device"

    # Filter by kind (a prefix matches its family) and page with the cursor.
    assert {e["kind"] for e in client.get(f"/orgs/{oid}/audit?kind=lease", headers=h).json()["events"]} == {"lease.taken"}
    seen, cursor = [], None
    while True:
        q = f"/orgs/{oid}/audit?limit=2" + (f"&cursor={cursor}" if cursor else "")
        body = client.get(q, headers=h).json()
        seen += [e["id"] for e in body["events"]]
        cursor = body["next"]
        if not cursor:
            break
    assert seen == [e["id"] for e in page["events"]]

    res = client.get(f"/orgs/{oid}/audit?format=csv", headers=h)
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
    assert 'attachment; filename="studio-north-audit-' in res.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(res.text)))
    assert rows[0] == ["at", "actor", "kind", "target", "details"]
    assert {r[2] for r in rows[1:]} >= {"lease.taken", "seat.assigned", "sso.signin", "invite.created"}
    assert any(r[1] == "a@example.com" and r[2] == "device.activated" for r in rows[1:])

    envelope(client.get(f"/orgs/{oid}/audit", headers=a), 403, "forbidden")
    envelope(client.get(f"/orgs/{oid}/audit?format=csv", headers=a), 403, "forbidden")
    envelope(client.get(f"/orgs/{oid}/audit"), 401, "unauthenticated")
    envelope(client.get(f"/orgs/{oid}/audit?cursor=nonsense", headers=h), 422, "validation_failed")
    envelope(client.get(f"/orgs/{oid}/audit?format=xml", headers=h), 422, "validation_failed")


def test_orgs_jobs_expire_invites_and_purge_audit(client, monkeypatch):
    h = signup(client, "owner@example.com")
    org = make_org(client, h)
    assert invite(client, h, org["id"], "late@example.com").status_code == 201
    with SessionLocal() as db:
        db.add(AuditEvent(org_id=org["id"], kind="old.event", at=clock.now() - timedelta(days=731), details={}))
        db.commit()
    later = clock.now() + timedelta(days=8)
    ran = tasks.run_due(later, force=True)
    assert {"orgs.invites.expire", "audit.purge", "licence.leases.expire", "sso.requests.purge"} <= set(ran)
    with SessionLocal() as db:
        inv = db.scalar(select(OrgInvite).where(OrgInvite.email == "late@example.com"))
        assert inv.expired_at is not None
        assert db.scalar(select(AuditEvent).where(AuditEvent.kind == "old.event")) is None
        assert db.scalar(select(AuditEvent).where(AuditEvent.kind == "invite.expired")) is not None


def test_grant_org_seats_script(client, capsys):
    h = signup(client, "owner@example.com")
    org = make_org(client, h)
    script = load_script("grant_org_seats")
    assert script.main(["--org", "studio-north", "--tier", "team", "--seats", "2"]) == 0
    assert "studio-north: team x 2 seats" in capsys.readouterr().out
    assert script.main(["--org", org["id"], "--tier", "enterprise", "--seats", "5", "--until", "2099-12-31"]) == 0
    with SessionLocal() as db:
        subs = list(db.scalars(select(Subscription).where(Subscription.organisation_id == org["id"])))
        assert len(subs) == 1 and subs[0].plan == "enterprise" and subs[0].seats == 5 and subs[0].provider == "manual"
        # Never the owner's personal plan.
        assert db.scalar(select(User).where(User.email == "owner@example.com")).plan == "free"
    assert me(client, h)["plan"] == "free"
    assert client.get(f"/orgs/{org['id']}", headers=h).json()["subscription"]["plan"] == "enterprise"
