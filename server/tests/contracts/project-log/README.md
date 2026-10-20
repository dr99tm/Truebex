# Project-log contract fixtures (`contracts/project-log.md` v1.2.0, §9)

Copied, never edited: the app side is authoritative for these files.

This is the app's set: CL1's seven files (contract 1.1.0) and CL2's `comments.json` (1.2.0). The app writes
it from its own code (`TruebexSync::FSyncStub::WriteFixtures` and `WriteCollabFixtures`, `-mwcl1fixtures`;
checked there by `cl-fixtures`) into `Docs/roadmap/fixtures/contracts/project-log/`.

* CL1's seven files last changed in app commit 93bc4cac2 (CL1, on app `main` since the merge 496033be3). PF4a
  copied them on 2026-10-15 from app `main` ad3aa5c45.
* `comments.json` came with app commit 83fdeedad (CL2, on app `main` since the merge 8692c6ff9, 2026-10-19). PF4b
  copied the folder on 2026-10-20 from app `main` 689da345d: `comments.json` new, the other seven unchanged.

Both copies were made with `scripts/sync-contract-fixtures.ps1 -Contract project-log`: each file is the app's
blob byte for byte (LF, as committed, not the app checkout's CRLF copy). `server/tests/test_pf4a_project_log_1_1.py`
holds the blob ids (`APP_BLOBS`) and checks them without the app repository; `test_pf4b_project_log_1_2.py`
checks the eight files against CL2's commits. PF4's own stand-in set (written by
`server/scripts/make_project_log_fixtures.py`, now retired) is gone.

| File | Holds |
|---|---|
| `project.json` | the 5.3 record of "House (fixture)" (`019a2b3c4d5e70008a00000000000001`), owner Ana (user 42), 2 members, `doc_version` 55, head 0, no snapshot yet |
| `members.json` | a 5.13 body: Ana Owner (owner) and Sam Editor (editor, user 7), both active, each with an `author_id` (1.1.0): Ana `019a2b3c4d5e7000a000000000000042`, Sam `019a2b3c4d5e7000a000000000000007` |
| `versions.json` | a 5.10 body: one version, "Baseline", at sequence 0, `snapshot_id` `c1000000000000000000000000000001` |
| `snapshot-0000.tbxp` | the app's version 55 document (`projectUid` `f08ffe0283418dea8627d42c7908ab88`): `Docs/roadmap/fixtures/Z0-baseline.tbxp` re-saved after CL0, so every row carries a 32-hex `uid` (77 walls, 31 openings) |
| `ops-remote.json` | `truebex-project-log-ops/1` (`schema`, `note`, `ops`; no push-level `replica_id`): 12 `delta` operations by Sam from replica `25a7548b4dbe8e788815184808694548`, each naming its own `replica_id`, `base_seq` 0, `delta_format` `o5/55`, real deltas in §6.2's byte form (base64 of gzip of the `o5/55` JSON with `ids`, `keys`, `before`, `after`) against that snapshot's ids |
| `presence.json` | a 5.18 body (`{"present": [...]}`): Sam on the desktop in the kitchen, selecting and editing wall `dc643577cfb582fabd0d7f9edef6b30d` |
| `action-move.json` | one bare §6.2 `action` operation as a light client writes it: Sam (the editor) moves wall `dc643577cfb582fabd0d7f9edef6b30d` 600 mm north, `refs` `["wall#dc643577cfb582fabd0d7f9edef6b30d"]` (agent-interface §6.2), `touched` the bare id; no `session` or `request_id` (the kernel's replay never reads them) |
| `comments.json` | (1.2.0, CL2) `truebex-project-log-comments/1` (`schema`, `note`, `comments`): Sam's comment as 5.19 returns it (§6.6), "I moved this wall 500 mm into the hall -- does the kitchen still fit?", open, a root comment pinned on the wall `presence.json` names (`anchor.entity` `dc643577cfb582fabd0d7f9edef6b30d`, no point, no view); its `comment_id` and `created_at` are the stub's, a server mints its own |

A person's operations carry their own `author_id` (licence 5.7): replaying `ops-remote.json` needs a caller
whose `author_id` is Sam's, so the platform tests set it, and `scripts/demo_replica.py` rewrites `author` to
the signed-in account's (keeping each operation's replica and delta). The comment's author is Sam by user id
(7) and name: `test_pf4b_apps_comment_round_trips` makes Sam user 7. Re-copy with the sync script when the
app's folder changes, then update `APP_BLOBS` and this README.
