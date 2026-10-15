"""A project's followed panorama sets through /v1 for API keys (PF12a).

`GET /v1/projects/{pid}/panoramas` and `…/panoramas/{set_id}` need
`projects:read` and hand each call to PF9's session handlers
(app/routers/mobile.py) with the key as an `api_key` caller, so the shapes,
the viewer-role rule, 404 for a non-member, the `rev` + `wait_s` long-poll
(no database connection held while waiting) and `Cache-Control: private,
no-store` are the session routes'; metering and the burst limit are every
/v1 read's (deps.api_key_auth). The doc's five names first, then the
document, the SDK and the burst limit."""

import json
import re
import sys
import time

import pytest

from app.config import get_settings
from app.database import engine
from app.projects import presence, waiters
from app.render import queue

from .conftest import LongPoll
from .licence_helpers import error_of
from .pf12_helpers import PL, ROOT, kh, make_key, make_legacy
from .project_helpers import CONTRACT, Person, create, hex32, invite_and_accept
from .render_helpers import WALL, admin, claimed, finish, issue_worker, project, push_touch, rj, submitted
from .test_mobile import _followed_set
from .test_pf12_api import _usage
from .test_pf12_openapi_sdks import live_api  # noqa: F401  (the fixture)

DOC = ROOT / "openapi" / "v1.json"
LIST_ROUTE = "/v1/projects/{project_id}/panoramas"
SET_ROUTE = "/v1/projects/{project_id}/panoramas/{set_id}"


@pytest.fixture(autouse=True)
def _clean_project_state():
    presence.reset()
    waiters.reset()
    yield
    presence.reset()
    waiters.reset()


def _house(client):
    """The owner (Pro trial) with a project, Sam a viewer of it, and one followed set of the owner's."""
    owner = Person(client, "owner@example.com")
    sam = Person(client, "sam@example.com", trial=False)
    pid = create(client, owner.dev)["project_id"]
    invite_and_accept(client, owner, pid, sam, "viewer")
    return owner, sam, pid, _followed_set(owner.user_id, pid)


def _without_request_id(body: dict) -> dict:
    return {k: v for k, v in body.items() if k != "request_id"}


# --- the doc's tests ------------------------------------------------------------------------------


def test_v1_panoramas_list_with_key(client):
    owner, sam, pid, set_id = _house(client)
    key = make_key(client, owner.session, ["projects:read"])

    listed = client.get(f"/v1/projects/{pid}/panoramas", headers=kh(key, **PL))
    assert listed.status_code == 200, listed.text
    assert listed.headers["cache-control"] == "private, no-store"
    assert listed.headers["x-truebex-contract"] == "project-log/1.1" and "x-ratelimit-remaining" in listed.headers
    # The same body as the session route answers the same account.
    assert listed.json() == client.get(f"/projects/{pid}/panoramas", headers=owner.web).json()
    sets = listed.json()["sets"]
    assert [s["set_id"] for s in sets] == [set_id]
    assert sets[0]["mine"] is True and sets[0]["following"] is True and sets[0]["rev"] == 1

    state = client.get(f"/v1/projects/{pid}/panoramas/{set_id}", headers=kh(key, **PL))
    assert state.status_code == 200, state.text
    assert state.headers["cache-control"] == "private, no-store"
    body = state.json()
    assert body == client.get(f"/projects/{pid}/panoramas/{set_id}", headers=owner.web).json()
    assert body["rev"] == 1 and body["follow_job_id"] == set_id and body["following"] is True
    assert body["manifest"]["schema"] == "truebex-tiles/1" and body["manifest"]["tiles_base"]

    # The viewer-role rule: a viewer's key reads the owner's set, not marked as its own.
    viewer = make_key(client, sam.session, ["projects:read"])
    as_viewer = client.get(f"/v1/projects/{pid}/panoramas", headers=kh(viewer, **PL))
    assert as_viewer.status_code == 200, as_viewer.text
    assert as_viewer.json() == client.get(f"/projects/{pid}/panoramas", headers=sam.web).json()
    assert as_viewer.json()["sets"][0]["mine"] is False
    assert client.get(f"/v1/projects/{pid}/panoramas/{set_id}", headers=kh(viewer, **PL)).json() == body

    # Metered per route, like every /v1 read.
    used = _usage(owner.email)
    assert used[LIST_ROUTE] == 1 and used[SET_ROUTE] == 1


def test_v1_panoramas_need_projects_read(client):
    owner, _, pid, set_id = _house(client)
    paths = (f"/v1/projects/{pid}/panoramas", f"/v1/projects/{pid}/panoramas/{set_id}")

    # A key without the scope: 403 naming it.
    writer = make_key(client, owner.session, ["jobs:write"])
    for path in paths:
        body = error_of(client.get(path, headers=kh(writer, **PL)), 403, "forbidden")
        assert body["data"]["needed"] == "projects:read" and body["data"]["scopes"] == ["jobs:write"]

    # No key, a wrong key, or the app's and the website's own credentials: 401.
    for headers in (PL, kh("tbx_live_nope", **PL), {**owner.web, **PL}, {**owner.dev, **PL}):
        for path in paths:
            error_of(client.get(path, headers=headers), 401, "unauthenticated")

    # A key made before scopes keeps every read scope, so it reads.
    old = make_key(client, owner.session, ["projects:write"], name="Old")
    make_legacy(old["id"])
    for path in paths:
        assert client.get(path, headers=kh(old, **PL)).status_code == 200

    # The session routes still take a session or a device token only.
    reader = make_key(client, owner.session, ["projects:read"], name="Reader")
    error_of(client.get(f"/projects/{pid}/panoramas", headers=kh(reader, **PL)), 401, "unauthenticated")
    error_of(client.get(f"/projects/{pid}/panoramas/{set_id}", headers=kh(reader, **PL)), 401, "unauthenticated")


def test_v1_panorama_set_long_poll(client, wakeups):
    """PF6's loop: a followed set rendered by a worker; the key's read waits on `rev`, wakes when an edit's
    `tiles` job finishes, and otherwise returns at `wait_s` with no database connection held meanwhile.
    `wakeups` patches the re-check above the wait: only a wake-up (or the deadline) ends a wait here."""
    owner = Person(client, "owner@example.com")
    pid, head = project(client, owner)
    token = issue_worker(client, admin(client))
    set_id = submitted(client, rj(owner), project_id=pid, at_seq=head, follow=True)["job_id"]
    finish(client, token, claimed(client, token))
    key = make_key(client, owner.session, ["projects:read"])
    url = f"/v1/projects/{pid}/panoramas/{set_id}"
    first = client.get(url, headers=kh(key, **PL)).json()
    assert first["rev"] == 1 and first["manifest"]["faces_rendered"] == 6
    waiting_on, wait_s = queue.job_key(set_id), queue.STATUS_WAIT_MAX_S

    # An edit while the key waits: the worker's tiles job moves the set's rev and wakes the read.
    reader = LongPoll(lambda: client.get(url, params={"rev": 1, "wait_s": wait_s}, headers=kh(key, **PL)))
    wakeups.until_waiting(waiting_on)
    push_touch(client, owner, pid, [WALL])
    finish(client, token, claimed(client, token), "manifest-tiles.json", wall_s=20)
    moved = reader.answer()
    assert moved.status_code == 200, moved.text
    assert moved.headers["cache-control"] == "private, no-store"
    assert moved.json()["rev"] == 2 and moved.json()["manifest"]["faces_rendered"] == 2
    wakeups.assert_woken(waiting_on, "the tiles job")
    assert reader.took < wait_s / 2
    assert moved.json() == client.get(f"/projects/{pid}/panoramas/{set_id}", headers=owner.web).json()

    # Nothing newer than rev 2: the read returns the same state at wait_s, holding no connection meanwhile.
    wakeups.clear()
    reader = LongPoll(lambda: client.get(url, params={"rev": 2, "wait_s": 1.5}, headers=kh(key, **PL)))
    wakeups.until_waiting(waiting_on)  # inside its wait, past the read made right after the waiter registered
    held = engine.pool.checkedout()
    same = reader.answer()
    assert same.status_code == 200 and same.json()["rev"] == 2
    assert reader.took >= 1.4
    wakeups.assert_deadline(waiting_on)
    assert held == 0, "a waiting /v1 panorama read held a database connection"

    # A rev already passed, or no rev: answered at once, without a wait (one would last the whole wait_s).
    wakeups.clear()
    started = time.monotonic()
    assert client.get(url, params={"rev": 0, "wait_s": wait_s}, headers=kh(key, **PL)).json()["rev"] == 2
    assert client.get(url, params={"wait_s": wait_s}, headers=kh(key, **PL)).json()["rev"] == 2
    assert wakeups.ended(waiting_on) == []
    assert time.monotonic() - started < wait_s / 2


def test_v1_panoramas_non_member_404(client):
    owner, sam, pid, set_id = _house(client)
    stranger = Person(client, "stranger@example.com", trial=False)
    outsider = make_key(client, stranger.session, ["projects:read"])
    error_of(client.get(f"/v1/projects/{pid}/panoramas", headers=kh(outsider, **PL)), 404, "not_found")
    error_of(client.get(f"/v1/projects/{pid}/panoramas/{set_id}", headers=kh(outsider, **PL)), 404, "not_found")

    key = make_key(client, owner.session, ["projects:read"])
    for path in (
        f"/v1/projects/{hex32()}/panoramas",  # no such project
        f"/v1/projects/{pid}/panoramas/{hex32()}",  # no such set
        f"/v1/projects/{pid}/panoramas/not-a-set",
    ):
        error_of(client.get(path, headers=kh(key, **PL)), 404, "not_found")
    # A set of another project is not this project's.
    other = create(client, owner.dev, "Other")["project_id"]
    error_of(client.get(f"/v1/projects/{other}/panoramas/{set_id}", headers=kh(key, **PL)), 404, "not_found")

    # A set kept by someone who left the project is not served, and a key of someone who left reads nothing.
    editor = Person(client, "ed@example.com")
    invite_and_accept(client, owner, pid, editor, "editor")
    eds = _followed_set(editor.user_id, pid)
    eds_key = make_key(client, editor.session, ["projects:read"])
    assert len(client.get(f"/v1/projects/{pid}/panoramas", headers=kh(key, **PL)).json()["sets"]) == 2
    assert client.get(f"/v1/projects/{pid}/panoramas/{eds}", headers=kh(eds_key, **PL)).status_code == 200
    assert client.delete(f"/projects/{pid}/members/{editor.user_id}", headers=owner.web).status_code == 204
    assert [s["set_id"] for s in client.get(f"/v1/projects/{pid}/panoramas", headers=kh(key, **PL)).json()["sets"]] == [set_id]
    error_of(client.get(f"/v1/projects/{pid}/panoramas/{eds}", headers=kh(key, **PL)), 404, "not_found")
    error_of(client.get(f"/v1/projects/{pid}/panoramas", headers=kh(eds_key, **PL)), 404, "not_found")


def test_v1_panoramas_validation(client):
    owner, _, pid, set_id = _house(client)
    key = make_key(client, owner.session, ["projects:read"])
    url = f"/v1/projects/{pid}/panoramas/{set_id}"
    for wait_s in (99, 25.5, -1):
        body = error_of(client.get(url, params={"rev": 1, "wait_s": wait_s}, headers=kh(key, **PL)), 422, "validation_failed")
        assert body["data"]["fields"] == [{"field": "wait_s", "in": "query", "message": f"0 to {queue.STATUS_WAIT_MAX_S}"}]
        # The same answer as the session route's.
        session = client.get(f"/projects/{pid}/panoramas/{set_id}", params={"rev": 1, "wait_s": wait_s}, headers=owner.web)
        assert _without_request_id(body) == _without_request_id(session.json())
    # Not numbers at all: the shared envelope too.
    for params, field in (({"wait_s": "soon"}, "wait_s"), ({"rev": "latest"}, "rev")):
        body = error_of(client.get(url, params=params, headers=kh(key, **PL)), 422, "validation_failed")
        assert body["data"]["fields"][0]["field"] == field
    # The upper bound itself is allowed.
    assert client.get(url, params={"rev": 0, "wait_s": queue.STATUS_WAIT_MAX_S}, headers=kh(key, **PL)).status_code == 200


# --- the document, the SDK, the burst limit -------------------------------------------------------------


def test_v1_panoramas_documented():
    doc = json.loads(DOC.read_text(encoding="utf-8"))
    listed = doc["paths"]["/v1/projects/{project_id}/panoramas"]["get"]
    one = doc["paths"]["/v1/projects/{project_id}/panoramas/{set_id}"]["get"]
    assert listed["operationId"] == "projects_panoramas_list" and one["operationId"] == "projects_panoramas_get"
    for op, model in ((listed, "PanoramaSetList"), (one, "PanoramaSetState")):
        assert op["x-truebex-scope"] == "projects:read" and op["x-truebex-contract"] == "project-log/1.1"
        assert op["tags"] == ["projects"] and op["description"]
        assert op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == f"#/components/schemas/{model}"
        for code in ("401", "403", "404", "429"):
            assert op["responses"][code]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ErrorEnvelope"
    assert "422" in one["responses"]
    assert {p["name"] for p in one["parameters"]} == {"project_id", "set_id", "rev", "wait_s"}
    schemas = doc["components"]["schemas"]
    for name in ("PanoramaSet", "PanoramaSetList", "PanoramaSetState", "TileManifest", "TileView", "TileFace"):
        assert schemas[name]["description"], name
    assert set(schemas["PanoramaSet"]["required"]) == {"set_id", "rev", "at_seq", "views", "following", "mine", "updated_at"}
    assert "truebex-tiles/1" in schemas["TileManifest"]["description"] and "tiles_base" in schemas["TileManifest"]["required"]
    # The Python types name every key as the wire does (the generator renames some, e.g. schema → schema_).
    models = (ROOT / "sdks" / "python" / "truebex" / "models.py").read_text(encoding="utf-8")
    assert not re.findall(r"^    \w+_: ", models, re.M)

    ops = (ROOT / "sdks" / "python" / "truebex" / "_operations.py").read_text(encoding="utf-8")
    assert "def panoramas_list(self, project_id: str)" in ops and "def panoramas_get(self, project_id: str, set_id: str" in ops
    js = (ROOT / "sdks" / "js" / "src" / "operations.d.ts").read_text(encoding="utf-8")
    assert "panoramasList(" in js and "panoramasGet(" in js


def test_v1_panoramas_python_sdk(client, live_api):  # noqa: F811
    owner, _, pid, set_id = _house(client)
    key = make_key(client, owner.session, ["projects:read"])
    sys.path.insert(0, str(ROOT / "sdks" / "python"))
    try:
        import truebex

        c = truebex.Client(api_key=key["key"], base_url=live_api, max_retries=0)
        sets = c.projects.panoramas_list(pid)
        assert [s["set_id"] for s in sets["sets"]] == [set_id]
        state = c.projects.panoramas_get(pid, set_id, rev=1, wait_s=0.2)
        assert state["rev"] == 1 and state["manifest"]["schema"] == "truebex-tiles/1"
        with pytest.raises(truebex.TruebexError) as err:
            c.projects.panoramas_get(pid, set_id, wait_s=99)
        assert err.value.status == 422 and err.value.code == "validation_failed"
        with pytest.raises(truebex.TruebexError) as err:
            c.projects.panoramas_get(pid, hex32())
        assert err.value.status == 404 and err.value.code == "not_found"
    finally:
        sys.path.remove(str(ROOT / "sdks" / "python"))
        for name in [m for m in sys.modules if m == "truebex" or m.startswith("truebex.")]:
            del sys.modules[name]


def test_v1_panoramas_burst_limit(client, monkeypatch):
    owner, _, pid, set_id = _house(client)
    s = get_settings()
    monkeypatch.setattr(s, "api_key_burst", 2)
    monkeypatch.setattr(s, "api_key_per_minute", 1)
    key = make_key(client, owner.session, ["projects:read"])
    assert client.get(f"/v1/projects/{pid}/panoramas", headers=kh(key, **PL)).status_code == 200
    assert client.get(f"/v1/projects/{pid}/panoramas/{set_id}", headers=kh(key, **PL)).status_code == 200
    body = error_of(client.get(f"/v1/projects/{pid}/panoramas", headers=kh(key, **PL)), 429, "rate_limited")
    assert body["data"]["limit"] == "burst" and body["retry_after_s"] >= 1
    used = _usage(owner.email)
    assert used[LIST_ROUTE] == 1 and used[SET_ROUTE] == 1  # the refused call is not counted
    # The session route is not a key call: no burst limit, no metering.
    assert client.get(f"/projects/{pid}/panoramas", headers={**owner.web, **CONTRACT}).status_code == 200
