"""Write the project digest fixture (PF9; a MINOR proposal for project-log
§6.4) into server/tests/contracts/project-digest/.

    .venv\\Scripts\\python.exe scripts\\make_digest_fixture.py

`digest-house.json` is the `truebex-project-digest/1` file a kernel replica
would write beside the fixture snapshot of PF4's project-log set: the same
entity ids (walls, rooms, openings, storey of `make_project_log_fixtures.py`;
the saved view of the render-jobs fixtures), plus placed products that
reference the marketplace fixture's supplier (PF7's, `tests/fixtures/market`)
so the phone shows names, prices and same-category swaps. Deterministic. The
app writes the real one once the owner adds `digest` to the contract (C.9).
"""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "contracts" / "project-digest"
SCHEMA = "truebex-project-digest/1"
SUPPLIER = "f8afe1ba2b0bf97f23ef888f040cf46a"  # Nord Living, tests/fixtures/market (PF7)


def eid(kind: int, n: int) -> str:
    """PF4's entity ids: walls 1, rooms 2, openings 3, storeys 4; views 5 (PF6);
    products 6 (new here)."""
    return f"0199c6a2e0007{kind:03x}8{n:015x}"


STOREY = eid(4, 1)
WALLS = [eid(1, n) for n in range(1, 9)]
ROOMS = [eid(2, n) for n in range(1, 4)]
OPENINGS = [eid(3, n) for n in range(1, 4)]
VIEWS = [eid(5, n) for n in range(1, 4)]
PRODUCTS = [eid(6, n) for n in range(1, 3)]


def digest() -> dict:
    oak = {"kind": "pattern3d", "pattern": "slat", "texture": "oak", "tile_mm": [180, 1200]}
    tiles = {"kind": "pattern3d", "pattern": "tile", "texture": "stone", "tile_mm": [600, 600]}
    return {
        "schema": SCHEMA,
        "note": "Fixture: what a kernel replica writes beside snapshot-0000 (PF9 proposal for project-log §6.4).",
        "doc_version": 38,
        "units": "mm",
        "region": "GB",
        "storeys": [{"id": STOREY, "name": "Ground floor", "elevation_mm": 0}],
        "rooms": [
            {
                "id": ROOMS[0], "name": "Living room", "storey": STOREY, "area_m2": 24.6, "centroid_mm": [4200, 2200, 0],
                "theme": "nordic-calm",
                "walls": [
                    {"id": WALLS[0], "name": "North wall", "face": "right"},
                    {"id": WALLS[1], "name": "East wall", "face": "right"},
                    {"id": WALLS[2], "name": "South wall", "face": "left"},
                    {"id": WALLS[3], "name": "West wall", "face": "left"},
                ],
                "finishes": {"floor": oak},
            },
            {
                "id": ROOMS[1], "name": "Kitchen", "storey": STOREY, "area_m2": 12.3, "centroid_mm": [8600, 2400, 0],
                "theme": None,
                "walls": [
                    {"id": WALLS[3], "name": "West wall", "face": "right"},
                    {"id": WALLS[4], "name": "North wall", "face": "right"},
                    {"id": WALLS[5], "name": "East wall", "face": "left"},
                ],
                "finishes": {"floor": tiles},
            },
            {
                "id": ROOMS[2], "name": "Bedroom", "storey": STOREY, "area_m2": 14.8, "centroid_mm": [4200, 7000, 0],
                "theme": "warm-minimal",
                "walls": [
                    {"id": WALLS[6], "name": "North wall", "face": "right"},
                    {"id": WALLS[7], "name": "East wall", "face": "left"},
                ],
                "finishes": {"floor": None},
            },
        ],
        "views": [
            {"id": VIEWS[0], "name": "Living room", "storey": STOREY, "room": ROOMS[0], "eye_mm": [4200, 1800, 1600], "yaw_deg": 0},
            {"id": VIEWS[1], "name": "Kitchen", "storey": STOREY, "room": ROOMS[1], "eye_mm": [8600, 2400, 1600], "yaw_deg": 270},
            {"id": VIEWS[2], "name": "Bedroom", "storey": STOREY, "room": ROOMS[2], "eye_mm": [4200, 7000, 1600], "yaw_deg": 180},
        ],
        "products": [
            {
                "id": PRODUCTS[0], "name": "Oslo 3-seater sofa", "room": ROOMS[0], "category": "furniture/seating/sofas",
                "product": {"supplier_id": SUPPLIER, "sku": "SOFA-OSLO-3", "variant_id": "oat-linen"},
                "at_mm": [3000, 3200, 0], "bearing_deg": 180,
            },
            {
                "id": PRODUCTS[1], "name": "Aker coffee table", "room": ROOMS[0], "category": "furniture/tables/coffee-tables",
                "product": {"supplier_id": SUPPLIER, "sku": "TABLE-AKER-CT", "variant_id": "default"},
                "at_mm": [3000, 2200, 0], "bearing_deg": 0,
            },
        ],
        "openings": [
            {"id": OPENINGS[0], "kind": "door", "name": "Door to the hall", "room": ROOMS[0], "host": WALLS[2]},
            {"id": OPENINGS[1], "kind": "window", "name": "Kitchen window", "room": ROOMS[1], "host": WALLS[4]},
            {"id": OPENINGS[2], "kind": "window", "name": "Bedroom window", "room": ROOMS[2], "host": WALLS[6]},
        ],
        "themes": [
            {"id": "nordic-calm", "name": "Nordic calm"},
            {"id": "warm-minimal", "name": "Warm minimal"},
            {"id": "classic-oak", "name": "Classic oak"},
        ],
    }


README = """# Project digest fixture (PF9; a MINOR proposal for `contracts/project-log.md` §6.4)

A light client (the mobile web client, PF9; the Android app, PF10) cannot read `.tbxp`. The proposal: a
snapshot may carry `files.digest`, a small JSON file the kernel replica that uploads the snapshot writes
beside it — `truebex-project-digest/1`: storeys; rooms with id, name, storey, area, centroid, bounding walls
(with the face that looks into the room), theme and floor finish; saved views with eye and bearing; placed
products with entity id, `FCadProductRef` (`supplier_id`, `sku`, `variant_id`), category and room; openings
with their host wall; the project's themes; and the project's market region. Lengths in doc millimetres,
areas in m², bearings compass (0 = north = doc +Y). Readers ignore keys they do not know.

| File | Holds |
|---|---|
| `digest-house.json` | the digest of PF4's fixture house (`../project-log/`): its walls, rooms, openings and storey ids, the saved views (the first is the render-jobs fixtures' "Living room"), and two products of the marketplace fixture's supplier |

Written by `server/scripts/make_digest_fixture.py` (deterministic). The app side writes the real file once the
owner adds `digest` to the contract (C.9); this folder is then re-copied from the app repo.
"""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(digest(), indent=2, ensure_ascii=False) + "\n"
    (OUT / "digest-house.json").write_text(text, encoding="utf-8", newline="\n")
    (OUT / "README.md").write_text(README, encoding="utf-8", newline="\n")
    (OUT / ".gitattributes").write_text("*.json text eol=lf\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT / 'digest-house.json'} ({len(text.encode())} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
