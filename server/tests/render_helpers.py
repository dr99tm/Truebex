"""Shared helpers for the render tests (PF6, contract render-jobs 1.1.0; the header 1.2 since PF11c, 1.3 since PF6c)."""

import copy
import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from app.database import SessionLocal
from app.models import Subscription

from .conftest import make_admin, signup
from .project_helpers import UPLOADS, Person, create, delta_op, hex32, pushed, snapshot

RJ = {"X-Truebex-Contract": "render-jobs/1.3"}  # what the app sends since CL4 (PF6c)
# The app's own set (CL3, render-jobs 1.1.0 §9), copied byte for byte.
FIX = Path(__file__).parent / "contracts" / "render-jobs"
# PF6's and PF11's stand-ins the app has no copy of (claim.json, the wind result).
RENDER_FIXTURES = Path(__file__).parent / "fixtures" / "render"
PROJECT_LOG = Path(__file__).parent / "contracts" / "project-log"
# CL3's fixtures render PR3's PR3-pano-rooms.tbxp: its project id, its three
# saved views in job-panorama.json's order, and the ids job-tiles.json's one
# operation touched (it moves the living room's west wall 300 mm west).
APP_PROJECT = "fd1f65c522298d6fbd318103c6601118"
VIEW_BEDROOM = "ecaf16d70fa5862cbba8f2288b9fd593"
VIEW_ENTRY = "8388104cbff98d2dba07fd23c19c83b5"
VIEW_LIVING = "aee49319c0d48a7a953f247b52c948be"
VIEWS = [VIEW_BEDROOM, VIEW_ENTRY, VIEW_LIVING]
MOVED = [
    "1ef08768492a8926b64f9592c0667bf9",
    "3b9fb6803c4c88a7958702688193438f",
    "4669090c15ee8367a7376ac885195872",
    "69c372acae5b8ad2a9d7979cc2594196",
    "6b5a6295be988227a75da6af952373f5",
    "902423107cab8a10846b22c90ba51415",
    "a4efa2e373a68a6e918a7473a82d4557",
    "b0bd1a39d86a8ebf9a45ff5235312966",
    "d0ccc0cd923987eb8d15dbcfd72832b3",
]


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


def project(client, person: Person, ops: int = 2, *, project_id: str | None = None) -> tuple[str, int]:
    """A project with the fixture snapshot at 0 and `ops` operations: (id, head).
    `project_id` (e.g. APP_PROJECT) is the id the platform gives it."""
    if project_id is None:
        pid = create(client, person.dev)["project_id"]
    else:
        with mock.patch("app.projects.service.uuid7_hex", lambda: project_id):
            pid = create(client, person.dev)["project_id"]
        assert pid == project_id
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
        body.setdefault("views", list(VIEWS))
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


def finish(client, token: str, c: dict, name: str = "manifest-panorama.json", wall_s: float = 84.2, at: dict | None = None) -> dict:
    """Upload the fixture manifest's rendered tiles and complete the claim. `at`
    gets `at["complete"]`, the time.monotonic() just before the complete: the
    call that wakes a read waiting on the job (the uploads before it wake none)."""
    m = fixture_manifest(name, c)
    upload_outputs(client, token, c, rendered_tiles(m))
    if at is not None:
        at["complete"] = time.monotonic()
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
