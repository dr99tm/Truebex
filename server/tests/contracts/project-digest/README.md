# Project digest fixture (PF9; a MINOR proposal for `contracts/project-log.md` §6.4)

A light client (the mobile web client, PF9; the Android app, PF10) cannot read `.tbxp`. The proposal: a
snapshot may carry `files.digest`, a small JSON file the kernel replica that uploads the snapshot writes
beside it — `truebex-project-digest/1`: storeys; rooms with id, name, storey, area, centroid, bounding walls
(with the face that looks into the room), theme and floor finish; saved views with eye and bearing; placed
products with entity id, `FCadProductRef` (`supplier_id`, `sku`, `variant_id`), category and room; openings
with their host wall; the project's themes; and the project's market region. Lengths in doc millimetres,
areas in m², bearings compass (0 = north = doc +Y). Readers ignore keys they do not know.

| File | Holds |
|---|---|
| `digest-house.json` | the digest of PF4's first fixture house: its walls, rooms, openings and storey ids (PF4's own ids, not those of CL1's set that replaced PF4's in `../project-log/`, PF4a), the saved views (the first is the render-jobs fixtures' "Living room"), and two products of the marketplace fixture's supplier |

Written by `server/scripts/make_digest_fixture.py` (deterministic). The app side writes the real file once the
owner adds `digest` to the contract (C.9); this folder is then re-copied from the app repo.
