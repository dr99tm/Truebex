"""The Android app's server side (PF10): the doc's three pytest names first —
the light clients' OpenAPI document is current, an Android Google ID token
(minted for the Web client id) signs in, presence as `client: "android"` —
then what keeps the two generated clients honest: they were generated from the
current document, and the real routes answer exactly the shapes it describes.
The build checks of the Android project that need no Flutter SDK (the store
listing, the mobile gate script, the lint ignore) are at the end; the Flutter
tests themselves run in scripts/verify-mobile.ps1."""

import hashlib
import json
import re
import struct
from pathlib import Path

import pytest
from pydantic import BaseModel

from app.mobile import clients
from app.projects import presence, waiters

from .licence_helpers import error_of
from .project_helpers import (
    CONTRACT,
    FIXTURES,
    Person,
    action_op,
    create,
    delta_op,
    hex32,
    invite_and_accept,
)
from .test_mobile import _followed_set, digest_bytes, snapshot_with_digest

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "openapi" / "clients.json"
GEN = ROOT / "mobile" / "android" / "lib" / "api" / "gen"
DTS = ROOT / "src" / "lib" / "api-clients.d.ts"
APP = ROOT / "mobile" / "android"
STORE = APP / "store"

# The answers the project-log, panorama and account models describe in full:
# every key the route sends must be named (the marketplace models name only
# what the clients read).
COMPLETE = {
    clients.ProjectRecord, clients.ProjectList, clients.OpenProject, clients.Member, clients.MemberList,
    clients.ProjectOwner, clients.ProjectQuota, clients.SnapshotSummary, clients.Snapshot, clients.SnapshotFiles,
    clients.SnapshotFile, clients.Operation, clients.OperationAction, clients.PushAnswer, clients.PushResult,
    clients.PullPage, clients.Presence, clients.PresenceView, clients.PresenceAnswer, clients.PresenceList,
    clients.PanoramaSet, clients.PanoramaSets, clients.SetState,
}


@pytest.fixture(autouse=True)
def _clean_project_state():
    presence.reset()
    waiters.reset()
    yield
    presence.reset()
    waiters.reset()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _strict(value, where: str = "answer") -> None:
    """No key the document does not name, anywhere inside a complete model."""
    if isinstance(value, BaseModel):
        if type(value) in COMPLETE:
            assert not value.model_extra, f"{where} ({type(value).__name__}) has keys the document lacks: {sorted(value.model_extra)}"
        for name in type(value).model_fields:
            _strict(getattr(value, name), f"{where}.{name}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _strict(item, f"{where}[{i}]")


def shaped(res, model: type[BaseModel], status: int = 200):
    assert res.status_code == status, res.text
    parsed = model.model_validate(res.json())
    _strict(parsed, model.__name__)
    return parsed


# --- the doc's Tests table ------------------------------------------------------------------------


def test_openapi_clients_document_current():
    from scripts import export_openapi

    fresh = export_openapi.render(export_openapi.build_clients())
    assert DOC.read_text(encoding="utf-8") == fresh, "openapi/clients.json is out of date: run scripts/gen-clients.ps1"
    doc = json.loads(fresh)
    ops = {(m, p): op for p, item in doc["paths"].items() for m, op in item.items()}
    assert set(ops) == set(clients.ROUTES)
    for (method, path), (op_id, contract, answer, _, auth) in clients.ROUTES.items():
        op = ops[(method, path)]
        assert op["operationId"] == op_id
        assert op.get("x-truebex-contract") == contract
        status = next(s for s in op["responses"] if s != "default")
        assert op["responses"][status]["content"]["application/json"]["schema"]["$ref"].endswith("/" + answer.__name__)
        assert op["responses"]["default"]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorEnvelope")
        assert (op["security"] == [{"session": []}]) == (auth == "session")
    # 5.6 reads its body itself: the document names it.
    push = ops[("post", "/projects/{project_id}/ops")]
    assert push["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("/PushIn")
    # The script's own check agrees (the CLI the gate script runs).
    assert export_openapi.main(["--clients", "--check"]) == 0


def test_android_google_token_audience(client, monkeypatch):
    """An ID token from Credential Manager, requested with the Web client id as the
    server client id, has that id as its audience: /auth/google takes it unchanged."""
    from google.oauth2 import id_token

    from app.config import get_settings
    from app.routers import auth as auth_router

    web_client = "1234-web.apps.googleusercontent.com"
    android_client = "1234-android.apps.googleusercontent.com"
    monkeypatch.setattr(auth_router.settings, "google_client_id", web_client)
    assert get_settings().google_client_id == web_client
    tokens = {
        "android-for-web-client-0123456789": {"aud": web_client, "azp": android_client},
        "android-for-android-client-012345": {"aud": android_client, "azp": android_client},
    }
    seen = []

    def verify(credential, request, audience):
        seen.append(audience)
        claims = tokens.get(credential)
        if claims is None or claims["aud"] != audience:
            raise ValueError("Token has wrong audience")
        return {
            **claims, "iss": "https://accounts.google.com", "sub": "android-sub-1", "email": "Phone@Gmail.com",
            "email_verified": True, "name": "Phone Person",
        }

    monkeypatch.setattr(id_token, "verify_oauth2_token", verify)
    ok = client.post("/auth/google", json={"credential": "android-for-web-client-0123456789"})
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["user"]["email"] == "phone@gmail.com" and body["user"]["google_linked"] is True
    assert seen == [web_client]  # verified against the Web client id, never the Android one
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and len(me.json()["author_id"]) == 32
    # A token minted for the Android client id itself is refused.
    refused = client.post("/auth/google", json={"credential": "android-for-android-client-012345"})
    assert refused.status_code == 401
    # Validation: a credential too short to be a token.
    assert client.post("/auth/google", json={"credential": "short"}).status_code == 422


def test_android_presence_client_kind(client):
    owner = Person(client, "owner@example.com")
    sam = Person(client, "sam@example.com", trial=False)
    pid = create(client, owner.dev)["project_id"]
    invite_and_accept(client, owner, pid, sam, "editor")
    phone = hex32()
    beat = {
        "replica_id": phone, "client": "android",
        "view": {"storey": None, "eye_mm": [4200, 1800, 1600], "yaw_deg": 90}, "selection": [], "editing": [],
    }
    answer = shaped(client.put(f"/projects/{pid}/presence", json=beat, headers=sam.web), clients.PresenceAnswer)
    assert answer.ttl_s == 30
    listed = shaped(client.get(f"/projects/{pid}/presence", headers=owner.web), clients.PresenceList)
    mine = [p for p in listed.present if p.replica_id == phone]
    assert len(mine) == 1 and mine[0].client == "android" and mine[0].user_id == sam.user_id
    assert mine[0].view is not None and mine[0].view.yaw_deg == 90
    # Leaving removes it.
    shaped(client.put(f"/projects/{pid}/presence", json={**beat, "leaving": True}, headers=sam.web), clients.PresenceAnswer)
    assert all(p.replica_id != phone for p in clients.PresenceList.model_validate(
        client.get(f"/projects/{pid}/presence", headers=owner.web).json()).present)
    # Auth and validation failures.
    assert client.put(f"/projects/{pid}/presence", json=beat, headers=CONTRACT).status_code == 401
    error_of(client.put(f"/projects/{pid}/presence", json={**beat, "client": "phone"}, headers=sam.web), 422, "validation_failed")


# --- the generated clients and the routes agree with the document ------------------------------


def test_generated_clients_are_from_this_document():
    sha = _sha(DOC)
    assert (GEN / "SPEC_SHA256").read_text(encoding="utf-8").strip() == sha, "the Dart client is stale: run scripts/gen-clients.ps1"
    first = DTS.read_text(encoding="utf-8").splitlines()[0]
    assert f"sha256 {sha}" in first, "src/lib/api-clients.d.ts is stale: run scripts/gen-clients.ps1"
    # Every operation has its Dart method and every answer its Dart model.
    dart = "\n".join(p.read_text(encoding="utf-8") for p in (GEN / "api").glob("*.dart"))
    models = {p.stem for p in (GEN / "model").glob("*.dart")}
    for op_id, _, answer, _, _ in clients.ROUTES.values():
        camel = re.sub(r"_(\w)", lambda m: m.group(1).upper(), op_id)
        assert f"Future<Response> {camel}WithHttpInfo(" in dart, op_id
        snake = re.sub(r"(?<!^)([A-Z])", r"_\1", answer.__name__).lower()
        assert snake in models, answer.__name__
    # PF9 reads its answers through the generated types.
    app_ts = (ROOT / "src" / "lib" / "app.ts").read_text(encoding="utf-8")
    assert 'from "@/lib/api-clients"' in app_ts and 'Wire["PushAnswer"]' in app_ts


def test_routes_answer_the_documented_shapes(client):
    """One project walked through every route both clients call; each answer
    parses as the document's model with no key the document lacks."""
    from .market_helpers import SOFA, SUPPLIER_ID, load as load_market

    owner = Person(client, "owner@example.com")
    sam = Person(client, "sam@example.com")
    pid = create(client, owner.dev)["project_id"]
    invite_and_accept(client, owner, pid, sam, "editor")
    client.post(f"/projects/{pid}/members", json={"email": "later@example.com", "role": "viewer"}, headers=owner.web)

    login = client.post("/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert login.status_code == 200 and login.json()["user"]["email"] == "owner@example.com"
    me = client.get("/auth/me", headers=owner.session).json()
    assert me["author_id"] == owner.author_id

    listed = shaped(client.get("/projects", headers=owner.web), clients.ProjectList)
    assert [p.project_id for p in listed.projects] == [pid] and listed.projects[0].latest_snapshot is None
    opened = shaped(client.get(f"/projects/{pid}", headers=sam.web), clients.OpenProject)
    assert opened.role == "editor" and {m.state for m in opened.members} == {"active", "invited"}
    shaped(client.get(f"/projects/{pid}/members", headers=sam.web), clients.MemberList)

    # The log: Sam's desktop delta, the phone's action, a conflict, a pull.
    wall = hex32()
    shaped(client.post(f"/projects/{pid}/ops", json={"replica_id": sam.replica, "ops": [delta_op(sam.author_id, [wall])]},
                       headers=sam.dev), clients.PushAnswer)
    phone = hex32()
    accepted = shaped(
        client.post(f"/projects/{pid}/ops", json={"replica_id": phone, "ops": [action_op(owner.author_id, [hex32()], base_seq=1)]},
                    headers=owner.web),
        clients.PushAnswer,
    )
    assert [r.status for r in accepted.results] == ["accepted"]
    stale = action_op(owner.author_id, [wall], base_seq=0)
    later = action_op(owner.author_id, [hex32()], base_seq=0)
    rejected = shaped(client.post(f"/projects/{pid}/ops", json={"replica_id": phone, "ops": [stale, later]}, headers=owner.web),
                      clients.PushAnswer)
    assert [r.status for r in rejected.results] == ["rejected", "not_processed"]
    assert rejected.results[0].winning and rejected.results[0].winning[0].kind == "delta"
    page = shaped(client.get(f"/projects/{pid}/ops", params={"after": 0, "limit": 1000}, headers=owner.web), clients.PullPage)
    assert [o.server_seq for o in page.ops] == [1, 2] and page.head_seq == 2 and page.more is False
    assert page.ops[0].delta is not None and page.ops[1].action is not None and page.ops[1].action.tool == "move"

    # Snapshots with the digest.
    assert snapshot_with_digest(client, owner.dev, pid, 2, digest_bytes()).status_code == 201
    snap = shaped(client.get(f"/projects/{pid}/snapshots/latest", headers=sam.web), clients.Snapshot)
    assert snap.files.digest is not None and snap.files.digest.url
    shaped(client.get("/projects", headers=sam.web), clients.ProjectList)

    # Presence (the phone) and the panoramas.
    beat = {"replica_id": phone, "client": "android", "selection": [], "editing": []}
    shaped(client.put(f"/projects/{pid}/presence", json=beat, headers=owner.web), clients.PresenceAnswer)
    shaped(client.get(f"/projects/{pid}/presence", headers=sam.web), clients.PresenceList)
    set_id = _followed_set(owner.user_id, pid)
    sets = shaped(client.get(f"/projects/{pid}/panoramas", headers=sam.web), clients.PanoramaSets)
    assert [s.set_id for s in sets.sets] == [set_id]
    state = shaped(client.get(f"/projects/{pid}/panoramas/{set_id}", headers=sam.web), clients.SetState)
    assert state.manifest is not None and state.manifest.schema_ == "truebex-tiles/1"
    assert set(state.manifest.views[0].faces.model_dump()) == {"n", "e", "s", "w", "u", "d"}

    # The marketplace reads (prices for the digest's products, a swap search).
    load_market()
    variant = SOFA["variants"][0]["variant_id"]
    prices = client.post(
        "/market/prices",
        json={"region": "GB", "items": [{"supplier_id": SUPPLIER_ID, "sku": SOFA["sku"], "variant_id": variant, "qty": 1}]},
        headers={"X-Truebex-Contract": "marketplace-api/1.1"},
    )
    answer = shaped(prices, clients.PricesAnswer)
    assert answer.items[0].sku == SOFA["sku"]
    found = shaped(client.get("/market/search", params={"category": SOFA["category"], "region": "GB", "limit": 6},
                              headers={"X-Truebex-Contract": "marketplace-api/1.1"}), clients.SearchAnswer)
    assert found.results
    product = shaped(client.get(f"/market/products/{found.results[0].product_id}", params={"region": "GB"},
                                headers={"X-Truebex-Contract": "marketplace-api/1.1"}), clients.ProductAnswer)
    assert product.variants


def test_contract_fixtures_are_the_shared_vectors():
    """Both clients' tests read the same files: PF9's self-test and PF10's Flutter tests."""
    selftest = (ROOT / "src" / "viewer" / "selftest.ts").read_text(encoding="utf-8")
    assert "action-move.json" in selftest
    dart_tests = "\n".join(p.read_text(encoding="utf-8") for p in (APP / "test").rglob("*.dart"))
    assert "server/tests/contracts/project-log" in dart_tests.replace("\\", "/")
    for name in ("action-move.json", "ops-remote.json"):
        assert name in dart_tests and (FIXTURES / name).exists()


# --- build checks of the Android project (no Flutter SDK needed) --------------------------------


def _png_size(path: Path) -> tuple[int, int]:
    head = path.read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    return struct.unpack(">II", head[16:24])


BANNED = re.compile(
    r"\b(unreal|epic games|unity|revit|archicad|sketchup|autocad|rhino|lumion|enscape|twinmotion|chief architect|"
    r"metaverse|vr|walkthrough|revolutionary|next-gen|seamless)\b",
    re.I,
)


def test_store_listing_assets():
    icon = STORE / "icon-512.png"
    graphic = STORE / "feature-graphic-1024x500.png"
    assert _png_size(icon) == (512, 512)
    assert _png_size(graphic) == (1024, 500)
    shots = sorted((STORE / "screenshots").glob("*.png"))
    assert 2 <= len(shots) <= 8
    for shot in shots:
        w, h = _png_size(shot)
        assert h > w and 320 <= w and h <= 3840 and h <= 2 * w, f"{shot.name}: {w}x{h} is not a portrait phone shot"

    listing = (STORE / "listing.en.md").read_text(encoding="utf-8")
    short = re.search(r"## Short description\s+(.+?)\n\s*\n", listing, re.S).group(1).strip()
    full = re.search(r"## Full description\s+(.+?)\n## ", listing, re.S).group(1).strip()
    assert 10 <= len(short) <= 80, len(short)
    assert 200 <= len(full) <= 4000, len(full)
    assert "https://truebex.com/privacy/" in listing
    for name in ("listing.en.md", "data-safety.md", "content-rating.md"):
        text = (STORE / name).read_text(encoding="utf-8")
        assert not BANNED.search(text), f"{name}: {BANNED.search(text).group(0)!r} breaks the brand rules"
    safety = (STORE / "data-safety.md").read_text(encoding="utf-8").lower()
    for answer in ("encrypted in transit", "not sold", "no tracking", "deletion"):
        assert answer in safety, answer


def test_app_strings_follow_the_brand_rules():
    arb = json.loads((APP / "lib" / "l10n" / "app_en.arb").read_text(encoding="utf-8"))
    for key, text in arb.items():
        if key.startswith("@"):
            continue
        assert not BANNED.search(text), f"{key}: {text!r}"
    # The conflict line is PF9's, word for word.
    assert arb["conflict"] == "{name} changed this first — your edit was replaced"


def test_mobile_gate_and_lint_ignore():
    gate = (ROOT / "scripts" / "verify-mobile.ps1").read_text(encoding="utf-8")
    for step in ("flutter analyze", "flutter test", "flutter build apk --debug"):
        assert step in gate, step
    eslint = (ROOT / "eslint.config.mjs").read_text(encoding="utf-8")
    assert '"mobile/**"' in eslint
    manifest = (APP / "android" / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
    assert "android:allowBackup=\"false\"" in manifest or "dataExtractionRules" in manifest
    assert "networkSecurityConfig" in manifest
    gradle = (APP / "android" / "app" / "build.gradle.kts").read_text(encoding="utf-8")
    assert 'applicationId = "com.truebex.app"' in gradle
    release = (APP / "android" / "app" / "src" / "main" / "res" / "xml" / "network_security_config.xml").read_text(encoding="utf-8")
    assert 'cleartextTrafficPermitted="false"' in release
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Android app" in readme
