"""The public API grown to projects, jobs, shares and the marketplace (PF12):
API key scopes, the /v1 mirror of the contract routes, the burst limit."""

import json
import math

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import UsageDaily

from .conftest import signup
from .pf12_helpers import ALL_SCOPES, PL, RJ, SB, kh, make_key, make_legacy, sha
from .project_helpers import Person, delta_op, hex32, pull, pushed
from .project_helpers import create as create_project
from .render_helpers import project as project_with_snapshot
from .share_helpers import SHARE_FIXTURES, blobs_by_sha, fixture_json, house

READ = ["projects:read", "market:read"]


def _usage(user_email: str) -> dict[str, int]:
    from app.models import User

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == user_email))
        rows = db.scalars(select(UsageDaily).where(UsageDaily.user_id == user.id)).all()
        out: dict[str, int] = {}
        for r in rows:
            out[r.endpoint] = out.get(r.endpoint, 0) + r.count
        return out


# --- keys ---------------------------------------------------------------------------------


def test_keys_create_with_scopes_validation(client):
    session = signup(client)
    # 401 without a session.
    assert client.post("/keys", json={"name": "CI", "scopes": ["projects:read"]}).status_code == 401
    # 422 for an unknown scope, and for none at all.
    res = client.post("/keys", json={"name": "CI", "scopes": ["projects:write", "projects:delete"]}, headers=session)
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "validation_failed" and "projects:delete" in res.json()["detail"]
    assert client.post("/keys", json={"name": "CI", "scopes": []}, headers=session).status_code == 422
    # Chosen scopes come back in the catalogue's order; none given = the read scopes.
    made = make_key(client, session, ["webhooks:manage", "projects:write"])
    assert made["scopes"] == ["projects:write", "webhooks:manage"] and made["legacy"] is False
    plain = make_key(client, session, name="Reader")
    assert plain["scopes"] == READ
    listed = {k["name"]: k for k in client.get("/keys", headers=session).json()}
    assert listed["CI"]["scopes"] == ["projects:write", "webhooks:manage"] and "key" not in listed["CI"]
    # The catalogue of scopes the dashboard offers.
    scopes = client.get("/keys/scopes").json()
    assert [s["scope"] for s in scopes["scopes"]] == ALL_SCOPES and scopes["default"] == READ
    assert all(s["description"] for s in scopes["scopes"])
    # A key made before scopes reads as every read scope.
    make_legacy(plain["id"])
    old = next(k for k in client.get("/keys", headers=session).json() if k["id"] == plain["id"])
    assert old["scopes"] == READ and old["legacy"] is True
    account = client.get("/v1/account", headers=kh(made)).json()
    assert account["key"]["scopes"] == ["projects:write", "webhooks:manage"]
    assert account["key"]["author"] == format(made["id"], "032x")


# --- projects --------------------------------------------------------------------------------


def test_v1_projects_mirror_shapes(client):
    owner = Person(client, "owner@example.com")
    key = make_key(client, owner.session, ["projects:read", "projects:write"])
    auth = kh(key, **PL)

    # 5.1 create: the contract's record, the contract header echoed.
    res = client.post("/v1/projects", json={"name": "API House", "doc_version": 38}, headers=auth)
    assert res.status_code == 201, res.text
    assert res.headers["X-Truebex-Contract"] == "project-log/1.2" and "X-RateLimit-Remaining" in res.headers
    rec = res.json()
    contract_rec = create_project(client, owner.dev, "App House")
    assert set(rec) == set(contract_rec)
    assert rec["head_seq"] == 0 and rec["role"] == "owner" and rec["name"] == "API House" and rec["latest_snapshot"] is None
    pid = rec["project_id"]

    # 5.2 list and 5.3 open answer as the contract routes do.
    mine = client.get("/v1/projects", headers=auth).json()
    assert set(mine) == {"projects", "next_cursor"}
    assert mine == client.get("/projects", headers=owner.dev).json()
    opened = client.get(f"/v1/projects/{pid}", headers=auth).json()
    assert opened == client.get(f"/projects/{pid}", headers=owner.dev).json()
    assert opened["quota"] and opened["members"][0]["role"] == "owner"

    # 5.6 push from a key: author_kind agent, the key's own author id.
    wall = hex32()
    op = delta_op(owner.author_id, [wall])
    del op["author"], op["author_kind"]
    res = client.post(f"/v1/projects/{pid}/ops", json={"replica_id": hex32(), "ops": [op]}, headers=auth)
    assert res.status_code == 200, res.text
    assert res.json()["results"][0]["status"] == "accepted" and res.json()["head_seq"] == 1
    # A person's op in the app keeps working beside it.
    pushed(client, owner.dev, pid, owner.replica, [delta_op(owner.author_id, [hex32()], base_seq=1)])

    # 5.7 pull: the same body as the contract route.
    via_key = client.get(f"/v1/projects/{pid}/ops", params={"after": 0}, headers=auth).json()
    assert via_key == pull(client, owner.dev, pid)
    agent = via_key["ops"][0]
    assert agent["author_kind"] == "agent" and agent["author"] == format(key["id"], "032x")
    assert via_key["ops"][1]["author_kind"] == "person"

    # Validation failures keep the contract's envelope; a key cannot push as a person.
    bad = delta_op(owner.author_id, [hex32()], base_seq=2)
    res = client.post(f"/v1/projects/{pid}/ops", json={"replica_id": hex32(), "ops": [bad]}, headers=auth)
    assert res.status_code == 422 and res.json()["code"] == "validation_failed"
    res = client.post(f"/v1/projects/{pid}/ops", json={"replica_id": "nope", "ops": [op]}, headers=auth)
    assert res.status_code == 422 and res.json()["data"]["fields"][0]["field"] == "replica_id"
    res = client.post("/v1/projects", json={"name": "", "doc_version": 38}, headers=auth)
    assert res.status_code == 422 and res.json()["code"] == "validation_failed"

    # 5.8 a snapshot uploaded through /v1/uploads (purpose snapshot) and 5.9.
    tbxp = b"TBXP" + b"\0" * 2048
    opened = client.post(
        "/v1/uploads",
        json={"purpose": "snapshot", "files": [{"sha256": sha(tbxp), "bytes": len(tbxp), "content_type": "application/octet-stream"}]},
        headers=kh(key, **SB),
    )
    assert opened.status_code == 201, opened.text
    up = opened.json()
    put = client.put(
        f"/v1/uploads/{up['upload_id']}/files/{sha(tbxp)}/parts/0",
        content=tbxp,
        headers=kh(key, **SB, **{"X-Part-Sha256": sha(tbxp), "Content-Type": "application/octet-stream"}),
    )
    assert put.status_code == 204, put.text
    snap = client.post(
        f"/v1/projects/{pid}/snapshots",
        json={"at_seq": 2, "doc_version": 38, "upload_id": up["upload_id"], "files": {"tbxp": sha(tbxp), "tbxpack": None}},
        headers=auth,
    )
    assert snap.status_code == 201, snap.text
    latest = client.get(f"/v1/projects/{pid}/snapshots/latest", headers=auth).json()
    assert latest["snapshot_id"] == snap.json()["snapshot_id"] and latest["files"]["tbxp"]["url"]

    # 5.10-5.12 versions, 5.13-5.14 members, 5.17-5.18 presence.
    version = client.post(
        f"/v1/projects/{pid}/versions",
        json={"name": "Planning issue", "at_seq": 2, "snapshot_id": snap.json()["snapshot_id"]},
        headers=auth,
    )
    assert version.status_code == 201, version.text
    assert client.get(f"/v1/projects/{pid}/versions", headers=auth).json()["versions"][0]["name"] == "Planning issue"
    invited = client.post(f"/v1/projects/{pid}/members", json={"email": "friend@example.com", "role": "viewer"}, headers=auth)
    assert invited.status_code == 201, invited.text
    assert len(client.get(f"/v1/projects/{pid}/members", headers=auth).json()["members"]) == 2
    beat = client.put(f"/v1/projects/{pid}/presence", json={"replica_id": hex32(), "client": "web"}, headers=auth)
    assert beat.status_code == 200, beat.text
    assert len(client.get(f"/v1/projects/{pid}/presence", headers=auth).json()["present"]) == 1

    # 5.4 rename; 401 without a key.
    assert client.patch(f"/v1/projects/{pid}", json={"name": "API House 2"}, headers=auth).json()["name"] == "API House 2"
    assert client.get("/v1/projects", headers=PL).status_code == 401
    assert client.get("/v1/projects", headers={"Authorization": "Bearer tbx_live_nope", **PL}).status_code == 401

    # Metered per route in usage_daily, like every /v1 call.
    used = _usage(owner.email)
    assert used["/v1/projects"] >= 3
    assert used["/v1/projects/{project_id}/ops"] >= 4
    assert used["/v1/uploads"] == 1


def test_v1_scopes_enforced(client):
    owner = Person(client, "owner@example.com")
    pid = create_project(client, owner.dev)["project_id"]
    reader = make_key(client, owner.session, ["projects:read"])

    # projects:read cannot push: 403 forbidden naming the scope.
    op = delta_op(owner.author_id, [hex32()])
    del op["author"], op["author_kind"]
    res = client.post(f"/v1/projects/{pid}/ops", json={"replica_id": hex32(), "ops": [op]}, headers=kh(reader, **PL))
    assert res.status_code == 403, res.text
    body = res.json()
    assert body["code"] == "forbidden" and body["data"]["needed"] == "projects:write"
    assert body["data"]["scopes"] == ["projects:read"]
    assert client.get(f"/v1/projects/{pid}", headers=kh(reader, **PL)).status_code == 200

    # An old key without scopes reads but cannot write.
    old = make_key(client, owner.session, ["projects:write"], name="Old")
    make_legacy(old["id"])
    assert client.get("/v1/projects", headers=kh(old, **PL)).status_code == 200
    res = client.post("/v1/projects", json={"name": "No", "doc_version": 38}, headers=kh(old, **PL))
    assert res.status_code == 403 and res.json()["data"]["needed"] == "projects:write"
    assert client.get("/v1/account", headers=kh(old)).json()["key"]["scopes"] == READ

    # Every other group checks its own scope.
    for method, path, needed in [
        ("post", "/v1/jobs", "jobs:write"),
        ("get", "/v1/shares", "shares:write"),
        ("get", "/v1/webhooks", "webhooks:manage"),
    ]:
        res = getattr(client, method)(path, headers=kh(reader), **({"json": {}} if method == "post" else {}))
        assert res.status_code == 403, (path, res.text)
        assert res.json()["data"]["needed"] == needed, path
    res = client.post(
        "/v1/uploads",
        json={"purpose": "share", "files": [{"sha256": "0" * 64, "bytes": 1, "content_type": "image/jpeg"}]},
        headers=kh(reader, **SB),
    )
    assert res.status_code == 403 and res.json()["data"]["needed"] == "shares:write"
    # A refused call is still a counted call (the key did authenticate).
    assert _usage(owner.email)["/v1/jobs"] == 1


def test_v1_key_cannot_delete_project(client):
    owner = Person(client, "owner@example.com")
    key = make_key(client, owner.session, ALL_SCOPES)
    pid = client.post("/v1/projects", json={"name": "Keep", "doc_version": 38}, headers=kh(key, **PL)).json()["project_id"]
    res = client.delete(f"/v1/projects/{pid}", headers=kh(key, **PL))
    assert res.status_code == 403, res.text
    assert res.json()["code"] == "session_required"
    assert client.get(f"/v1/projects/{pid}", headers=kh(key, **PL)).status_code == 200
    # The website still deletes it.
    assert client.delete(f"/projects/{pid}", headers={**owner.session, **PL}).status_code == 204


def test_v1_jobs_pack_export(client):
    owner = Person(client, "owner@example.com")
    pid, head = project_with_snapshot(client, owner)
    key = make_key(client, owner.session, ["projects:read", "jobs:write"])
    body = {"kind": "pack", "project_id": pid, "at_seq": head, "params": {"items": ["sheets"]}}
    # 401 without a key.
    assert client.post("/v1/jobs", json=body, headers=RJ).status_code == 401
    res = client.post("/v1/jobs", json=body, headers=kh(key, **RJ, **{"Idempotency-Key": hex32()}))
    assert res.status_code == 201, res.text
    job = res.json()
    assert job["kind"] == "pack" and job["state"] == "queued" and job["cost_units_estimate"] > 0
    assert res.headers["X-Truebex-Contract"] == "render-jobs/1.4"
    assert client.get(f"/v1/jobs/{job['job_id']}", headers=kh(key, **RJ)).json()["job_id"] == job["job_id"]
    assert [j["job_id"] for j in client.get("/v1/jobs", headers=kh(key, **RJ)).json()["jobs"]] == [job["job_id"]]
    assert client.get("/v1/jobs/usage", headers=kh(key, **RJ)).json()["limit_cu"] is not None
    # Output before it ran: the contract's 409.
    assert client.get(f"/v1/jobs/{job['job_id']}/output", headers=kh(key, **RJ)).json()["code"] == "not_ready"
    # Validation failures pass through: an unknown item, a body that is not an object.
    bad = {**body, "params": {"items": ["ifc"]}}
    res = client.post("/v1/jobs", json=bad, headers=kh(key, **RJ))
    assert res.status_code == 422 and res.json()["data"]["fields"][0]["field"] == "params.items"
    res = client.post("/v1/jobs", content=b"[1]", headers=kh(key, **RJ, **{"Content-Type": "application/json"}))
    assert res.status_code == 422 and res.json()["code"] == "validation_failed"
    # Cancel needs jobs:write and answers the record.
    assert client.post(f"/v1/jobs/{job['job_id']}/cancel", headers=kh(key, **RJ)).json()["state"] == "cancelled"


def test_v1_shares_with_key(client):
    session = signup(client, "designer@example.com")
    key = make_key(client, session, ["shares:write"])
    auth = kh(key, **SB)
    # 422 manifest errors pass through unchanged.
    case = fixture_json("manifest-invalid.json")["cases"][0]
    res = client.post("/v1/shares", json={"title": "Broken", "manifest": case["manifest"]}, headers=auth)
    assert res.status_code == case["expect"]["status"], res.text
    assert res.json()["code"] == case["expect"]["code"]
    assert [{"path": e["path"], "rule": e["rule"]} for e in res.json()["data"]["errors"]] == case["expect"]["errors"]

    # Create → upload every part through /v1/uploads → publish.
    res = client.post("/v1/shares", json={"title": "House — client review", "manifest": house()}, headers=auth)
    assert res.status_code == 201, res.text
    created = res.json()
    upload = created["upload"]
    share_id = created["share"]["share_id"]
    assert created["share"]["state"] == "uploading"
    # Publishing before the files arrive: the contract's 422.
    assert client.post(f"/v1/shares/{share_id}/publish", headers=auth).json()["code"] == "upload_incomplete"
    data = blobs_by_sha()
    for f in upload["files"]:
        blob = data[f["sha256"]]
        size = upload["part_bytes"]
        for n in range(math.ceil(len(blob) / size)):
            chunk = blob[n * size : (n + 1) * size]
            put = client.put(
                f"/v1/uploads/{upload['upload_id']}/files/{f['sha256']}/parts/{n}",
                content=chunk,
                headers={**auth, "X-Part-Sha256": sha(chunk), "Content-Type": "application/octet-stream"},
            )
            assert put.status_code == 204, put.text
    status = client.get(f"/v1/uploads/{upload['upload_id']}", headers=auth).json()
    assert all(f["state"] == "complete" for f in status["files"])
    res = client.post(f"/v1/shares/{share_id}/publish", headers=auth)
    assert res.status_code == 200, res.text
    share = res.json()["share"]
    assert share["state"] == "live" and share["url"]
    # 5.6-5.9.
    listed = client.get("/v1/shares", headers=auth).json()
    assert [s["share_id"] for s in listed["shares"]] == [share_id] and "limits" in listed
    assert client.patch(f"/v1/shares/{share_id}", json={"title": "Renamed"}, headers=auth).json()["title"] == "Renamed"
    assert client.get(f"/v1/shares/{share_id}", headers=auth).json()["visits"]["total"] == 0
    assert client.delete(f"/v1/shares/{share_id}", headers=auth).json()["state"] == "revoked"
    # Another account's key sees nothing.
    other = make_key(client, signup(client, "other@example.com"), ["shares:write"])
    assert client.get(f"/v1/shares/{share_id}", headers=kh(other, **SB)).status_code == 404
    assert (SHARE_FIXTURES / "manifest-house.json").is_file()


def test_v1_burst_limit(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "api_key_burst", 3)
    monkeypatch.setattr(s, "api_key_per_minute", 1)
    session = signup(client)
    key = make_key(client, session)
    for _ in range(3):
        assert client.get("/v1/ping", headers=kh(key)).status_code == 200
    res = client.get("/v1/ping", headers=kh(key))
    assert res.status_code == 429, res.text
    body = res.json()
    assert body["code"] == "rate_limited" and body["data"]["limit"] == "burst"
    assert body["retry_after_s"] >= 1 and res.headers["Retry-After"] == str(body["retry_after_s"])
    # Before the monthly quota: the refused call is not counted, and another
    # key of the same account has its own bucket.
    assert _usage("dev@example.com")["/v1/ping"] == 3
    second = make_key(client, session, name="Second")
    assert client.get("/v1/ping", headers=kh(second)).status_code == 200


def test_market_reads_with_key(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "market_reads_per_minute", 2)
    market = {"X-Truebex-Contract": "marketplace-api/1.1"}
    for _ in range(2):
        assert client.get("/market/regions", headers=market).status_code == 200
    assert client.get("/market/regions", headers=market).json()["code"] == "rate_limited"
    # A key with market:read lifts the anonymous limit and is metered.
    session = signup(client)
    key = make_key(client, session)  # the read scopes
    for _ in range(4):
        res = client.get("/market/regions", headers=kh(key, **market))
        assert res.status_code == 200, res.text
        assert "X-RateLimit-Remaining" in res.headers
    assert _usage("dev@example.com")["/market/regions"] == 4
    # Without market:read: 403; a bad key: 401.
    writer = make_key(client, session, ["projects:write"], name="Writer")
    res = client.get("/market/categories", headers=kh(writer, **market))
    assert res.status_code == 403 and res.json()["data"]["needed"] == "market:read"
    assert client.get("/market/categories", headers={"X-API-Key": "tbx_live_nope", **market}).status_code == 401


def test_feeds_need_supplier_feed_scope(client, monkeypatch):
    from .supplier_helpers import FEED_CSV, no_internet, post_feed, verified

    no_internet(monkeypatch)
    h, _sid = verified(client)
    # PF8's own rule comes first: a key whose owner is no catalogue member is refused as before.
    stranger = make_key(client, signup(client, "stranger@example.com"), ["supplier:feed"])
    assert post_feed(client, stranger["key"], FEED_CSV).json()["code"] == "not_supplier"
    # A member's developer key needs supplier:feed …
    plain = make_key(client, h, ["projects:read"])
    res = post_feed(client, plain["key"], FEED_CSV)
    assert res.status_code == 403 and res.json()["data"]["needed"] == "supplier:feed"
    assert client.get(f"/market/feeds/{hex32()}", headers=kh(plain)).json()["code"] == "forbidden"
    # … or was made before scopes existed.
    make_legacy(plain["id"])
    assert post_feed(client, plain["key"], FEED_CSV).status_code == 202
    feeder = make_key(client, h, ["supplier:feed"], name="Feeds")
    assert post_feed(client, feeder["key"], FEED_CSV).status_code == 202


def test_v1_openapi_scopes_named():
    """Every /v1 operation has an id and names the scope it needs (or none)."""
    from app.main import app

    schema = app.openapi()
    for path, item in schema["paths"].items():
        if not path.startswith("/v1/"):
            continue
        for method, op in item.items():
            assert op.get("operationId"), (method, path)
            scope = op.get("x-truebex-scope")
            assert scope is None or scope in ALL_SCOPES, (method, path, scope)
    assert json.dumps(schema)  # serialisable
