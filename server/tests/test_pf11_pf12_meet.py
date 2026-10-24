"""Where PF11 (analysis jobs on PF6's queue, the AI proxy) meets PF12 (API
keys with scopes, /v1, webhooks): an agent with a key uploads an analysis
input, submits a wind job through /v1/jobs, is told when it finished by a
webhook and reads its results; the scopes hold on the analysis catalogue;
the AI proxy still answers the app only. The SDK submits an analysis that
names no project (PF11 makes `project_id` optional for analysis kinds)."""

import json
import sys

import httpx
import pytest

from app.database import SessionLocal
from app.webhooks import delivery, events, urls

from .analysis_helpers import entities, octahedron_stl, put_inputs, sha, wind_body
from .licence_helpers import error_of
from .pf12_helpers import ROOT, RJ, SB, kh, make_key
from .project_helpers import Person, hex32
from .render_helpers import admin, claimed, issue_worker
from .test_analysis import ANALYSIS_KINDS, _bins, _complete, _fixture_result, _send_outputs
from .test_pf12_openapi_sdks import live_api  # noqa: F401  (the fixture)


@pytest.fixture()
def receiver(monkeypatch):
    got: list[httpx.Request] = []
    monkeypatch.setattr(urls, "resolve", lambda host: ["93.184.216.34"])
    monkeypatch.setattr(
        delivery, "client_factory", lambda: httpx.Client(transport=httpx.MockTransport(lambda r: got.append(r) or httpx.Response(200)))
    )
    return got


def _v1_upload(client, key: dict, data: bytes) -> None:
    opened = client.post(
        "/v1/uploads",
        json={"purpose": "job-input", "files": [{"sha256": sha(data), "bytes": len(data), "content_type": "application/octet-stream"}]},
        headers=kh(key, **SB),
    )
    assert opened.status_code == 201, opened.text
    put = client.put(
        f"/v1/uploads/{opened.json()['upload_id']}/files/{sha(data)}/parts/0",
        content=data,
        headers=kh(key, **SB, **{"X-Part-Sha256": sha(data), "Content-Type": "application/octet-stream"}),
    )
    assert put.status_code == 204, put.text


def test_api_key_runs_an_analysis_job_with_a_webhook(client, receiver):
    a = Person(client, "a@example.com")  # a Pro trial: holds analysis.reports
    token = issue_worker(client, admin(client), name="cpu-eu-01", kinds=ANALYSIS_KINDS, cls="cpu-8")
    key = make_key(client, a.session, ["projects:read", "jobs:write", "webhooks:manage"])
    hooked = client.post(
        "/v1/webhooks", json={"url": "https://hooks.example.com/truebex", "events": ["job.succeeded", "job.failed"]}, headers=kh(key)
    )
    assert hooked.status_code == 201, hooked.text

    # The key uploads the geometry (purpose job-input needs jobs:write) and submits through /v1.
    stl = octahedron_stl()
    _v1_upload(client, key, stl)
    _v1_upload(client, key, entities())  # render-jobs 1.2.0: a wind job's entity ids are required
    res = client.post("/v1/jobs", json=wind_body(stl), headers=kh(key, **RJ, **{"Idempotency-Key": hex32()}))
    assert res.status_code == 201, res.text
    rec = res.json()
    assert rec["kind"] == "wind" and rec["class"] == "cpu-8" and rec["state"] == "queued"
    assert rec["cost_units_estimate"] > 0

    # A cpu-8 worker runs it; the account's endpoint hears job.succeeded.
    c = claimed(client, token, worker_id="cpu-eu-01", kinds=ANALYSIS_KINDS)
    assert c["job"]["job_id"] == rec["job_id"] and c["job"]["profile"]
    _send_outputs(client, token, c, _bins())
    done = _complete(client, token, c, _fixture_result(c))
    assert done.status_code == 200, done.text
    with SessionLocal() as db:
        events.flush_ops(db)
        assert delivery.deliver_due(db) == 1
    body = json.loads(receiver[0].content)
    assert body["type"] == "job.succeeded"
    assert body["data"]["job_id"] == rec["job_id"] and body["data"]["kind"] == "wind" and body["data"]["class"] == "cpu-8"

    # The key reads the §6.3 results with signed file URLs, and the month's use by kind.
    out = client.get(f"/v1/jobs/{rec['job_id']}/output", headers=kh(key, **RJ))
    assert out.status_code == 200, out.text
    assert out.json()["schema"] == "truebex-analysis/1" and set(out.json()["urls"]) == {sha(b) for b in _bins()}
    usage = client.get("/v1/jobs/usage", headers=kh(key, **RJ)).json()
    assert usage["by_kind"]["wind"] > 0


def test_scopes_hold_on_analysis_routes(client):
    a = Person(client, "a@example.com")
    stl = octahedron_stl()
    put_inputs(client, a.dev, stl, entities())
    reader = make_key(client, a.session, ["projects:read"])
    hooks_only = make_key(client, a.session, ["webhooks:manage"])

    # Submitting an analysis job needs jobs:write, on /v1 and on the contract route alike.
    for path in ("/v1/jobs", "/jobs"):
        err = error_of(client.post(path, json=wind_body(stl), headers=kh(reader, **RJ, **{"Idempotency-Key": hex32()})), 403, "forbidden")
        assert err["data"]["needed"] == "jobs:write"
    # The analysis catalogue is a read: projects:read.
    cat = client.get("/analysis/catalogue", headers=kh(reader, **RJ))
    assert cat.status_code == 200, cat.text
    assert {k["kind"] for k in cat.json()["kinds"]} >= {"wind", "energy", "acoustics"}
    err = error_of(client.get("/analysis/catalogue", headers=kh(hooks_only, **RJ)), 403, "forbidden")
    assert err["data"]["needed"] == "projects:read"


def test_ai_proxy_still_refuses_api_keys(client):
    a = Person(client, "a@example.com")
    key = make_key(client, a.session, ["projects:read", "jobs:write"])
    headers = kh(key, **{"X-Truebex-Contract": "ai-proxy/1.1"})
    error_of(client.get("/ai/models", headers=headers), 403, "forbidden")
    error_of(client.get("/ai/balance", headers=headers), 403, "forbidden")


def test_python_sdk_submits_an_analysis_without_a_project(client, live_api):  # noqa: F811
    a = Person(client, "a@example.com")
    key = make_key(client, a.session, ["projects:read", "jobs:write"])
    sys.path.insert(0, str(ROOT / "sdks" / "python"))
    try:
        import truebex

        c = truebex.Client(api_key=key["key"], base_url=live_api, max_retries=0)
        stl = octahedron_stl()
        assert {f["state"] for f in c.upload("job-input", [stl, entities()])["files"]} == {"complete"}
        body = wind_body(stl)
        job = c.jobs.create(kind="wind", inputs=body["inputs"], params=body["params"])
        assert job["kind"] == "wind" and job["project_id"] is None and job["state"] == "queued"
        assert [j["job_id"] for j in c.jobs.list(kind="wind")["jobs"]] == [job["job_id"]]
        # A render kind still needs its project: the contract's 422 comes back as the SDK's error.
        try:
            c.jobs.create(kind="panorama", views=[hex32()])
            raise AssertionError("a panorama without a project was accepted")
        except truebex.TruebexError as err:
            assert err.status == 422 and err.code == "validation_failed"
    finally:
        sys.path.remove(str(ROOT / "sdks" / "python"))
        for name in [m for m in sys.modules if m == "truebex" or m.startswith("truebex.")]:
            del sys.modules[name]
