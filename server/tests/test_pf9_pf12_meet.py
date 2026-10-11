"""Where PF9 (the mobile web client: a snapshot's project digest, members'
author ids, a project's followed panorama sets) meets PF12 (API keys, the /v1
mirror, openapi/v1.json and the SDKs and /developers/ reference generated from
it): a key registers a snapshot with its digest through /v1 and reads it back;
the document, both SDKs' types and the reference name `files.digest` and the
members' `author_id`; the panorama routes stay off /v1 and refuse a key (a
PF12 carry-over)."""

import json
import re
import sys

import pytest

from .licence_helpers import error_of
from .pf12_helpers import PL, ROOT, SB, kh, make_key, sha
from .project_helpers import FIXTURES, Person, hex32
from .test_mobile import _followed_set, digest_bytes
from .test_pf12_openapi_sdks import live_api  # noqa: F401  (the fixture)
from .test_site_pf13 import OUT, Doc, built  # noqa: F401  (built is a fixture)

DOC = ROOT / "openapi" / "v1.json"


def _doc() -> dict:
    return json.loads(DOC.read_text(encoding="utf-8"))


def _v1_snapshot(client, key: dict, pid: str, at_seq: int, digest: bytes | None):
    """Upload through /v1/uploads (purpose snapshot) and register through /v1."""
    tbxp = (FIXTURES / "snapshot-0000.tbxp").read_bytes()
    files = [tbxp] + ([digest] if digest is not None else [])
    opened = client.post(
        "/v1/uploads",
        json={
            "purpose": "snapshot",
            "files": [{"sha256": sha(f), "bytes": len(f), "content_type": "application/octet-stream"} for f in files],
        },
        headers=kh(key, **SB),
    )
    assert opened.status_code == 201, opened.text
    upload_id = opened.json()["upload_id"]
    for f in files:
        put = client.put(
            f"/v1/uploads/{upload_id}/files/{sha(f)}/parts/0",
            content=f,
            headers=kh(key, **SB, **{"X-Part-Sha256": sha(f), "Content-Type": "application/octet-stream"}),
        )
        assert put.status_code == 204, put.text
    body = {
        "at_seq": at_seq,
        "doc_version": 38,
        "upload_id": upload_id,
        "files": {"tbxp": sha(tbxp), "tbxpack": None, "digest": sha(digest) if digest is not None else None},
    }
    return client.post(f"/v1/projects/{pid}/snapshots", json=body, headers=kh(key, **PL, **{"Idempotency-Key": hex32()}))


def test_v1_snapshot_with_digest_round_trips(client):
    owner = Person(client, "owner@example.com")
    key = make_key(client, owner.session, ["projects:read", "projects:write"])
    auth = kh(key, **PL)
    pid = client.post("/v1/projects", json={"name": "API House", "doc_version": 38}, headers=auth).json()["project_id"]

    digest = digest_bytes()
    res = _v1_snapshot(client, key, pid, 0, digest)
    assert res.status_code == 201, res.text
    files = res.json()["files"]
    assert files["digest"]["sha256"] == sha(digest) and files["digest"]["bytes"] == len(digest)

    # The key reads it back as the app's own route answers it, and the URL serves the digest.
    latest = client.get(f"/v1/projects/{pid}/snapshots/latest", headers=auth)
    assert latest.status_code == 200, latest.text
    via_key = latest.json()["files"]["digest"]
    via_app = client.get(f"/projects/{pid}/snapshots/latest", headers=owner.dev).json()["files"]["digest"]
    assert (via_key["sha256"], via_key["bytes"]) == (via_app["sha256"], via_app["bytes"]) == (sha(digest), len(digest))
    got = client.get(via_key["url"].replace("http://testserver", ""))
    assert got.status_code == 200 and got.content == digest
    assert json.loads(got.content)["schema"] == "truebex-project-digest/1"

    # Without one, `digest: null`; a malformed one is the contract's 422 on files.digest.
    plain = _v1_snapshot(client, key, pid, 0, None)
    assert plain.status_code == 201 and plain.json()["files"]["digest"] is None
    bad = _v1_snapshot(client, key, pid, 0, b"not json")
    assert error_of(bad, 422, "validation_failed")["data"]["fields"][0]["field"] == "files.digest"

    # The members PF9 names a conflict's winner from carry their author ids through /v1 too.
    members = client.get(f"/v1/projects/{pid}/members", headers=auth).json()["members"]
    assert members[0]["author_id"] == owner.author_id


def test_v1_document_and_sdks_name_the_digest():
    schemas = _doc()["components"]["schemas"]
    out = schemas["SnapshotFiles"]
    assert out["properties"]["digest"]["anyOf"] == [{"$ref": "#/components/schemas/SnapshotFileUrl"}, {"type": "null"}]
    assert "digest" in out["required"] and "digest" in out["description"]
    assert "digest" in schemas["SnapshotFilesIn"]["properties"] and "digest" in schemas["SnapshotFilesIn"]["description"]
    assert "author_id" in schemas["Member"]["properties"]

    models = (ROOT / "sdks" / "python" / "truebex" / "models.py").read_text(encoding="utf-8")
    ts = (ROOT / "sdks" / "js" / "src" / "schema.d.ts").read_text(encoding="utf-8")
    for name, field in (("SnapshotFiles", "digest"), ("SnapshotFilesIn", "digest"), ("Member", "author_id")):
        py = re.search(rf"^class {name}\(.*?(?=^class |\Z)", models, re.M | re.S)
        assert py and re.search(rf"^    {field}: ", py.group(0), re.M), f"models.py {name} lacks {field}"
        js = re.search(rf"^( +){name}: \{{.*?^\1\}}", ts, re.M | re.S)
        assert js and re.search(rf"^\s+{field}\??: ", js.group(0), re.M), f"schema.d.ts {name} lacks {field}"


def test_python_sdk_registers_a_snapshot_with_a_digest(client, live_api):  # noqa: F811
    owner = Person(client, "owner@example.com")
    key = make_key(client, owner.session, ["projects:read", "projects:write"])
    tbxp = (FIXTURES / "snapshot-0000.tbxp").read_bytes()
    digest = digest_bytes()
    sys.path.insert(0, str(ROOT / "sdks" / "python"))
    try:
        import truebex

        c = truebex.Client(api_key=key["key"], base_url=live_api, max_retries=0)
        pid = c.projects.create(name="SDK House", doc_version=38)["project_id"]
        upload = c.upload("snapshot", [tbxp, digest])
        snap = c.projects.create_snapshot(
            pid, at_seq=0, doc_version=38, upload_id=upload["upload_id"],
            files={"tbxp": sha(tbxp), "tbxpack": None, "digest": sha(digest)},
        )
        assert snap["files"]["digest"]["sha256"] == sha(digest)
        assert c.projects.latest_snapshot(pid)["files"]["digest"]["bytes"] == len(digest)
        assert c.projects.list_members(pid)["members"][0]["author_id"] == owner.author_id
    finally:
        sys.path.remove(str(ROOT / "sdks" / "python"))
        for name in [m for m in sys.modules if m == "truebex" or m.startswith("truebex.")]:
            del sys.modules[name]


def test_panoramas_stay_off_v1(client):
    """PF9's panorama routes take a session or a device token; /v1 has no mirror yet (carry-over)."""
    owner = Person(client, "owner@example.com")
    key = make_key(client, owner.session, ["projects:read", "projects:write"])
    pid = client.post("/v1/projects", json={"name": "API House", "doc_version": 38}, headers=kh(key, **PL)).json()["project_id"]
    set_id = _followed_set(owner.user_id, pid)

    sets = client.get(f"/projects/{pid}/panoramas", headers=owner.web)
    assert sets.status_code == 200 and [s["set_id"] for s in sets.json()["sets"]] == [set_id]
    error_of(client.get(f"/projects/{pid}/panoramas", headers=kh(key, **PL)), 401, "unauthenticated")
    error_of(client.get(f"/projects/{pid}/panoramas/{set_id}", headers=kh(key, **PL)), 401, "unauthenticated")
    assert client.get(f"/v1/projects/{pid}/panoramas", headers=kh(key, **PL)).status_code in (404, 405)
    assert not [p for p in _doc()["paths"] if "panorama" in p]


def test_site_reference_names_the_digest(built):  # noqa: F811
    page = Doc((OUT / "developers" / "projects" / "index.html").read_text(encoding="utf-8"))
    for op in ("projects_create_snapshot", "projects_latest_snapshot"):
        section = page.all("section", data_operation=op)[0]
        assert "digest" in page.text(section), op
