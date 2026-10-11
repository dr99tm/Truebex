"""The developer API's description and the SDKs generated from it (PF12):
`openapi/v1.json` is current, the SDKs' operation layer and types follow it,
and both SDKs work end to end against a live API."""

import json
import re
import socket
import subprocess
import sys
import threading
import time

import pytest

from .pf12_helpers import ALL_SCOPES, PL, ROOT, kh, make_key, node, sha
from .project_helpers import Person, delta_op, hex32

DOC = ROOT / "openapi" / "v1.json"


def _doc() -> dict:
    return json.loads(DOC.read_text(encoding="utf-8"))


def test_openapi_v1_document_current():
    sys.path.insert(0, str(ROOT / "server" / "scripts"))
    try:
        import export_openapi
    finally:
        sys.path.remove(str(ROOT / "server" / "scripts"))
    fresh = export_openapi.render(export_openapi.build())
    assert DOC.read_text(encoding="utf-8") == fresh, (
        "openapi/v1.json is out of date: run server\\.venv\\Scripts\\python.exe server\\scripts\\export_openapi.py --v1 "
        "then scripts\\gen-sdks.ps1"
    )


def test_openapi_v1_document_shape():
    doc = _doc()
    assert doc["openapi"].startswith("3.1") and doc["servers"] == [{"url": "https://api.truebex.com"}]
    ops = {(m, p): op for p, item in doc["paths"].items() for m, op in item.items()}
    # Every route group of the doc's design table.
    for path in ("/v1/projects", "/v1/projects/{project_id}/ops", "/v1/jobs", "/v1/uploads", "/v1/shares",
                 "/v1/webhooks", "/v1/webhooks/{endpoint_id}/deliveries/{delivery_id}/resend",
                 "/v1/webhooks/{endpoint_id}/secret/rotate", "/market/search", "/market/feeds/{feed_id}"):
        assert path in doc["paths"], path
    ids = [op["operationId"] for op in ops.values()]
    assert len(ids) == len(set(ids)) and all(re.fullmatch(r"[a-z]+_[a-z_]+", i) for i in ids)
    for (method, path), op in ops.items():
        scope = op.get("x-truebex-scope")
        assert scope is None or scope in ALL_SCOPES, (method, path)
        assert op["description"], (method, path)
        assert {"bearerKey": []} in op["security"], (method, path)
        assert "x-api-key" not in [p["name"].lower() for p in op.get("parameters", [])]
    assert ops[("get", "/market/search")]["x-truebex-auth"] == "optional"
    assert ops[("post", "/market/feeds")]["x-truebex-scope"] == "supplier:feed"
    # Every schema a document names is defined; no generated names leak through.
    text = json.dumps(doc)
    for ref in set(re.findall(r'"#/components/schemas/([^"]+)"', text)):
        assert ref in doc["components"]["schemas"], ref
    assert not [n for n in doc["components"]["schemas"] if "__" in n or n.startswith("Body_")]
    assert "HTTPValidationError" not in text


def test_openapi_contract_headers_match_the_routes(client):
    """The SDKs send each operation's `x-truebex-contract`; the routes echo the same."""
    doc = _doc()
    want = {op["operationId"].split("_")[0]: op.get("x-truebex-contract") for item in doc["paths"].values() for op in item.values()}
    owner = Person(client, "owner@example.com")
    key = make_key(client, owner.session, ALL_SCOPES)
    got = {
        "projects": client.get("/v1/projects", headers=kh(key)).headers["X-Truebex-Contract"],
        "jobs": client.get("/v1/jobs", headers=kh(key)).headers["X-Truebex-Contract"],
        "shares": client.get("/v1/shares", headers=kh(key)).headers["X-Truebex-Contract"],
        "market": client.get("/market/regions", headers=kh(key)).headers["X-Truebex-Contract"],
    }
    for group, header in got.items():
        assert want[group] == header, group
    assert want["uploads"] == got["shares"] and want["feeds"] == got["market"]


def test_sdk_operations_current():
    res = subprocess.run(
        [sys.executable, str(ROOT / "sdks" / "generate.py"), "--check"], capture_output=True, text=True, encoding="utf-8", timeout=120
    )
    assert res.returncode == 0, res.stderr


def test_sdk_types_cover_every_schema():
    """The MIT generators' output (models.py, schema.d.ts) names every schema of the document."""
    schemas = _doc()["components"]["schemas"]
    models = (ROOT / "sdks" / "python" / "truebex" / "models.py").read_text(encoding="utf-8")
    ts = (ROOT / "sdks" / "js" / "src" / "schema.d.ts").read_text(encoding="utf-8")
    for name in schemas:
        assert re.search(rf"^class {re.escape(name)}\(", models, re.M), f"models.py lacks {name}: run scripts\\gen-sdks.ps1"
        assert re.search(rf"^\s+{re.escape(name)}: \{{", ts, re.M), f"schema.d.ts lacks {name}: run scripts\\gen-sdks.ps1"
    for op in json.loads(json.dumps([o for item in _doc()["paths"].values() for o in item.values()])):
        assert f'{op["operationId"]}: {{' in ts, op["operationId"]


def test_sdk_packages_publishable():
    py = (ROOT / "sdks" / "python" / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "truebex"' in py and "dependencies = []" in py
    pkg = json.loads((ROOT / "sdks" / "js" / "package.json").read_text(encoding="utf-8"))
    assert pkg["name"] == "@truebex/sdk" and pkg["type"] == "module" and not pkg.get("dependencies")
    version = _doc()["info"]["version"]
    assert pkg["version"] == version and f'version = "{version}"' in py
    for readme in (ROOT / "sdks" / "python" / "README.md", ROOT / "sdks" / "js" / "README.md"):
        text = readme.read_text(encoding="utf-8")
        assert "verify" in text.lower() and "TRUEBEX_API_KEY" in text
        assert "tbx_live_" not in text.replace("tbx_live_…", ""), "no key in examples"


# --- end to end ------------------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def live_api(client):
    """The test app on a real port, so the SDKs speak HTTP to it."""
    import uvicorn

    from app.main import app

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 20
    while not server.started:
        assert time.time() < deadline, "the live API did not start"
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


def test_python_sdk_end_to_end(client, live_api):
    owner = Person(client, "owner@example.com")
    key = make_key(client, owner.session, ALL_SCOPES)
    sys.path.insert(0, str(ROOT / "sdks" / "python"))
    try:
        import truebex

        c = truebex.Client(api_key=key["key"], base_url=live_api, max_retries=0)
        assert "tbx_live" not in repr(c)
        account = c.account.get()
        assert account["key"]["scopes"] == ALL_SCOPES
        # The human test's line: a project with head_seq 0.
        project = c.projects.create(name="API House", doc_version=38)
        assert project["head_seq"] == 0 and project["name"] == "API House"
        pid = project["project_id"]
        assert [p["project_id"] for p in c.projects.list()["projects"]] == [pid]
        op = delta_op(owner.author_id, [hex32()])
        del op["author"], op["author_kind"]
        pushed = c.projects.push_ops(pid, replica_id=hex32(), ops=[op])
        assert pushed["head_seq"] == 1
        pulled = c.projects.pull_ops(pid, after=0)
        assert pulled["ops"][0]["author_kind"] == "agent"
        # A snapshot through the upload helper, then an export job.
        tbxp = b"TBXP" + b"\1" * 4096
        upload = c.upload("snapshot", [tbxp])
        assert upload["files"][0]["state"] == "complete"
        snap = c.projects.create_snapshot(
            pid, at_seq=1, doc_version=38, upload_id=upload["upload_id"], files={"tbxp": sha(tbxp), "tbxpack": None}
        )
        assert snap["at_seq"] == 1
        job = c.jobs.create(kind="pack", project_id=pid, at_seq=1, params={"items": ["sheets"]})
        assert job["state"] == "queued" and job["cost_units_estimate"] > 0
        assert c.jobs.get(job["job_id"])["job_id"] == job["job_id"]
        # Errors carry the envelope.
        with pytest.raises(truebex.TruebexError) as err:
            c.projects.delete(pid)
        assert err.value.status == 403 and err.value.code == "session_required" and err.value.request_id
        with pytest.raises(truebex.TruebexError) as err:
            c.projects.get("0" * 32)
        assert err.value.code == "not_found"
        # Webhooks: an endpoint and its secret.
        hook = c.webhooks.create(url="https://93.184.216.34/hook", events=["job.failed"])
        assert hook["secret"].startswith("whsec_")
        assert c.webhooks.list()["endpoints"][0]["endpoint_id"] == hook["endpoint_id"]
        # The marketplace with the key.
        assert "regions" in c.market.regions()
        # A wrong key.
        with pytest.raises(truebex.TruebexError) as err:
            truebex.Client(api_key="tbx_live_wrong", base_url=live_api, max_retries=0).account.ping()
        assert err.value.status == 401 and "tbx_live_wrong" not in str(err.value)
    finally:
        sys.path.remove(str(ROOT / "sdks" / "python"))
        for name in [m for m in sys.modules if m == "truebex" or m.startswith("truebex.")]:
            del sys.modules[name]


def test_js_sdk_end_to_end(client, live_api):
    exe = node()
    if not exe:
        pytest.skip("node is not installed")
    owner = Person(client, "owner@example.com")
    key = make_key(client, owner.session, ["projects:read", "projects:write"])
    op = delta_op(owner.author_id, [hex32()])
    del op["author"], op["author_kind"]
    script = f"""
import {{ Truebex, TruebexError }} from "./sdks/js/src/index.mjs";
const c = new Truebex({{ apiKey: {json.dumps(key["key"])}, baseUrl: {json.dumps(live_api)}, maxRetries: 0 }});
const out = {{}};
const project = await c.projects.create({{ name: "JS House", doc_version: 38 }});
out.head = project.head_seq;
out.pushed = (await c.projects.pushOps(project.project_id, {{ replica_id: {json.dumps(hex32())}, ops: [{json.dumps(op)}] }})).head_seq;
out.pulled = (await c.projects.pullOps(project.project_id, {{ after: 0 }})).ops.length;
try {{ await c.jobs.create({{ kind: "pack", project_id: project.project_id, at_seq: 1, params: {{ items: ["sheets"] }} }}); }}
catch (e) {{ out.error = [e instanceof TruebexError, e.status, e.code, e.data.needed]; }}
out.leak = JSON.stringify(c).includes("tbx_live");
console.log(JSON.stringify(out));
"""
    res = subprocess.run([exe, "--input-type=module", "-e", script], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout) == {"head": 0, "pushed": 1, "pulled": 1, "error": [True, 403, "forbidden", "jobs:write"], "leak": False}
    assert client.get("/v1/projects", headers=kh(key, **PL)).json()["projects"][0]["name"] == "JS House"
