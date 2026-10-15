# Project-log contract fixtures (`contracts/project-log.md` v1.1.0, §9)

Copied, never edited: the app side is authoritative for these files.

This is CL1's set. The app writes it from its own code (`TruebexSync::FSyncStub::WriteFixtures`,
`-mwcl1fixtures`; checked there by `cl-fixtures`) into `Docs/roadmap/fixtures/contracts/project-log/`. The
folder last changed in app commit 93bc4cac2 (CL1, on app `main` since the merge 496033be3). PF4a copied it on
2026-10-15 from app `main` ad3aa5c45 with `scripts/sync-contract-fixtures.ps1 -Contract project-log`: each
file is the app's blob byte for byte (LF, as committed, not the app checkout's CRLF copy).
`server/tests/test_pf4a_project_log_1_1.py` holds the blob ids (`APP_BLOBS`) and checks them without the app
repository. PF4's own stand-in set (written by `server/scripts/make_project_log_fixtures.py`, now retired)
is gone; the app's set replaced it as this README said it would.

| File | Holds |
|---|---|
| `project.json` | the 5.3 record of "House (fixture)" (`019a2b3c4d5e70008a00000000000001`), owner Ana (user 42), 2 members, `doc_version` 55, head 0, no snapshot yet |
| `members.json` | a 5.13 body: Ana Owner (owner) and Sam Editor (editor), both active, each with an `author_id` (1.1.0): Ana `019a2b3c4d5e7000a000000000000042`, Sam `019a2b3c4d5e7000a000000000000007` |
| `versions.json` | a 5.10 body: one version, "Baseline", at sequence 0, `snapshot_id` `c1000000000000000000000000000001` |
| `snapshot-0000.tbxp` | the app's version 55 document (`projectUid` `f08ffe0283418dea8627d42c7908ab88`): `Docs/roadmap/fixtures/Z0-baseline.tbxp` re-saved after CL0, so every row carries a 32-hex `uid` (77 walls, 31 openings) |
| `ops-remote.json` | `truebex-project-log-ops/1` (`schema`, `note`, `ops`; no push-level `replica_id`): 12 `delta` operations by Sam from replica `25a7548b4dbe8e788815184808694548`, each naming its own `replica_id`, `base_seq` 0, `delta_format` `o5/55`, real deltas in §6.2's byte form (base64 of gzip of the `o5/55` JSON with `ids`, `keys`, `before`, `after`) against that snapshot's ids |
| `presence.json` | a 5.18 body (`{"present": [...]}`): Sam on the desktop in the kitchen, selecting and editing wall `dc643577cfb582fabd0d7f9edef6b30d` |
| `action-move.json` | one bare §6.2 `action` operation as a light client writes it: Sam (the editor) moves wall `dc643577cfb582fabd0d7f9edef6b30d` 600 mm north, `refs` `["wall#dc643577cfb582fabd0d7f9edef6b30d"]` (agent-interface §6.2), `touched` the bare id; no `session` or `request_id` (the kernel's replay never reads them) |

A person's operations carry their own `author_id` (licence 5.7): replaying `ops-remote.json` needs a caller
whose `author_id` is Sam's, so the platform tests set it, and `scripts/demo_replica.py` rewrites `author` to
the signed-in account's (keeping each operation's replica and delta). Re-copy with the sync script when the
app's folder changes, then update `APP_BLOBS` and this README.
