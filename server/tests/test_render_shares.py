"""Where PF6 meets PF5: a share whose panorama follows a render set.

PF6's own tests read the live share through a stand-in resolver; these go
through PF5's real shares (5.4, 5.5, 5.10, `/view/{slug}`, revoke): the
manifest rule for `live_job_id`, `GET /s/{slug}/live` on a published share, the
share page's CSP for the tiles' origin, and the share's end ending the live
view. `live_job_id` and `/s/{slug}/live` are PF6's share-bundle MINOR proposal.
"""

import copy
import threading

import pytest

from app.config import get_settings
from app.projects import waiters
from app.render import live, pools

from .licence_helpers import error_of
from .project_helpers import Person
from .render_helpers import WALL, admin, claimed, finish, issue_worker, project, push_touch, rj, submitted
from .share_helpers import CONTRACT, create, dev, house, published, web

LIVE_BUNDLE = "6" * 32
PLAIN_BUNDLE = "7" * 32


@pytest.fixture(autouse=True)
def _clean_state():
    waiters.reset()
    pools.DESIRED.clear()
    live.set_share_resolver(None)  # PF5's shares.service.by_slug
    yield
    waiters.reset()


def live_house(job_id: str, bundle_id: str = LIVE_BUNDLE) -> dict:
    m = copy.deepcopy(house(bundle_id))
    m["panoramas"][0]["live_job_id"] = job_id  # p1, the start panorama
    return m


@pytest.fixture()
def followed(client):
    """A Pro-trial designer whose followed panorama set has rendered once."""
    a = Person(client, "a@example.com")
    pid, head = project(client, a)
    token = issue_worker(client, admin(client))
    follow = submitted(client, rj(a), project_id=pid, at_seq=head, follow=True)
    finish(client, token, claimed(client, token))
    return {"a": a, "pid": pid, "token": token, "job_id": follow["job_id"]}


def test_share_manifest_live_job_id_rule(client, followed):
    a = followed["a"]
    for bad in ("not-a-job", 7, "A" * 32):
        res = create(client, a.token, live_house(bad))
        err = error_of(res, 422, "manifest_invalid")
        assert [(e["path"], e["rule"]) for e in err["data"]["errors"]] == [("panoramas[0].live_job_id", "type")], bad
    res = create(client, a.token, live_house(followed["job_id"]))
    assert res.status_code == 201, res.text


def test_published_share_follows_the_set(client, followed, monkeypatch):
    a, token, pid = followed["a"], followed["token"], followed["pid"]
    monkeypatch.setattr(get_settings(), "tiles_base_url", "https://cdn.example.com/tiles")
    share = published(client, a.token, live_house(followed["job_id"]))
    slug = share["slug"]

    # The page data carries the panorama's live_job_id to the viewer.
    data = client.get(f"/s/{slug}", headers=CONTRACT).json()
    assert data["manifest"]["panoramas"][0]["live_job_id"] == followed["job_id"]
    assert "live_job_id" not in data["manifest"]["panoramas"][1]

    # The live read resolves the share through PF5 and serves the set.
    first = client.get(f"/s/{slug}/live", params={"panorama": "p1"}, headers=CONTRACT)
    assert first.status_code == 200, first.text
    state = first.json()
    assert state["following"] is True and state["job_id"] == followed["job_id"]
    assert state["manifest"]["tiles_base"] == "https://cdn.example.com/tiles"
    assert state["manifest"]["faces_rendered"] == 6
    error_of(client.get(f"/s/{slug}/live", params={"panorama": "p2"}, headers=CONTRACT), 404, "not_found")

    # The share page lets the viewer load tiles from the CDN's origin.
    csp = client.get(f"/view/{slug}").headers["Content-Security-Policy"]
    img = next(d for d in csp.split("; ") if d.startswith("img-src "))
    assert "https://cdn.example.com" in img.split()
    assert "cdn.example.com" not in csp.replace(img, "")

    # An edit re-renders two faces; a waiting viewer sees the new rev.
    got: dict = {}

    def wait() -> None:
        got["res"] = client.get(f"/s/{slug}/live", params={"rev": state["rev"], "wait_s": 10}, headers=CONTRACT)

    t = threading.Thread(target=wait)
    t.start()
    push_touch(client, a, pid, [WALL])
    finish(client, token, claimed(client, token), "manifest-tiles.json")
    t.join(10)
    moved = got["res"].json()
    assert moved["rev"] > state["rev"] and moved["manifest"]["faces_rendered"] == 2

    # Ending the share ends its live view (410, as the share page answers).
    assert client.delete(f"/shares/{share['share_id']}", headers=web(a.session)).status_code == 200
    err = error_of(client.get(f"/s/{slug}/live", headers=CONTRACT), 410, "share_gone")
    assert err["data"]["state"] == "revoked"


def test_plain_share_csp_and_another_accounts_set(client, followed, monkeypatch):
    monkeypatch.setattr(get_settings(), "tiles_base_url", "https://cdn.example.com/tiles")
    a = followed["a"]
    plain = published(client, a.token, house(PLAIN_BUNDLE))
    assert "cdn.example.com" not in client.get(f"/view/{plain['slug']}").headers["Content-Security-Policy"]
    error_of(client.get(f"/s/{plain['slug']}/live", headers=CONTRACT), 404, "not_found")

    # Someone else's share cannot show this designer's set.
    b = Person(client, "b@example.com")
    other = published(client, b.token, live_house(followed["job_id"]))
    error_of(client.get(f"/s/{other['slug']}/live", headers=CONTRACT), 404, "not_found")
    assert client.get(f"/s/{other['slug']}", headers=dev(b.token)).status_code == 200
