"""Where organisations (PF3) meet the project service (PF4).

* An organisation's named or floating seat is a plan for cloud projects:
  `seat_source` decides `cloud.sync` and the quotas, from the website and the
  app alike, and losing the seat closes the gate again.
* An organisation invitation (`/invite/?t=`) and a project invitation
  (`/invite/project/?t=`) are separate links: each token works only at its own
  endpoint.
"""

from app import mail
from app.projects.quotas import GIB

from .conftest import signup
from .licence_helpers import activated, error_of, fp
from .org_helpers import (  # noqa: F401  (_clean_mail_and_caches is an autouse fixture)
    _clean_mail_and_caches,
    assign,
    grant,
    invite,
    join,
    make_org,
    me,
    set_floating,
    token_from_mail,
)
from .project_helpers import CONTRACT, delta_op, dev, hex32, invite_token, pushed, web

NEW = {"name": "House", "doc_version": 38}


def _team(client, seats=2):
    owner = signup(client, "owner@example.com")
    org = make_org(client, owner)
    grant(org["slug"], "team", seats)
    return owner, org


def test_org_named_seat_unlocks_cloud_projects(client):
    owner, org = _team(client)
    member = join(client, owner, org["id"], "m@example.com")
    member_id = me(client, member)["id"]

    # A member without a seat is on their own Free plan.
    body = error_of(client.post("/projects", json=NEW, headers=web(member)), 403, "plan_required")
    assert body["data"] == {"feature": "cloud.sync", "plan": "free"}

    assert assign(client, owner, org["id"], member_id, "named").status_code == 200
    res = client.post("/projects", json=NEW, headers=web(member))
    assert res.status_code == 201, res.text
    pid = res.json()["project_id"]
    # The organisation's tier sets the owner's quotas (Team's placeholder).
    opened = client.get(f"/projects/{pid}", headers=web(member)).json()
    assert opened["role"] == "owner" and opened["quota"] == {"bytes": 200 * GIB, "bytes_used": 0}

    # The app: the seat reaches the device's entitlement and its pushes.
    device = activated(client, member, fingerprint=fp("m@example.com"), name="M")
    assert device["entitlement"]["document"]["plan"] == "team"
    token = device["device_token"]
    author = client.get("/licence/account", headers={"Authorization": f"Bearer {token}"}).json()["author_id"]
    answer = pushed(client, dev(token), pid, hex32(), [delta_op(author, [hex32()])])
    assert [r["status"] for r in answer["results"]] == ["accepted"]

    # Taking the seat away closes the gate; the project and its log stay.
    assert assign(client, owner, org["id"], member_id, "none").status_code == 200
    error_of(client.post("/projects", json=NEW, headers=web(member)), 403, "plan_required")
    res = client.post(f"/projects/{pid}/ops", json={"replica_id": hex32(), "ops": [delta_op(author, [hex32()])]}, headers=dev(token))
    assert error_of(res, 403, "plan_required")["data"]["feature"] == "cloud.sync"
    assert client.get(f"/projects/{pid}", headers=web(member)).json()["head_seq"] == 1


def test_org_floating_seat_unlocks_cloud_projects(client):
    owner, org = _team(client)
    set_floating(client, owner, org["id"], 1)
    member = join(client, owner, org["id"], "f@example.com")
    assert assign(client, owner, org["id"], me(client, member)["id"], "floating").status_code == 200

    # The website needs no lease: a floating member's session creates projects.
    res = client.post("/projects", json=NEW, headers=web(member))
    assert res.status_code == 201, res.text
    # The app takes the floating lease and creates and pushes as well.
    device = activated(client, member, fingerprint=fp("f@example.com"), name="F")
    assert device["entitlement"]["document"]["plan"] == "team"
    res = client.post("/projects", json={**NEW, "name": "Barn"}, headers=dev(device["device_token"]))
    assert res.status_code == 201, res.text


def test_org_and_project_invitations_are_separate_links(client):
    owner, org = _team(client)
    owner_id = me(client, owner)["id"]
    assert assign(client, owner, org["id"], owner_id, "named").status_code == 200
    pid = client.post("/projects", json=NEW, headers=web(owner)).json()["project_id"]

    # One person invited to both, in two e-mails with two kinds of link.
    assert invite(client, owner, org["id"], "x@example.com").status_code == 201
    res = client.post(f"/projects/{pid}/members", json={"email": "x@example.com", "role": "viewer"}, headers=web(owner))
    assert res.status_code == 201, res.text
    sent = [m for m in mail.OUTBOX if m.to == "x@example.com"]
    assert sorted(m.template for m in sent) == ["org_invite", "project_invite"]
    org_token = token_from_mail("x@example.com")
    project_token = invite_token(next(m for m in sent if m.template == "project_invite").text)
    assert org_token != project_token

    # Each token works only at its own endpoint.
    x = signup(client, "x@example.com")
    error_of(client.post("/projects/invites/accept", json={"token": org_token}, headers=web(x)), 404, "not_found")
    error_of(client.post("/invites/accept", json={"token": project_token}, headers=x), 404, "not_found")
    res = client.post("/projects/invites/accept", json={"token": project_token}, headers=web(x))
    assert res.status_code == 200 and res.json()["project"]["role"] == "viewer"
    res = client.post("/invites/accept", json={"token": org_token}, headers=x)
    assert res.status_code == 200 and res.json()["role"] == "member"
    # Joining the organisation gives no seat, so x reads the project but cannot create one.
    assert [p["project_id"] for p in client.get("/projects", headers=web(x)).json()["projects"]] == [pid]
    error_of(client.post("/projects", json=NEW, headers={**x, **CONTRACT}), 403, "plan_required")
