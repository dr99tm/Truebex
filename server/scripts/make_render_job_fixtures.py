"""Write the platform's own render-jobs stand-ins into server/tests/fixtures/render/.

    py -3.12 scripts\\make_render_job_fixtures.py            (writes them)
    py -3.12 scripts\\make_render_job_fixtures.py --check    (exit 1 when a file differs)

PF6 (2026-10-10) staged the whole contract set (render-jobs.md §9) with this
script while the app had none. CL3 then published its own
(`Docs/roadmap/fixtures/contracts/render-jobs/` in the app repo), copied byte
for byte into server/tests/contracts/render-jobs/ by
scripts/sync-contract-fixtures.ps1 (PF6a, 2026-10-15). What the app does not
publish stays here, the platform's own, until AN3 (analysis) and the app
publish theirs: a 5.7 answer (`claim.json`), the two operation files PF6's
job files named, and PF11's wind result (§6.3) with its arrays. Deterministic,
standard library only.
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "render"
SNAPSHOT = Path(__file__).resolve().parents[1] / "tests" / "contracts" / "project-log" / "snapshot-0000.tbxp"

PROJECT_ID = "0199c6a2f1007a3c8b5e2d4f6a7b8c9d"  # the project-log fixtures' "House"
WALL_MOVED = "0199c6a2e00070018000000000000001"  # the project-log fixtures' first wall
JOB_TILES = "a11ce000000000000000000000000002"
LEASE_ID = "1ea5e000000000000000000000000001"
UPLOAD_ID = "0b10ad00000000000000000000000001"


def dump(obj) -> bytes:
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def record(job_id: str, kind: str, state: str, at_seq: int, **extra) -> dict:
    base = {
        "job_id": job_id,
        "kind": kind,
        "state": state,
        "rev": 2,
        "project_id": PROJECT_ID,
        "at_seq": at_seq,
        "progress": 0,
        "message": "",
        "created_at": "2026-10-09T11:00:00Z",
        "started_at": None,
        "finished_at": None,
        "attempts": 0,
        "cost_units_estimate": 1.6,
        "cost_units": None,
        "output_ready": False,
        "error": None,
    }
    base.update(extra)
    return base


README = """# The platform's own render-jobs stand-ins (PF6, PF11)

Not the contract's set: that is the app's own (CL3, render-jobs 1.1.0 §9), copied byte for byte into
`../../contracts/render-jobs/`. These are the files the app publishes no copy of, written by
`server/scripts/make_render_job_fixtures.py` (`--check` compares every file; standard library only). PF6
staged them with the whole set on 2026-10-10; PF6a (2026-10-15) moved them here when CL3's set replaced the
rest. They stay the platform's own until AN3 (analysis, the wind result) and the app publish theirs, after
which those files are re-copied into the contract folder and dropped here. Fixture data, never public copy.

| File | Holds | Read by |
|---|---|---|
| `claim.json` | a 5.7 answer (the job record with `changed` and `params`, the lease, the signed inputs, the output upload; URLs are placeholders) | `test_render.py` (the claim's keys) |
| `ops-empty.json`, `ops-move-wall.json` | the project-log 5.7 bodies PF6's own job files named: none, and one "Move wall" of the project-log fixtures' first wall | nothing since PF6a (the app's `ops-tiles.json` replaced them); kept with their history |
| `wind-result.json`, `wind-*.bin` | an analysis result (§6.3, `truebex-analysis/1`) whose fields name the project-log fixtures' wall ids, and its three little-endian arrays named by SHA-256 | `test_analysis.py`, `tests/fakes/stub_solver/run.py` |

The project id and the wall ids are the project-log fixtures' (`../../contracts/project-log/`).
"""


def files() -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    out["ops-empty.json"] = dump({"ops": [], "head_seq": 0, "more": False})
    move = {
        "op_id": hashlib.sha256(b"render-jobs move wall").hexdigest()[:32],
        "server_seq": 1,
        "replica_id": "5e1d0c0ffee000000000000000000b07",
        "author": "0199c6a2f0007000a000000000000007",
        "author_kind": "person",
        "at": "2026-10-09T11:00:00.000Z",
        "kind": "delta",
        "name": "Move wall",
        "base_seq": 0,
        "touched": [WALL_MOVED],
        "delta_format": "o5/38",
        "delta": "VEJYRHsic3RhbmRfaW4iOnRydWV9",
        "action": None,
        "restore": None,
    }
    out["ops-move-wall.json"] = dump({"ops": [move], "head_seq": 1, "more": False})

    # An analysis result (§6.3): arrays are little-endian files named by SHA-256.
    cp = struct.pack("<8f", -0.8, -0.6, -0.35, 0.1, 0.45, 0.7, 0.9, -0.2)
    ids = b"".join(bytes.fromhex(f"0199c6a2e00070018{n:015x}") for n in range(1, 9))
    comfort = bytes([0, 0, 1, 1, 0, 1, 2, 1, 1, 2, 3, 2, 0, 1, 1, 0])
    arrays = {}
    for data in (cp, ids, comfort):
        sha = hashlib.sha256(data).hexdigest()
        arrays[data] = sha
        out[f"wind-{sha[:12]}.bin"] = data
    wind = {
        "schema": "truebex-analysis/1",
        "kind": "wind",
        "project_id": PROJECT_ID,
        "at_seq": 12,
        "params": {"speed_ms": 5, "direction_deg": 225, "reference_height_m": 10, "terrain": "suburban", "comfort": "lawson"},
        "engine": {"name": "cfd-solver", "version": "1", "image": "sha256:" + hashlib.sha256(b"solver image").hexdigest()},
        "summary": {"max_speed_ms": 7.2},
        "fields": [
            {
                "name": "pressure_coefficient", "unit": "1", "on": "faces", "count": 8,
                "values": arrays[cp], "entities": arrays[ids],
            }
        ],
        "grids": [
            {
                "name": "comfort_lawson", "unit": "class", "origin_mm": [-20000, -20000, 1500], "cell_mm": 500,
                "nx": 4, "ny": 4, "values": arrays[comfort],
            }
        ],
        "report": None,
    }
    out["wind-result.json"] = dump(wind)

    snap = SNAPSHOT.read_bytes()
    claim = {
        "job": record(JOB_TILES, "tiles", "claimed", 1, attempts=0),
        "lease_id": LEASE_ID,
        "lease_expires_at": "2026-10-09T11:02:00Z",
        "inputs": {
            "snapshot": {
                "at_seq": 0,
                "tbxp": {"sha256": hashlib.sha256(snap).hexdigest(), "bytes": len(snap), "url": "https://api.example.invalid/files/snapshot"},
                "tbxpack": None,
            },
            "ops_url": "https://api.example.invalid/files/ops",
            "base_manifest_url": "https://api.example.invalid/files/base-manifest",
            "files": {},
        },
        "output_upload": {"upload_id": UPLOAD_ID, "part_bytes": 8388608},
    }
    out["claim.json"] = dump(claim)
    out["README.md"] = README.encode("utf-8")
    out[".gitattributes"] = b"* -text\n"
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="compare instead of writing; exit 1 on a difference")
    args = parser.parse_args(argv)
    want = files()
    if args.check:
        have = {p.name for p in OUT.iterdir() if p.is_file()} if OUT.is_dir() else set()
        bad = sorted(n for n, data in want.items() if not (OUT / n).is_file() or (OUT / n).read_bytes() != data)
        extra = sorted(have - set(want))
        for name in bad:
            print(f"differs or missing: {OUT / name}")
        for name in extra:
            print(f"not written by this script: {OUT / name}")
        if bad or extra:
            print("run server\\.venv\\Scripts\\python.exe server\\scripts\\make_render_job_fixtures.py")
            return 1
        print(f"{OUT}: {len(want)} files up to date")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in want.items():
        (OUT / name).write_bytes(data)
    print(f"wrote {len(want)} files to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
