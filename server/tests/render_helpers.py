"""Shared helpers for the render tests (PF6, contract render-jobs)."""

import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.database import SessionLocal
from app.models import Subscription

from .conftest import make_admin, signup
from .project_helpers import UPLOADS, Person, create, delta_op, hex32, pushed, snapshot

RJ = {"X-Truebex-Contract": "render-jobs/1.0"}
FIX = Path(__file__).parent / "contracts" / "render-jobs"
PROJECT_LOG = Path(__file__).parent / "contracts" / "project-log"
VIEW = "0199c6a2e00070058000000000000001"  # the fixtures' "Living room"
WALL = "0199c6a2e00070018000000000000001"


def rj(person_or_headers) -> dict:
    """Render-jobs headers for a Person's device, or for session headers."""
    if isinstance(person_or_headers, Person):
        return {"Authorization": f"Bearer {person_or_headers.token}", **RJ}
    return {**person_or_headers, **RJ}


def wk(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", **RJ}


def admin(client, email: str = "admin@example.com") -> dict:
    headers = signup(client, email)
    make_admin(email)
    return headers


def issue_worker(client, admin_headers: dict, name: str = "pc-rtx", kinds=("panorama", "tiles", "pack"), cls: str = "gpu-std") -> str:
    res = client.post("/admin/workers", json={"name": name, "kinds": list(kinds), "class": cls}, headers=admin_headers)
    assert res.status_code == 201, res.text
    return res.json()["token"]


def project(client, person: Person, ops: int = 2) -> tuple[str, int]:
    """A project with the fixture snapshot at 0 and `ops` operations: (id, head)."""
    pid = create(client, person.dev)["project_id"]
    tbxp = (PROJECT_LOG / "snapshot-0000.tbxp").read_bytes()
    res = snapshot(client, person.dev, pid, 0, tbxp)
    assert res.status_code == 201, res.text
    head = 0
    for i in range(ops):
        head = pushed(client, person.dev, pid, person.replica, [delta_op(person.author_id, [hex32()], base_seq=head)])["head_seq"]
    return pid, head


def push_touch(client, person: Person, pid: str, touched: list[str], *, delta_format: str = "o5/38") -> int:
    head = client.get(f"/projects/{pid}", headers=person.dev).json()["head_seq"]
    op = delta_op(person.author_id, touched, base_seq=head)
    op["delta_format"] = delta_format
    return pushed(client, person.dev, pid, person.replica, [op])["head_seq"]


def submit(client, headers: dict, **body):
    body.setdefault("kind", "panorama")
    if body["kind"] in ("panorama", "tiles"):
        body.setdefault("views", [VIEW])
    return client.post("/jobs", json=body, headers={**headers, "Idempotency-Key": hex32()})


def submitted(client, headers: dict, **body) -> dict:
    res = submit(client, headers, **body)
    assert res.status_code == 201, res.text
    return res.json()


def claim(client, token: str, *, worker_id: str = "pc-rtx", kinds=("panorama", "tiles", "pack"), doc_version_max: int = 38, wait_s: float = 0):
    body = {"worker_id": worker_id, "kinds": list(kinds), "app_version": "1.1.0", "doc_version_max": doc_version_max, "wait_s": wait_s}
    return client.post("/workers/claim", json=body, headers=wk(token))


def claimed(client, token: str, **kw) -> dict:
    res = claim(client, token, **kw)
    assert res.status_code == 200, res.text
    return res.json()


def heartbeat(client, token: str, c: dict, progress: float = 0.5, message: str = "face e"):
    return client.post(
        f"/workers/jobs/{c['job']['job_id']}/heartbeat",
        json={"lease_id": c["lease_id"], "progress": progress, "message": message},
        headers=wk(token),
    )


def fixture_manifest(name: str, c: dict) -> dict:
    m = copy.deepcopy(json.loads((FIX / name).read_text(encoding="utf-8")))
    job = c["job"]
    m["job_id"] = job["job_id"]
    m["project_id"] = job["project_id"]
    m["at_seq"] = job["at_seq"]
    return m


def tile_bytes(sha: str) -> bytes:
    return (FIX / "tiles" / f"{sha}.jpg").read_bytes()


def rendered_tiles(m: dict) -> list[str]:
    out = []
    for v in m["views"]:
        for face in v["faces"].values():
            if face["rendered"]:
                out += [s for row in face["tiles"] for s in row]
    return list(dict.fromkeys(out))


def upload_outputs(client, token: str, c: dict, shas: list[str]) -> dict:
    """Declare the tiles into the claim's job-output session and send them."""
    files = [{"sha256": s, "bytes": len(tile_bytes(s)), "content_type": "image/jpeg"} for s in shas]
    res = client.post(
        "/uploads",
        json={"purpose": "job-output", "upload_id": c["output_upload"]["upload_id"], "files": files},
        headers={"Authorization": f"Bearer {token}", **UPLOADS},
    )
    assert res.status_code == 201, res.text
    opened = res.json()
    for state in opened["files"]:
        if state["state"] == "present":
            continue
        data = tile_bytes(state["sha256"])
        sent = client.put(
            f"/uploads/{opened['upload_id']}/files/{state['sha256']}/parts/0",
            content=data,
            headers={
                "Authorization": f"Bearer {token}",
                **UPLOADS,
                "Content-Type": "application/octet-stream",
                "X-Part-Sha256": hashlib.sha256(data).hexdigest(),
            },
        )
        assert sent.status_code == 204, sent.text
    return opened


def complete(client, token: str, c: dict, manifest: dict, wall_s: float = 84.2, cls: str = "gpu-std"):
    return client.post(
        f"/workers/jobs/{c['job']['job_id']}/complete",
        json={"lease_id": c["lease_id"], "output": manifest, "usage": {"wall_s": wall_s, "class": cls}},
        headers=wk(token),
    )


def finish(client, token: str, c: dict, name: str = "manifest-panorama.json", wall_s: float = 84.2) -> dict:
    """Upload the fixture manifest's rendered tiles and complete the claim."""
    m = fixture_manifest(name, c)
    upload_outputs(client, token, c, rendered_tiles(m))
    res = complete(client, token, c, m, wall_s=wall_s)
    assert res.status_code == 200, res.text
    return res.json()


def job(client, headers: dict, job_id: str) -> dict:
    res = client.get(f"/jobs/{job_id}", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def studio(user_id: int, currency: str = "GBP") -> None:
    """A live Studio subscription (Studio has overage)."""
    with SessionLocal() as db:
        db.add(
            Subscription(
                user_id=user_id, plan="studio", provider="paddle", status="active", currency=currency,
                current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
                provider_customer_id="ctm_test", provider_subscription_id=f"sub_{user_id}", interval="month", seats=1,
            )
        )
        db.commit()
