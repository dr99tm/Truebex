"""Write the licence contract's §9 fixtures (licence-api.md v1.0.0).

    cd server
    .venv\\Scripts\\python.exe scripts\\make_licence_fixtures.py [--out DIR] [--check]

The app repo's Docs/roadmap/fixtures/contracts/licence/ is the master copy
(the app side is authoritative); this script made the first version there
because PF1 landed before LC1 (LC1's Deliverables allow it). Everything is
deterministic: a fixed TEST key (Ed25519 signatures are deterministic too),
fixed ids, nonces and clocks, so re-running reproduces the same bytes.
`--check` regenerates in memory and fails if the folder differs.

The TEST key's private half is in keys.json on purpose: it is worthless
outside tests, and the app pins kid test-2026-10 in non-Shipping builds only.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))

from app.licence import signing  # noqa: E402
from app.licence.jcs import canonicalize  # noqa: E402

OUT = SERVER / "tests" / "contracts" / "licence"
KID = "test-2026-10"
SEED = signing.b64url_encode(hashlib.sha256(b"truebex licence-api TEST key test-2026-10").digest())
STUB_NOW = "2026-10-09T12:00:00Z"
ISSUED = "2026-10-09T11:00:00Z"
REQUEST_ID = "0" * 31 + "1"

FREE_FEATURES = ["export.dxf", "export.pdf", "lighting.full", "render.panorama"]
GATE_KEYS = [
    "export.clean", "export.dwg", "export.ifc", "assets.library", "share.links", "vr.pc", "mep",
    "analysis.reports", "market.cost", "cloud.sync", "cloud.panoramas", "collab.live", "ai.byok", "ai.metered",
]
PAID_FEATURES = sorted(set(FREE_FEATURES + GATE_KEYS))
FREE_LIMITS = {"storeys": 1, "devices": 2, "share_links": 1, "cloud_cu_month": 0, "ai_credits_month": 0}
PAID_LIMITS = {**FREE_LIMITS, "storeys": None}


def uuid7(ms: int, tail: int) -> str:
    """A fixed UUIDv7 (32 hex) from milliseconds and a 74-bit tail."""
    rand_a, rand_b = tail >> 62 & 0xFFF, tail & ((1 << 62) - 1)
    return f"{ms << 80 | 0x7 << 76 | rand_a << 64 | 0b10 << 62 | rand_b:032x}"


MS = 1791543600000  # 2026-10-09T11:00:00Z
DEVICE_ID = uuid7(MS, 0x1A2B3C4D5E6F708192)
DEVICE_ID_2 = uuid7(MS - 86_400_000, 0x2B3C4D5E6F70819203)
AUTHOR_ID = uuid7(MS - 30 * 86_400_000, 0x3C4D5E6F7081920314)
ORG_ID = uuid7(MS - 60 * 86_400_000, 0x4D5E6F708192031425)
FINGERPRINT = hashlib.sha256(
    b"truebex-fp/1\n8f2c1b9e-0d4a-4f6b-9c3e-2a1b0c9d8e7f\nS-1-5-21-1004336348-1177238915-682003330-1001"
).hexdigest()
ACCOUNT = {"user_id": 42, "email": "a@b.com", "author_id": AUTHOR_ID, "org_id": None}
USER_OUT = {
    "id": 42, "email": "a@b.com", "created_at": "2026-10-01T09:00:00", "plan": "pro", "name": "A B",
    "avatar_url": None, "has_password": True, "google_linked": False,
}

# The 4 KiB stand-in installer whose size and SHA-256 the feeds state.
INSTALLER = (b"TRUEBEX INSTALLER STUB - contract licence-api fixtures, not a real installer.\n" * 64)[:4096]
INSTALLER_SHA = hashlib.sha256(INSTALLER).hexdigest()

# Hand-written RFC 8785 results (independent of jcs.py): the referee for both
# canonicalisers on the escapes the contract names.
JCS_CASES = [
    {"name": "keys sorted by UTF-16 code units, nested, no whitespace",
     "document": {"b": 1, "a": {"z": [], "B": {}}, "A": [3, 1, 2]},
     "canonical": '{"A":[3,1,2],"a":{"B":{},"z":[]},"b":1}'},
    {"name": "short escapes, quote and backslash",
     "document": {"s": "tab\there \"quoted\" back\\slash\nnew\rline\bbell\fform"},
     "canonical": '{"s":"tab\\there \\"quoted\\" back\\\\slash\\nnew\\rline\\bbell\\fform"}'},
    {"name": "other control characters as lowercase \\u00xx; DEL and / left alone",
     "document": {"c": "\u0000\u0001\u001f\u007f/"},
     "canonical": '{"c":"\\u0000\\u0001\\u001f\u007f/"}'},
    {"name": "non-ASCII stays UTF-8, never \\u-escaped",
     "document": {"t": "café — € \U0001f600"},
     "canonical": '{"t":"café — € \U0001f600"}'},
    {"name": "integers, booleans, null",
     "document": {"n": [0, -1, 9007199254740991], "t": True, "f": False, "z": None},
     "canonical": '{"f":false,"n":[0,-1,9007199254740991],"t":true,"z":null}'},
]


def nonce(name: str) -> str:
    return hashlib.sha256(f"nonce {name}".encode()).hexdigest()[:32]


def document(name: str, **over) -> dict:
    doc = {
        "schema": "truebex-entitlement/1",
        "plan": "pro",
        "features": PAID_FEATURES,
        "limits": PAID_LIMITS,
        "seat_kind": "personal",
        "trial": False,
        "device_id": DEVICE_ID,
        "fingerprint": FINGERPRINT,
        "issued_at": ISSUED,
        "refresh_after": "2026-10-10T11:00:00Z",
        "expires_at": "2026-10-23T11:00:00Z",
        "plan_period_end": "2026-11-01T00:00:00Z",
        "nonce": nonce(name),
        "account": ACCOUNT,
    }
    doc.update(over)
    return doc


def entitlement_fixtures(key) -> dict[str, dict]:
    docs = {
        "free": document(
            "free", plan="free", features=FREE_FEATURES, limits=FREE_LIMITS, seat_kind="free", plan_period_end=None
        ),
        "pro": document("pro"),
        "studio": document("studio", plan="studio"),
        "team": document("team", plan="team", seat_kind="named", account={**ACCOUNT, "org_id": ORG_ID}),
        "enterprise": document(
            "enterprise", plan="enterprise", seat_kind="named", plan_period_end=None,
            account={**ACCOUNT, "org_id": ORG_ID},
        ),
        # A trial that started on 2026-10-05 and ends on 2026-10-19: the
        # document may not outlive it.
        "trial": document(
            "trial", seat_kind="trial", trial=True, expires_at="2026-10-19T11:00:00Z",
            plan_period_end="2026-10-19T11:00:00Z",
        ),
        "floating": document(
            "floating", plan="team", seat_kind="floating", refresh_after="2026-10-09T11:30:00Z",
            expires_at="2026-10-09T13:00:00Z", account={**ACCOUNT, "org_id": ORG_ID},
        ),
        "expired": document(
            "expired", issued_at="2026-09-20T11:00:00Z", refresh_after="2026-09-21T11:00:00Z",
            expires_at="2026-10-04T11:00:00Z",
        ),
    }
    notes = {
        "free": "Free: watermarked exports (no export.clean), one storey.",
        "pro": "Pro on a personal seat; the stub's default.",
        "studio": "Studio on a personal seat.",
        "team": "Team on a named seat of an organisation.",
        "enterprise": "Enterprise on a named seat.",
        "trial": "The 14-day Pro trial: expires_at is the trial's end, not issued_at + 14 d.",
        "floating": "Team on a floating seat: refresh after 30 min, expires after 2 h.",
        "expired": "Pro, expires_at before stub_now: the app must run Free.",
        "tampered": "Pro signed, then plan changed to enterprise: the signature must fail.",
    }
    out = {}
    for name, doc in docs.items():
        env = signing.sign_envelope(doc, key, KID)
        out[name] = {"note": notes[name], "stub_now": STUB_NOW, "canonical": canonicalize(doc), "envelope": env}
    env = signing.sign_envelope(document("tampered"), key, KID)
    env["document"] = {**env["document"], "plan": "enterprise"}
    out["tampered"] = {
        "note": notes["tampered"], "stub_now": STUB_NOW, "canonical": canonicalize(env["document"]), "envelope": env,
    }
    return out


def manifest(version: str, channel: str, published_at: str, notes_md: str, min_from: str | None) -> dict:
    return {
        "schema": "truebex-release/1",
        "version": version,
        "channel": channel,
        "platform": "win64",
        "published_at": published_at,
        "mandatory": False,
        "min_update_from": min_from,
        "notes_md": notes_md,
        "notes_url": f"https://truebex.com/changelog/#{version}",
        "installer": {"file": f"Truebex-Setup-{version}.exe", "bytes": len(INSTALLER), "sha256": INSTALLER_SHA},
    }


def release_fixtures(key) -> dict[str, dict]:
    rel = [
        manifest(
            "1.2.0-beta.1", "beta", "2026-11-20T09:00:00Z",
            "### What's new in the beta\n* A fixture release for tests, not a real one.\n", "1.1.0",
        ),
        manifest(
            "1.1.0", "stable", "2026-11-02T09:00:00Z",
            "### What's new\n* A fixture release for tests, not a real one.\n"
            "* **Bold**, a [link](https://truebex.com/changelog/#1.1.0), \"quotes\", "
            "a back\\slash and an em dash — for both canonicalisers.\n",
            "1.0.0",
        ),
        manifest("1.0.0", "stable", "2026-10-07T09:00:00Z", "### First release\n* A fixture release for tests.\n", None),
    ]

    def entry(m):
        return {
            "manifest": m,
            "signature": signing.sign(m, key, KID),
            "download": f"/releases/{m['version']}/download?platform=win64",
        }

    def feed(channel, ms):
        return {
            "schema": "truebex-releases/1", "channel": channel, "platform": "win64",
            "latest": ms[0]["version"], "releases": [entry(m) for m in ms],
        }

    return {
        "releases-stable": {"http_status": 200, "body": feed("stable", rel[1:])},
        "releases-beta": {"http_status": 200, "body": feed("beta", rel)},
    }


def error(code: str, status: int, detail: str, data=None) -> dict:
    return {
        "http_status": status,
        "body": {"detail": detail, "code": code, "status": status, "request_id": REQUEST_ID,
                 "retry_after_s": None, "data": data},
    }


def response_fixtures(ents: dict) -> dict[str, dict]:
    pro = ents["pro"]["envelope"]
    devices = [
        {"device_id": DEVICE_ID, "name": "DESKTOP-7Q2", "os": "windows 10.0.26200", "app_version": "1.0.0",
         "activated_at": "2026-10-09T11:00:00Z", "last_seen_at": "2026-10-09T11:55:00Z", "current": True},
        {"device_id": DEVICE_ID_2, "name": "STUDIO-LAPTOP", "os": "windows 10.0.22631", "app_version": "1.0.0",
         "activated_at": "2026-10-08T11:00:00Z", "last_seen_at": "2026-10-08T18:20:00Z", "current": False},
    ]
    return {
        "link-start": {"http_status": 201, "body": {
            "link_code": "QX7D-K9MP", "poll_secret": "fixture-poll-secret-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"[:43],
            "verify_url": "https://truebex.com/dashboard/link/?code=QX7D-K9MP", "expires_in_s": 600, "interval_s": 5,
        }},
        "link-pending": {"http_status": 200, "body": {"status": "pending"}},
        "link-approved": {"http_status": 200, "body": {"status": "approved", "token": {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0MiJ9.fixture-not-a-real-token",
            "token_type": "bearer", "user": USER_OUT,
        }}},
        "link-expired": error("link_expired", 410, "This sign-in code has expired or was already used. Start again."),
        "activate-ok": {"http_status": 201, "body": {
            "device_id": DEVICE_ID, "device_token": "tbx_dev_fixture-not-a-real-token-AAAAAAAAAAAAAAAA"[:51],
            "entitlement": pro,
        }},
        "activate-device-limit": error(
            "device_limit", 409, "2 devices are active on this seat. Remove one to continue.",
            {"limit": 2, "devices": [{k: d[k] for k in ("device_id", "name", "os", "app_version", "last_seen_at")}
                                     for d in devices]},
        ),
        "account-pro": {"http_status": 200, "body": {
            "user": {"id": 42, "email": "a@b.com", "name": "A B", "avatar_url": None},
            "author_id": AUTHOR_ID, "plan": "pro", "plan_name": "Pro",
            "trial": {"used": True, "active": False, "ends_at": None},
            "seat": {"kind": "personal", "org_id": None, "org_name": None},
            "seats": {"total": 1, "assigned": 1}, "devices": {"active": 2, "limit": 2},
            "manage_url": "https://truebex.com/dashboard/billing/",
        }},
        "devices": {"http_status": 200, "body": {"devices": devices, "limit": 2}},
    }


README = """# Licence contract fixtures (licence-api.md v1.0.0, §9)

Made by PF1 on 2026-10-09 with `server/scripts/make_licence_fixtures.py` (deterministic: re-running
reproduces these bytes). From the merge on, the master copy is the app repo's
`Docs/roadmap/fixtures/contracts/licence/`; the platform keeps a copy here, copied, never edited.

| File | Holds |
|---|---|
| `keys.json` | the TEST key pair, kid `test-2026-10`; `private_key` is the 32-byte Ed25519 seed (base64url), worthless outside tests |
| `entitlement-<name>.json` | `{note, stub_now, canonical, envelope}`: `envelope` is the 5.5 `entitlement` exactly as served, `canonical` the RFC 8785 text of `envelope.document`, `stub_now` the clock the stub pins |
| `link-*.json`, `activate-*.json`, `account-pro.json`, `devices.json`, `releases-*.json` | responses as `{http_status, body}`; errors use the shared §7 envelope |
| `installer-stub.bin` | the 4 KiB "installer" whose size and SHA-256 the release manifests state |
| `jcs-cases.json` | hand-written RFC 8785 results for the escapes §6.2 names (both canonicalisers must match) |

Every signature is by the TEST key. `entitlement-tampered.json` was signed as Pro and then edited to
Enterprise, so it must fail; `entitlement-expired.json` expired before `stub_now`. Release notes are
fixture text, never public copy.
"""


def build() -> dict[str, bytes]:
    key = signing.private_key_from_seed(SEED)
    for case in JCS_CASES:
        got = canonicalize(case["document"])
        if got != case["canonical"]:
            raise SystemExit(f"jcs.py disagrees with the hand-written case {case['name']!r}: {got!r}")
    files: dict[str, object] = {
        "keys.json": {
            "note": "TEST key for the licence contract fixtures. Never used in production.",
            "keys": [{"kid": KID, "alg": "Ed25519", "use": "test", "public_key": signing.public_key_b64url(key),
                      "private_key": SEED}],
        },
        "jcs-cases.json": {"cases": JCS_CASES},
    }
    ents = entitlement_fixtures(key)
    files.update({f"entitlement-{n}.json": v for n, v in ents.items()})
    files.update({f"{n}.json": v for n, v in response_fixtures(ents).items()})
    files.update({f"{n}.json": v for n, v in release_fixtures(key).items()})
    out = {name: (json.dumps(v, indent=2, ensure_ascii=False) + "\n").encode("utf-8") for name, v in files.items()}
    out["installer-stub.bin"] = INSTALLER
    out["README.md"] = README.encode("utf-8")
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--check", action="store_true", help="fail if the folder differs from a fresh build")
    args = ap.parse_args(argv)
    out = Path(args.out)
    files = build()
    if args.check:
        stale = [n for n, data in files.items() if not (out / n).is_file() or (out / n).read_bytes() != data]
        if stale:
            print("differs: " + ", ".join(sorted(stale)))
            return 1
        print(f"{len(files)} fixture files up to date")
        return 0
    out.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (out / name).write_bytes(data)
    print(f"wrote {len(files)} files to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
