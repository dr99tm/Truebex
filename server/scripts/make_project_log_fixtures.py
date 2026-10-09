"""Write the project-log contract fixtures (contracts/project-log.md §9) into
server/tests/contracts/project-log/.

    .venv\\Scripts\\python.exe scripts\\make_project_log_fixtures.py [--baseline <Z0-baseline.tbxp>]

Deterministic: re-running reproduces the same bytes. CL1 owns the master copy
(`Docs/roadmap/fixtures/contracts/project-log/` in the app repo) once CL0 has
landed; until then PF4 stages this set, written to the letter of §5, §6 and
§9. `snapshot-0000.tbxp` is the app repo's `Docs/roadmap/fixtures/Z0-baseline.tbxp`
as it is today (before CL0 gives its rows ids); the server never opens it.
Deltas are stand-in bytes (`TBXD` + JSON): CL1 defines the real byte form,
and the server stores deltas without decoding them.
"""

import argparse
import base64
import hashlib
import json
import shutil
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "contracts" / "project-log"
DEFAULT_BASELINE = Path(r"T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\fixtures\Z0-baseline.tbxp")

PROJECT_ID = "0199c6a2f1007a3c8b5e2d4f6a7b8c9d"
OWNER_AUTHOR = "0199c6a2f0007000a000000000000042"
EDITOR_AUTHOR = "0199c6a2f0007000a000000000000007"
REPLICA_REMOTE = "5e1d0c0ffee000000000000000000b07"
SNAPSHOT_ID = "c0ffee00000000000000000000000001"
VERSION_ID = "7e510000000000000000000000000001"
SCALARS = "00000000000000000000000000000001"
CREATED = "2026-10-09T10:00:00Z"
DOC_VERSION = 38


def eid(kind: int, n: int) -> str:
    """A stable UUIDv7-shaped entity id: walls 1, rooms 2, openings 3, storeys 4."""
    return f"0199c6a2e0007{kind:03x}8{n:015x}"


STOREY = eid(4, 1)
WALLS = [eid(1, n) for n in range(1, 9)]
ROOMS = [eid(2, n) for n in range(1, 4)]
OPENINGS = [eid(3, n) for n in range(1, 4)]


def delta(name: str, touched: list[str]) -> str:
    raw = b"TBXD" + json.dumps({"stand_in": True, "name": name, "rows": touched}, separators=(",", ":")).encode()
    return base64.b64encode(raw).decode("ascii")


def op(n: int, name: str, touched: list[str]) -> dict:
    touched = sorted(set(touched))
    return {
        "op_id": hashlib.sha256(f"ops-remote {n}".encode()).hexdigest()[:32],
        "author": EDITOR_AUTHOR,
        "author_kind": "person",
        "at": f"2026-10-09T10:{n:02d}:00.000Z",
        "touched": touched,
        "delta": delta(name, touched),
        "server_seq": 0,
        "replica_id": REPLICA_REMOTE,
        "base_seq": 0,
        "kind": "delta",
        "name": name,
        "delta_format": f"o5/{DOC_VERSION}",
        "action": None,
        "restore": None,
    }


def ops_remote() -> dict:
    steps = [
        ("Move wall", [WALLS[0]]),
        ("Move wall", [WALLS[1], ROOMS[0]]),
        ("Add door", [OPENINGS[0], WALLS[2]]),
        ("Resize window", [OPENINGS[1]]),
        ("Paint walls", [WALLS[3], WALLS[4]]),
        ("Rename room", [ROOMS[1]]),
        ("Add wall", [WALLS[5], ROOMS[1], ROOMS[2]]),
        ("Move door", [OPENINGS[0]]),
        ("Set floor finish", [ROOMS[2]]),
        ("Change units", [SCALARS]),
        ("Add window", [OPENINGS[2], WALLS[6]]),
        ("Move wall", [WALLS[7], ROOMS[2]]),
    ]
    return {
        "note": "12 operations by the editor (a second author) against ids of snapshot-0000; a 5.6 push body.",
        "replica_id": REPLICA_REMOTE,
        "ops": [op(i + 1, name, touched) for i, (name, touched) in enumerate(steps)],
    }


def member(user_id, email, name, role, accepted=CREATED) -> dict:
    return {
        "user_id": user_id,
        "invite_id": None,
        "email": email,
        "name": name,
        "role": role,
        "state": "active",
        "invited_at": CREATED,
        "accepted_at": accepted,
    }


MEMBERS = [
    member(42, "owner@example.test", "Alex", "owner"),
    member(7, "editor@example.test", "Sam", "editor", "2026-10-09T10:05:00Z"),
]


def project(snapshot_bytes: int) -> dict:
    return {
        "project_id": PROJECT_ID,
        "name": "House",
        "role": "owner",
        "owner": {"user_id": 42, "name": "Alex"},
        "org_id": None,
        "created_at": CREATED,
        "updated_at": "2026-10-09T10:12:00Z",
        "head_seq": 0,
        "latest_snapshot": {
            "snapshot_id": SNAPSHOT_ID,
            "at_seq": 0,
            "doc_version": DOC_VERSION,
            "created_at": CREATED,
        },
        "doc_version": DOC_VERSION,
        "members": MEMBERS,
        "bytes": snapshot_bytes,
        "quota": {"bytes": 10 * 1024**3, "bytes_used": snapshot_bytes},
    }


def versions() -> dict:
    return {
        "versions": [
            {
                "version_id": VERSION_ID,
                "name": "Baseline",
                "note": "The house as first saved to the cloud.",
                "at_seq": 0,
                "snapshot_id": SNAPSHOT_ID,
                "created_by": 42,
                "created_at": CREATED,
            }
        ]
    }


def presence() -> dict:
    kitchen_wall = WALLS[3]
    return {
        "note": "The editor in the kitchen, editing one wall: `heartbeat` is the 5.17 body, `presence` what 5.18 lists.",
        "heartbeat": {
            "replica_id": REPLICA_REMOTE,
            "client": "desktop",
            "view": {"storey": STOREY, "eye_mm": [4200, 1800, 1600], "yaw_deg": 90},
            "selection": [kitchen_wall],
            "editing": [kitchen_wall],
        },
        "presence": {
            "user_id": 7,
            "name": "Sam",
            "replica_id": REPLICA_REMOTE,
            "client": "desktop",
            "seen_at": "2026-10-09T10:12:30Z",
            "view": {"storey": STOREY, "eye_mm": [4200, 1800, 1600], "yaw_deg": 90},
            "selection": [kitchen_wall],
            "editing": [kitchen_wall],
        },
    }


def action_move() -> dict:
    return {
        "note": "One action operation as PF9 writes it: move a wall 600 mm north (agent-interface §6.4).",
        "replica_id": "3eb0000000000000000000000000c1e7",
        "op": {
            "op_id": hashlib.sha256(b"action-move").hexdigest()[:32],
            "author": OWNER_AUTHOR,
            "author_kind": "person",
            "at": "2026-10-09T10:30:00.000Z",
            "touched": [WALLS[0]],
            "delta": None,
            "server_seq": 0,
            "replica_id": "3eb0000000000000000000000000c1e7",
            "base_seq": 12,
            "kind": "action",
            "name": "Move wall",
            "delta_format": None,
            "action": {
                "tool": "move",
                "args": {"refs": [WALLS[0]], "by_mm": [0, 600, 0]},
                "permission": "edit",
                "session": "5e55000000000000000000000000000a",
                "request_id": "4e90000000000000000000000000000b",
            },
            "restore": None,
        },
    }


README = """# Project-log contract fixtures (`contracts/project-log.md` v1.0.0, §9)

Copied, never edited: the app side is authoritative for these files.

On 2026-10-10 the app repository had no `Docs/roadmap/fixtures/contracts/project-log/` folder yet (CL1
creates it once CL0 has landed), so PF4 wrote this set to the letter of `project-log.md` §5, §6 and §9 with
`server/scripts/make_project_log_fixtures.py` (deterministic) and staged it here. CL1 copies the folder into
the app repo (or replaces it with its own, after which this folder is re-copied from there).

| File | Holds |
|---|---|
| `project.json`, `members.json`, `versions.json` | the 5.3 record of "House" with an owner (user 42) and an editor (user 7), its members (5.13) and one named version at sequence 0 (5.10) |
| `snapshot-0000.tbxp` | the app repo's `Docs/roadmap/fixtures/Z0-baseline.tbxp` as it is today; CL1 replaces it with the copy re-saved after CL0 (rows with ids) |
| `ops-remote.json` | a 5.6 push body: 12 operations by the editor (author `{editor}`) against ids of that snapshot; deltas are stand-in bytes (`TBXD` + JSON) until CL1 defines the byte form |
| `presence.json` | the editor in the kitchen, editing one wall: the 5.17 heartbeat and the 5.18 entry |
| `action-move.json` | one `action` operation as PF9 writes it (`move` of a wall, agent-interface §6.4) |

A person's operations carry their own `author_id` (licence 5.7): replaying `ops-remote.json` needs a caller
whose `author_id` is the editor's, so the platform test sets it, and `scripts/demo_replica.py` rewrites
`author` to the signed-in account's.
""".replace("{editor}", EDITOR_AUTHOR)


def write_json(name: str, data: dict) -> None:
    (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    args = parser.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    snap = OUT / "snapshot-0000.tbxp"
    if args.baseline.is_file():
        shutil.copyfile(args.baseline, snap)
    elif not snap.is_file():
        raise SystemExit(f"no baseline at {args.baseline} and no staged snapshot-0000.tbxp")
    size = snap.stat().st_size
    write_json("project.json", project(size))
    write_json("members.json", {"members": MEMBERS})
    write_json("versions.json", versions())
    write_json("ops-remote.json", ops_remote())
    write_json("presence.json", presence())
    write_json("action-move.json", action_move())
    (OUT / "README.md").write_text(README, encoding="utf-8", newline="\n")
    (OUT / ".gitattributes").write_text("*.tbxp binary\n*.json text eol=lf\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT} (snapshot {size} bytes, sha256 {hashlib.sha256(snap.read_bytes()).hexdigest()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
