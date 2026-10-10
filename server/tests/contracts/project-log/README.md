# Project-log contract fixtures (`contracts/project-log.md` v1.0.0, §9)

Copied, never edited: the app side is authoritative for these files.

On 2026-10-10 the app repository had no `Docs/roadmap/fixtures/contracts/project-log/` folder yet (CL1
creates it once CL0 has landed), so PF4 wrote this set to the letter of `project-log.md` §5, §6 and §9 with
`server/scripts/make_project_log_fixtures.py` (deterministic) and staged it here. CL1 copies the folder into
the app repo (or replaces it with its own, after which this folder is re-copied from there).

| File | Holds |
|---|---|
| `project.json`, `members.json`, `versions.json` | the 5.3 record of "House" with an owner (user 42) and an editor (user 7), its members (5.13) and one named version at sequence 0 (5.10) |
| `snapshot-0000.tbxp` | the app repo's `Docs/roadmap/fixtures/Z0-baseline.tbxp` as it is today; CL1 replaces it with the copy re-saved after CL0 (rows with ids) |
| `ops-remote.json` | a 5.6 push body: 12 operations by the editor (author `0199c6a2f0007000a000000000000007`) against ids of that snapshot; deltas are stand-in bytes (`TBXD` + JSON) until CL1 defines the byte form |
| `presence.json` | the editor in the kitchen, editing one wall: the 5.17 heartbeat and the 5.18 entry |
| `action-move.json` | one `action` operation as PF9 writes it (`move` of a wall, agent-interface §6.4) |

A person's operations carry their own `author_id` (licence 5.7): replaying `ops-remote.json` needs a caller
whose `author_id` is the editor's, so the platform test sets it, and `scripts/demo_replica.py` rewrites
`author` to the signed-in account's.
