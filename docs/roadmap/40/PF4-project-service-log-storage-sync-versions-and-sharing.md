# PF4 — Project service: log storage, sync, versions and sharing (launch priority 2)

**Needs merged:** PF1. **Unblocks:** PF6, PF9, PF12 (their Needs); the real endpoints behind the app's CL1, CL2, CL4. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\project-log.md` (v1.0.0, 2026-10-09; the app side is authoritative).

## Status

**Done 2026-10-10** on `ap/t10-pf4-project-service-log-storage` (Autopilot T10): all eighteen endpoints of
`project-log.md` v1.0.0 plus `POST /projects/invites/accept`, the upload protocol its snapshots use (PF5's
`server/app/uploads/`, taken as is), `Idempotency-Key`, the push hook, the three jobs, the dashboard Projects
pages and `/invite/project/`, and `server/scripts/demo_replica.py`; verify gate green (lint, build, pytest 211
passed, 4 Postgres-marked skipped; on Postgres 17 too). Code: `server/app/projects/`,
`server/app/routers/projects.py`, `src/app/dashboard/projects/`, `src/app/invite/project/`. See As-built.

Before this task no project storage existed (`00-contract.md` P.1; the contract's §11 listed all eighteen
endpoints as "PF4: not yet"). What it builds on, verified with Grep on 2026-10-09:

| Area | Where | Today |
|---|---|---|
| Developer API promise | `server/app/routers/v1.py:3-4`; `src/app/developers/page.tsx:137-140` | "product endpoints (projects, assets, exports) get added here as they ship" (PF12 mirrors this feature under `/v1`) |
| Session and API-key auth | `server/app/deps.py:21-46`, `:55-110` | |
| Sign-up paths an invitation must meet | `server/app/routers/auth.py:26` (register), `:72` (Google) | no e-mail verification exists for password accounts |
| Content ownership | `src/app/terms/page.tsx:53-58` | "Designs, projects and other content you create with Truebex belong to you" |
| From PF1 (Needs) | device tokens, `author_id` (licence 5.7), entitlement feature `cloud.sync`, `contract_http.py`, `storage/`, `tasks.py`, `require_admin` | |
| From PF5 (when merged) | `server/app/uploads/` (share-bundle §5) | snapshots upload through it |

What the owner meant: app-side `00-understanding.md` §8.

## Goal

"On the phone, swap the floor finish; the operation reaches the cloud, the worker re-renders two cube faces, the panorama on the phone and the desktop app both update within seconds" (`00-understanding.md` §8). This feature is the cloud half of that sentence's first step and of "several people in one model": projects live in the cloud as a log of operations in server order, with snapshots for a fast open, named versions and restore, members with roles, presence, and quotas per tier; every replica rebuilds the same state, and a conflict is decided by the server and shown by the app.

## Read first

* **`contracts/project-log.md` v1.0.0** — the law: §4 credentials and the role matrix, §5 the eighteen endpoints, §6.2 the operation, §6.3 order and conflicts, §6.4 snapshots, §6.5 presence, §7 errors, §8 retry and `Idempotency-Key`, §9 fixtures (copied into `server/tests/contracts/project-log/`), §10 platform tests, §11 *implemented by*.
* `contracts/share-bundle.md` §5.1–5.3 (the upload protocol, purpose `snapshot`); `contracts/licence-api.md` §4 and 5.7 (`author_id`); `contracts/render-jobs.md` §2 (PF6 enqueues `tiles` jobs on pushes to followed projects).
* `contracts/agent-interface.md` v1.0.0 §5 (the log-safe tools: `place` for objects and products, `move`, `resize`, `fill`, `apply_theme`) and §6.4 (`FTruebexAgentAction` on the wire: `{tool, args, permission, session, request_id}`): the server checks an `action` operation's shape and that its tool is log-safe, and never runs it.
* `guides/GD7-*.md` is not written yet: project, byte and member quotas are placeholders `from GD7`.
* PF14 §Design, Plumbing (`storage`, `idempotency`, `uploads`, `mail`, `tasks`); skills `truebex-brand-voice` (invitation e-mail text).

## Scope

**In:**
1. Projects (contract 5.1–5.5): create from the app or the website, list owned and shared with a cursor, open (record, head, latest snapshot, members, quota), rename (owner), delete (owner, session token only, never a device token or an API key).
2. The operation log (5.6, 5.7): pushes of up to 200 operations and 16 MiB, stored append-only, contiguous `server_seq` per project under concurrent pushes, `duplicate` by `op_id`, the §6.3 conflict rule (`rejected` with up to 50 `winning` operations, the rest `not_processed`), §7 validation; pulls after a sequence number with `limit` ≤ 1000 and a long-poll of up to 25 s woken by the next push.
3. Snapshots (5.8, 5.9): a `.tbxp` and optional `.tbxpack` uploaded through the share-bundle upload protocol (purpose `snapshot`) and registered at `at_seq`; 15-minute URLs; the newest five kept plus every version's.
4. Versions and restore (5.10–5.12): a version names a snapshot at exactly its `at_seq`; restore appends a `restore` operation, which conflicts with nothing.
5. Permissions: owner, editor, viewer exactly as the §4 matrix; pushing from a device needs `cloud.sync` in the entitlement (403 `plan_required`).
6. Sharing (5.13–5.16): invite by e-mail with a role (the platform sends the e-mail with an acceptance link), change a role, remove, leave (the owner cannot leave); an invitation for an address without an account waits as `invited`.
7. Presence (5.17, 5.18): heartbeats with view, selection and soft locks, `ttl_s` 30, `leaving` on close.
8. Object storage for snapshots and assets: blobs content-addressed under `projects/{pid}/blobs/{sha256}` through the storage interface; deltas over 64 KiB kept there too (P.3 item 5: SQLite and the local filesystem until PF14).
9. Quotas per tier (projects, bytes, members): 403 `quota_exceeded` with `data.limit` and `data.used`; the limit keys `cloud_projects`, `cloud_bytes`, `project_members` proposed as a MINOR addition to `licence-api.md` §6.3.
10. A push hook (`on_ops_accepted(project_id, ops)`) that PF6 subscribes to for followed panorama sets.
11. `Idempotency-Key` on 5.1, 5.8, 5.11, 5.12 and 5.14 (24 h, §8).
12. Website pages: Projects in the dashboard (list, members, versions, restore, delete with a typed confirmation) and the invitation acceptance page.
13. Tests including a two-client reconciliation (contract §10) and a pytest for every endpoint (happy path, auth failure, validation failure).

**Out (and where it goes):**
* The delta's byte form, applying operations, rebase and the visible conflict resolution → CL1, CL2 (app).
* Rendering and following panorama sets → PF6; the web and Android light clients → PF9, PF10.
* The `/v1/projects` mirror with API keys → PF12; the tool schema inside `action` operations → `agent-interface.md` (AI1, PF12).
* Organisation-owned projects → PF3 adds `org_id` when merged (the column exists from day one, nullable).
* Server-side snapshot compaction → not planned (the app uploads snapshots, §6.4).

## Design

### API

Shapes are the contract's; this is how the platform serves them (`server/app/routers/projects.py`, service `server/app/projects/`).

| # | Endpoint | Platform behaviour |
|---|---|---|
| 5.1 | `POST /projects` | device or session; `Idempotency-Key`; quota `cloud_projects`; creates the owner membership; record per contract |
| 5.2 | `GET /projects` | owned and member-of, newest activity first; opaque cursor of (`updated_at`, `project_id`) |
| 5.3 | `GET /projects/{pid}` | viewer; record + members + `quota {bytes, bytes_used}`; 404 for non-members (no existence leak) |
| 5.4, 5.5 | `PATCH`, `DELETE /projects/{pid}` | owner; delete only with a session (403 `session_required`), soft delete, blobs purged after 30 days |
| 5.6 | `POST /projects/{pid}/ops` | one transaction that locks the project row (`SELECT … FOR UPDATE` on Postgres, `BEGIN IMMEDIATE` on SQLite); per operation in array order: `op_id` seen → `duplicate`; else any accepted operation of another replica with `server_seq > base_seq` sharing a `touched` id (index table below) → `rejected` with `winning`, the rest `not_processed`; else `server_seq = head + 1`; commit, wake the project's waiters, call the push hooks |
| 5.7 | `GET /projects/{pid}/ops` | `async` endpoint: reads after `after`; when empty waits on the project's `asyncio.Condition` up to `wait_s`, then re-reads; a 1 s re-check covers pushes on another process |
| 5.8, 5.9 | snapshots | the upload session must hold every named file complete (422 `upload_incomplete`), `at_seq ≤ head` (409 `seq_ahead`); URLs from `signed_get_url` (900 s) |
| 5.10–5.12 | versions, restore | 422 `snapshot_seq_mismatch`; restore appends `kind: "restore"` with the platform's fixed `replica_id` and the caller's `author_id` |
| 5.13–5.16 | members | an invite e-mails a link `/invite/project/?t=…`; acceptance needs a signed-in account and the token (password accounts have no e-mail verification, so a matching address alone never grants access); 409 `already_member`, 409 `owner_cannot_leave` |
| 5.17, 5.18 | presence | an in-process map keyed by (project, replica) with a 30 s TTL; the `presence` table takes over when more than one API process runs (PF14) |
| — | `POST /projects/invites/accept` | website only (session + token): attaches the invitation to the signed-in account |

### Data

| Table | Fields | Notes |
|---|---|---|
| `projects` | `project_id` (32 hex), `name` ≤ 120, `owner_user_id`, `org_id` (nullable, PF3), `doc_version`, `head_seq` BIGINT, `bytes` BIGINT, `server_replica_id`, `created_at`, `updated_at`, `deleted_at` | |
| `project_members` | `project_id`, `user_id` (null while invited), `email`, `role`, `state` active / invited, `invite_token_hash`, `invited_by`, `invited_at`, `accepted_at` | |
| `project_ops` | `project_id`, `server_seq` BIGINT (PK with project), `op_id` (unique per project), `replica_id`, `author`, `author_kind`, `kind`, `name`, `at`, `received_at`, `base_seq`, `delta_format`, `delta` BLOB ≤ 64 KiB or `delta_key`, `action` JSON, `restore` JSON | append-only; deltas over 64 KiB at `projects/{pid}/ops/{server_seq}.bin` |
| `op_touched` | `project_id`, `entity_id` CHAR(32), `server_seq`, `replica_id` | index (`project_id`, `entity_id`, `server_seq`) answers the conflict query |
| `project_snapshots` | `snapshot_id`, `project_id`, `at_seq`, `doc_version`, `tbxp_sha256`, `tbxp_bytes`, `tbxpack_sha256`, `tbxpack_bytes`, `created_by`, `created_at` | blobs under `projects/{pid}/blobs/{sha256}` |
| `project_versions` | `version_id`, `project_id`, `name`, `note`, `at_seq`, `snapshot_id`, `created_by`, `created_at` | pins its snapshot |
| `presence` | `project_id`, `replica_id`, `user_id`, `client`, `payload` JSON, `seen_at` | only with more than one API process |
| `idempotency_keys` | PF14 Plumbing | 24 h |

Bytes per project = snapshots kept + blobs + offloaded deltas, maintained on write; the owner's (or organisation's) total is checked against `cloud_bytes`.

### UI

| Page | What it shows |
|---|---|
| `src/app/dashboard/projects/page.tsx` (noindex) | projects with role, last change, size; "Shared with me" filter |
| `src/app/dashboard/projects/view/page.tsx` (`?id=`, inside `Suspense`) | head, size, members (invite, role, remove), versions (restore), Delete with the project's name typed |
| `src/app/invite/project/page.tsx` (noindex) | sign in or sign up, then Accept; the token comes from `?t=` |
| `DashboardShell.tsx` `NAV` | a Projects entry |

### Jobs / workers

| Job | Every | Does |
|---|---|---|
| `projects.snapshots.prune` | 1 h | keeps the newest five and every version's snapshot; deletes the other blobs no longer referenced |
| `projects.purge_deleted` | 24 h | removes projects deleted more than 30 days ago with their blobs |
| `projects.presence.sweep` | 10 s | drops presence older than 30 s |

### Security and privacy

* Role checks per the §4 matrix on every route; non-members get 404; a device token cannot delete (the contract's decision, so neither can an agent driving the app).
* Operations are opaque: the server never decodes a delta or runs an action; it checks sizes, ids and ordering only.
* Long-polls are `async` and capped at 20 waiting requests per account, so they never hold the synchronous worker threads the other routers use.
* Signed URLs live 15 minutes; invitation tokens are 256-bit and stored hashed; project content is the owner's (`src/app/terms/page.tsx:53-58`) and is deleted 30 days after the project is.

## Deliverables

- [x] `server/app/projects/` (`service.py`, `ops.py` with the §6.3 rule, `snapshots.py`, `members.py`, `presence.py`, `hooks.py`), `server/app/routers/projects.py`
- [x] models and settings; `server/app/uploads/` and `server/app/idempotency.py` if not yet present (PF14 Plumbing, to `share-bundle.md` §5)
- [x] mail template `project_invite`
- [x] `server/scripts/demo_replica.py`: a scripted replica (create, upload the fixture snapshot, push and pull the fixture operations) for the human test before CL1 lands
- [x] `server/tests/contracts/project-log/` copied from the app repo's fixtures (copied, never edited)
- [x] dashboard Projects pages, `/invite/project/`, `src/lib/projects.ts`
- [x] contract §11 rows and the proposed licence §6.3 limit keys recorded in As-built

## Tests

The first twelve names are the contract's §10 platform tests.

| Name | Kind | Asserts |
|---|---|---|
| `test_push_assigns_contiguous_seq` | pytest | 1..n without gaps under 8 concurrent pushers |
| `test_push_duplicate_op_id` | pytest | a repeated `op_id` → `duplicate` with its first number |
| `test_conflict_returns_winning_op_and_stops_batch` | pytest | rule 1–2: `rejected` with `winning`, later operations `not_processed` |
| `test_same_replica_never_conflicts` | pytest | rule 3, and a `restore` conflicts with nothing |
| `test_two_client_reconciliation` | pytest | two clients interleave 50 operations; both pulls end at the same head and order |
| `test_pull_long_poll_wakes_on_push` | pytest | a waiting pull returns within 1 s of a push |
| `test_roles_enforced` | pytest | the §4 matrix for viewer, editor, owner on every route |
| `test_device_token_cannot_delete_project` | pytest | 403 `session_required` for a device token and an API key |
| `test_snapshot_requires_complete_upload` | pytest | 422 `upload_incomplete` |
| `test_version_restore_appends_op` | pytest | restore gets the next number and names the version |
| `test_presence_expires_after_ttl` | pytest | gone after 30 s of fake time; `leaving` removes at once |
| `test_contract_header_and_error_envelope` | pytest | header echoed; MAJOR 2 → 400 `contract_version`; envelope with `code` and `request_id` |
| `test_projects_create_list_open` | pytest | device and session create; list shows owned and shared; 401 without credential; 422 empty name |
| `test_projects_push_requires_cloud_sync` | pytest | a Free device token → 403 `plan_required` with `data.feature` |
| `test_projects_push_validation` | pytest | unsorted `touched`, `base_seq > head`, a 5 MiB delta, `kind: "merge"`, an `action` with the non-log-safe tool `export_pdf` → 422; 201 operations → 413 |
| `test_projects_quota_exceeded` | pytest | projects, bytes and members over the tier → 403 with `data.limit`, `data.used` |
| `test_projects_snapshot_seq_ahead_and_prune` | pytest | 409 `seq_ahead`; after seven snapshots five remain plus the version's |
| `test_projects_version_snapshot_mismatch` | pytest | 422 `snapshot_seq_mismatch` |
| `test_projects_members_invite_flow` | pytest | e-mail in `mail.OUTBOX` with a token; accept needs session and token; 409 `already_member`; 409 `owner_cannot_leave` |
| `test_projects_idempotency_key_replay` | pytest | same key and body replay 5.1; another body → 409 `idempotency_mismatch` |
| `test_projects_fixture_ops_remote_replay` | pytest | the contract's `ops-remote.json` pushes through the real endpoints with numbers 1–12 |
| `test_projects_push_hook_called` | pytest | a registered hook receives exactly the accepted operations |
| `test_projects_large_delta_offloaded` | pytest | a 100 KiB delta lands in storage and pulls back byte-equal |
| `test_site_pf4_project_pages_noindex` | build check | `out/dashboard/projects/` and `out/invite/project/` carry `noindex` |
| `npm run lint`, `npm run build` | build check | green |

## Human test

1. Local API with PF1's keys and `MAIL_BACKEND=console`; the build served against it. Sign up as a@example.test and start the Pro trial on an activated device (PF1 human test steps 6–9) so the device holds `cloud.sync`.
2. Push a project from the app: in a CL1 build, File → Save to cloud; without CL1, in `server/` run `.venv\Scripts\python.exe scripts\demo_replica.py --token tbx_dev_… push --fixture tests\contracts\project-log` → "project House, head 12".
3. Dashboard → Projects lists House with role Owner, head 12 and its size.
4. Open House → Members → invite b@example.test as Editor → the invite e-mail prints in the API console with a link.
5. In a private window sign up as b and open the link → Accept → b's Projects lists House, role Editor.
6. Pull as b: a second CL1 install opens House from the cloud and shows the same model; or `demo_replica.py --token <b's device token> pull --project <id>` → 12 operations, the same order.
7. Conflict: with both replicas at head 12, a moves a wall and b moves the same wall; a pushes first → accepted 13; b's push → `rejected` naming a's operation (CL2 shows "replaced by a").
8. Versions → Name "Planning issue" (after a snapshot) → Restore → head 14, a `restore` operation in the log; presence shows both people while their windows are open.

## Risks / traps

* Long-polls on the synchronous thread pool would starve every other request: 5.7 is `async`, short queries run through `run_in_threadpool`.
* Contiguous numbers need a lock per project: SQLite gives it by serialising writers; Postgres needs the row lock (`test_push_assigns_contiguous_seq` runs on both when PF14's `TEST_DATABASE_URL` is set).
* Cloudflare closes idle connections at 100 s and limits bodies to 100 MB: pulls wait at most 25 s; pushes stay under 16 MiB; snapshots travel in 8 MiB parts.
* The upload protocol belongs to PF5 (share-bundle §11); if PF5 has not merged, this task builds `server/app/uploads/` exactly to share-bundle §5 and records it, so the merge task keeps one copy.
* An `action` operation is checked for shape only (§6.4 fields, a log-safe `tool` of `agent-interface.md` §5, ≤ 64 KiB); its arguments are validated by the kernel replicas that apply it, so a newer tool argument (a MINOR change there) needs no platform release.
* The quota keys are not in `licence-api.md` §6.3 yet: a MINOR change the owner applies there first (C.9), recorded in As-built.
* No e-mail verification exists for password accounts (`server/app/routers/auth.py:26`): invitations attach by token, never by matching address.

## As-built

* **Date, branch, commits:** 2026-10-10, `ap/t10-pf4-project-service-log-storage` (base `master` at 4758ae1):
  `ada2092` (server: the service, uploads, idempotency, jobs, fixtures, tests), `528c296` (site: Projects
  pages, invitation page, `demo_replica.py`), `0dc976d` (README, production presence backend, polish), the
  docs commit ticking this row and the review-fixes commit after it.
* **Counts:** pytest 180 → 215 collected (177 → 211 passed on SQLite; the Postgres-marked 3 → 4 skip there):
  `tests/test_projects.py` 31 (the contract's twelve §10 names, the doc's eleven PF4 names, a Postgres twin of
  `test_push_assigns_contiguous_seq`, the presence test on both backends, pull arguments and the wait cap,
  the 30-day purge, the jobs in the worker, the upload protocol for snapshots, `demo_replica.py` driven
  through the human-test path, and the review hardening), `tests/test_site_pf4.py` 4 build checks.
  **Postgres:** a disposable PostgreSQL 17.10 cluster on this PC (`initdb` in the session scratchpad, port
  55432, removed afterwards): the 4 `postgres`-marked tests pass (`test_push_assigns_contiguous_seq_postgres`:
  96 operations from 8 threads, 1..96 gap-free under the row lock); `tests/test_projects.py` with
  `TEST_APP_DATABASE_URL` (the whole app on Postgres): 31 passed; the whole suite on Postgres: 213 passed, 1
  failed — `test_billing.py::test_wayl_checkout_and_verified_webhook` (PF2's dormant Wayl rail, a 30-day
  period compared across time zones), which fails the same way on the base commit 4758ae1 with a fresh
  database, so it is not PF4's (for PF2 / the owner). **Live runs:** uvicorn on SQLite with inline jobs and console mail drove
  the whole human test with `demo_replica.py` (12 operations, the invite link printed in the API console,
  accept, pull, the long-poll woken by a's move, the conflict naming operation 13, the snapshot download
  byte-equal to the fixture, restore → head 14, the CORS preflight from the served origin, 403
  `session_required` for a device delete); headless Edge over CDP on the served `out/` (built against that
  API) listed House, showed people, versions, a desktop replica under "Here now", named and restored a
  version ("Restored. The history now ends at operation 13."), kept Delete disabled until the name was
  typed, and accepted an invitation as a second account ("You joined House as editor.", then "Shared with
  me" lists it).
* **Deviations from Design and why:**
  1. *Uploads are PF5's code.* `ap/t5-pf5-share-pages` (c1907ce) already had `server/app/uploads/` and
     `server/app/routers/uploads.py`; they are copied byte for byte so the merge keeps one copy. Only
     `uploads/jobs.py` differs (master's `@periodic` jobs take `now` and open their own session, PF14), and
     `config.share_max_bytes` is added (PF5 adds the same setting with its other share settings). Snapshots are
     copied from the account's blob (`blobs/{account}/{sha256}`) to `projects/{pid}/blobs/{sha256}`.
  2. *Fixtures authored here.* The app repo had no `Docs/roadmap/fixtures/contracts/project-log/` (CL1 makes it
     after CL0), so `server/scripts/make_project_log_fixtures.py` wrote the §9 set to the letter of the
     contract (deterministic; README in the folder): `snapshot-0000.tbxp` is today's `Z0-baseline.tbxp`,
     deltas are stand-in bytes (`TBXD` + JSON). CL1 copies the folder to the app repo or replaces it.
  3. *Invitations stay `invited` until accepted*, with `user_id` null, even for an address that has an account
     (the security rule above wins over the contract's "an invitation without an account" wording). Members
     carry an extra `invite_id` (32 hex, null once active) and 5.15 / 5.16 accept it in the `{user_id}` path
     segment, so the owner can change or withdraw a pending invitation. Proposed as a MINOR addition to
     `project-log.md` §5.13–5.16.
  4. *A person's operations carry their own `author_id`*: `author_kind: "person"` with another `author` is 422
     (`ops[i].author`), so nobody can push as someone else; agent session ids are not checked. Proposed as a
     §6.2 rule (PATCH). `demo_replica.py` rewrites the fixture's `author`; the replay test sets the user's.
  5. *Additive response keys* (readers ignore unknown keys): records carry `updated_at` (the dashboard's "last
     change") and `org_id`; a `rejected` result carries `more` (the contract's `data.more`, which a
     per-operation result has no `data` for). 5.3's `members` is the list, 5.1/5.2/5.4's the count, as written.
  6. *Plan gates.* Creating a project needs `cloud.sync` from any credential (5.1 lists `plan_required`),
     inviting needs it on the owner's plan, pushing and registering a snapshot need it only from a device
     (§4); a light client's session push needs the editor role only.
  7. *Quotas* live in `server/app/projects/quotas.py` as placeholders, not in `catalogue.json`: the licence
     fixtures and `test_catalogue` pin today's limits and §6.3 changes first (C.9). A value the owner adds to
     `catalogue.json` `limits` wins at once. `project_members` counts the owner and pending invitations;
     `cloud_bytes` counts snapshot blobs and offloaded deltas (inline deltas ≤ 64 KiB are not counted).
  8. *Idempotency* (`server/app/idempotency.py`, PF14's row): only 2xx answers are kept (an error frees the
     key, so a retry after an upgrade runs again); a second request while the first runs is 409
     `idempotency_in_progress` (`retry_after_s` 1). New code: a MINOR proposal for §7 / §8.
  9. *Limits the contract left open:* past 20 waiting pulls per account (per API process) → 429
     `rate_limited` (`retry_after_s` 5); a pull and a `winning` list stop at 16 MiB of deltas (`more: true`);
     version `name` ≤ 120, `note` ≤ 2000; the restore operation's `name` is "Restore <version>".
  10. *Production* runs two uvicorn processes, so `infra/host/compose.yaml` sets
      `PROJECTS_PRESENCE_BACKEND=db`; a push on the other process reaches a waiting pull through the 1 s
      re-check. The console mail backend now also prints the text part to stderr (the invite link shows in
      the API console).
  11. *Human test addresses:* sign-up refuses `.test` domains (`email-validator`'s special-use rule), so the
      human test uses `@example.com`.
  12. *Review hardening* (an independent review of the server diff): a push gives its pooled connection back
      while a slow client sends its body (restore reads its body before auth); `bytes` is recounted from the
      snapshots kept and the offloaded deltas under the project lock, and registering a snapshot and the prune
      job take that lock, so concurrent writes cannot lose bytes or drop a file a new snapshot names; the
      invitation mail goes out before the row is stored (503 `unavailable`, `retry_after_s` 60, when the relay
      fails, so the same Idempotency-Key retries cleanly); a replica id held by another person answers 403
      `forbidden` (5.18 lists replica ids, so nobody can end or overwrite someone else's presence); `NaN` and
      `Infinity` are refused in pushes and presence (422) so a stored operation can never break later pulls;
      a Unicode digit in a member reference is 404.
* **Contract §11 rows** for the owner to set to "PF4: done" in `contracts/project-log.md`: all eighteen —
  `POST /projects`, `GET /projects`, `GET /projects/{pid}`, `PATCH /projects/{pid}`, `DELETE /projects/{pid}`,
  `POST /projects/{pid}/ops`, `GET /projects/{pid}/ops`, `POST /projects/{pid}/snapshots`,
  `GET /projects/{pid}/snapshots/latest`, `GET /projects/{pid}/versions`, `POST /projects/{pid}/versions`,
  `POST /projects/{pid}/versions/{vid}/restore`, `GET /projects/{pid}/members`, `POST /projects/{pid}/members`,
  `PATCH /projects/{pid}/members/{user_id}`, `DELETE /projects/{pid}/members/{user_id}`,
  `PUT /projects/{pid}/presence`, `GET /projects/{pid}/presence`. `share-bundle.md` §11's `/uploads` rows stay
  PF5's (served here from PF5's module). **Licence §6.3 MINOR proposal:** limit keys `cloud_projects`
  (projects owned), `cloud_bytes` (bytes of snapshots and offloaded deltas across them) and `project_members`
  (people on one project, owner and pending invitations included), integers or null = no limit; placeholders
  Free 0 / 0 / 1, Pro 50 / 10 GiB / 5, Studio 200 / 50 GiB / 10, Team 500 / 200 GiB / 50, Enterprise null
  until GD7. **Project-log MINOR / PATCH proposals:** items 3, 4, 5, 8 and 9 above.
* **Carry-over → which feature:** PF5 merge — keep one `server/app/uploads/` (PF5's files are identical;
  keep master's `jobs.py` signature) and one `share_max_bytes` setting. PF6 — subscribe
  `app.projects.hooks.on_ops_accepted` for followed panorama sets. PF12 — mirror these routes under
  `/v1/projects` with API keys. PF3 — fill `projects.org_id`, count `cloud_bytes` per organisation, and
  extend `quotas.plan_of` with organisation seats. PF9 / PF10 — write `action` operations through 5.6 with a
  session. CL1 — the real fixtures (`snapshot-0000.tbxp` with ids, real deltas) and the app's cloud save;
  CL2 — the visible conflict resolution and presence badges. GD7 — the quota values. The owner — the
  contract's §11 and the licence §6.3 rows above, and SMTP on the VM so invitations leave the console.
* **Merged with PF3, PF3a and PF14a (2026-10-10, Autopilot T29, `ap/t29-merge-t10-pf4-project-service-lo`):**
  the conflicts were all places where both sides appended. Settings: PF3's block, then PF4's at the end of
  `config.py` and `.env.example`. `init_db` and `sqlite_to_postgres.py` import both sets of models. `main.py` has
  both sets of routers and jobs. The README has Organisations, then Cloud projects, plus both sets of env rows.
  In the dashboard nav, Projects stays in the first group, followed by PF3's Workspace switcher and Organisation
  group. `constants.ts` has `PROJECTS` and `PROJECT_INVITE`, then PF3a's `ORG_BILLING`. The console mail backend
  prints each message once, the full text on stderr, so both kinds of invite link show in the API console.
  The PF3 carry-over "extend `quotas.plan_of` with organisation seats" needed no code: `plan_of` already calls
  `seats.seat_source`, which PF3 made the best of a person's own seat and their organisation seats.
  `tests/test_projects_orgs.py` proves it: a named or floating seat opens `cloud.sync` from the site and the
  app, Team's quotas apply, and losing the seat closes the gate while the log stays. It also shows that an
  organisation invitation and a project invitation each work only at their own endpoint (404 at the other).
  One merge regression is fixed. PF3's `/invite/` layout set a plain title, which ended the root
  "%s · Truebex" template for `/invite/project/`; the layout now passes the template on
  (`test_site_pf4_invite_titles_keep_the_site_suffix`). Counts: pytest 268 passed, 4 Postgres-marked skipped.
  On Postgres 17 (`TEST_APP_DATABASE_URL` + `TEST_DATABASE_URL`) everything passes except PF2's
  `test_wayl_checkout_and_verified_webhook`, which assumes a UTC session, as on both sides before the merge.
  Still open → PF3 / PF4: `projects.org_id` and organisation-wide `cloud_bytes`. Also, `seat_source` counts a
  floating seat without a lease, so a device refused a lease (pool full, entitlement Free) can still push.
  The app follows its Free entitlement and does not try.
