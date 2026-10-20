# PF4b — The project service follows project-log 1.2.0 (CL2): comments 5.19–5.22 with the project's comment revision, `comments_rev` on presence, CL2's `comments.json` re-copied (launch priority 2)

**Needs merged:** PF4, PF4a, PF9, PF10, PF12 (all on `master` faf1686); CL2 on the app side ("collaboration: several people in one model", merged on the app repo's `main` as 8692c6ff9 on 2026-10-19 through T181). **Unblocks:** CL2 against the real API (`-mwsync=live -mwapi=<url>`), so CL2's two-PC human test; comments and presence on the web, the phone and the headset (PF9, PF10, PR5). **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\project-log.md` **1.2.0** (2026-10-19; the app side is authoritative, C.9): *Changes* 2026-10-19, §5 (5.15–5.22), §6.5, §6.6, §7, §8 "Comments (1.2.0)", §9 (`comments.json`, the `collab` script), §10 (`test_comments_roles`, `test_presence_comments_rev`). The routes now answer `X-Truebex-Contract: project-log/1.2`.

## Status

**Built 2026-10-20** on `ap/t90-pf4b-the-project-service-follows` (Autopilot T90); see As-built. What was missing on `master` faf1686 against app `main` 689da345d (both read before the work):

| # | Where (master faf1686) | Before |
|---|---|---|
| 1 | `server/tests/contracts/project-log/` | CL1's 7 files; CL2's `comments.json` (app 83fdeedad, blob 589a9e56…) missing |
| 2 | `server/app/` | no comment route, table or model: every 5.19–5.22 call answered 404, so the app keeps its comments queued and says so (the contract's *Changes*) |
| 3 | `server/app/projects/presence.py` `heartbeat` / `present` | `{"ttl_s", "others"}` and `{"present"}`, without `comments_rev` |
| 4 | `routers/projects.py`, `routers/mobile.py`, `routers/v1/projects.py` | echoed `project-log/1.1` |
| 5 | `/v1/projects` | 5.1–5.18 only; `HeartbeatResult` / `PresenceList` without `comments_rev` |
| 6 | `projects/quotas.py` `require_feature` | one message, about cloud projects, for every plan gate |

**5.15 and 5.16 against 1.2.0's wording (checked, nothing changed).** 5.15 `change_member_role` (`routers/projects.py`): the owner only (`open_project(…, "owner")`), the role `viewer` or `editor` (`members._role`, else 422), the owner's own role never changes (422 "The owner's role cannot change."), 200 with the member. 5.16 `remove_member`: the owner removes anyone else (another member: 403 `forbidden`, `needed` `owner`), a member removes themself (leave, 204), the owner leaving answers 409 `owner_cannot_leave` (`members.remove`). A demoted member's next push answers 403 because every editor route reads the live role (`service.open_project`). No rule differs from 1.2.0; `test_projects.py` already covers each.

## Goal

Several people work in one cloud project from the desktop app (CL2): they pin comments on a wall or on a view, reply, edit, resolve, reopen and delete them, and every client learns from its presence heartbeat when there is something new to fetch. The platform stores the comments outside the document and the log, enforces who may do what, numbers every change so a client never misses or repeats one, and answers the app exactly as CL2's own fixture and stub expect.

## Read first

* `docs/roadmap/40/00-contract.md` P.2–P.4; `PF4-…md` (the service), `PF4a-project-log-1-1-0.md` (the fixture copy and the `APP_BLOBS` pattern), `PF12-…md` (the `/v1` mirror and the generators).
* `project-log.md` 1.2.0, the sections named above.
* App repo, read only: `Docs/roadmap/fixtures/contracts/project-log/comments.json`; `Plugins/CADTOOL/Source/TruebexSync/Private/SyncStub.cpp` ("5.19 - 5.22 comments", about :1415–1525), `SyncCollab.cpp` (`FCadComment::FromJson` / `ToJson` / `AnchorJson`, `FetchComments`, `MergeComment`), `SyncClient.cpp` (:200 `project-log/1.2`, :362–377 the four comment calls); `Docs/roadmap/40/CL2-collaboration-several-people-in-one-model.md` (Carry-over, Human test).
* Code: `server/app/projects/ops.py` (`lock_project`), `server/app/idempotency.py`, `server/app/projects/quotas.py`, `server/app/database.py` (`_ADDED_COLUMNS`).

## Scope

**In** (nothing was cut):

1. **The fixtures.** `scripts\sync-contract-fixtures.ps1 -Contract project-log`; `comments.json` in `APP_BLOBS` (`test_pf4a_project_log_1_1.py`; CL1's commits are checked against the seven, CL2's against the eight); the folder README's row and the app commits.
2. **Storage.** A `project_comments` table and the project's comment revision as a `projects.comments_rev` column (`_ADDED_COLUMNS`; NULL = 0).
3. **5.19–5.22 on `/projects`** with §5's roles, `Idempotency-Key` on 5.20, §6.6 field for field, §7's errors, RFC 3339 UTC times with `Z`.
4. **The revision.** Every 5.20, 5.21 and 5.22 bumps it by exactly one under the project row's lock; 5.19 answers `{"comments": [...], "rev": <current>}`.
5. **`comments_rev` on presence** (5.17, 5.18): the project's current revision, 0 before any comment.
6. **The plan gate:** 5.20 from a device checks the caller's plan for `collab.live`, with its own message; 5.17 stays ungated.
7. **project-log/1.2** on `routers/projects.py`, `routers/mobile.py`, `routers/v1/projects.py`; 1.0 and 1.1 clients keep working.
8. **`/v1`:** `/v1/projects/{pid}/comments` mirrors 5.19–5.22; `HeartbeatResult` / `PresenceList` document `comments_rev`; `openapi/v1.json` (API 1.1.0), `openapi/clients.json`, the SDKs and both generated light clients regenerated.

**Out (and where it goes):**

* Comments and presence on the web, the phone and the headset: CL2's carry-over to PF9, PF10 and PR5. They start by sending `project-log/1.2` (`src/lib/app.ts`, `src/lib/projects.ts`, `api.dart`, `mobile/clients.py` `LOG`) and adding the comment routes to `openapi/clients.json`.
* Notifications (an e-mail or a push when someone comments or replies): no feature owns it yet; a later PF (the owner's call), on top of `comments.list_after`.
* Comments on the website's project pages (`/dashboard/projects/`): PF9's carry-over, with the web client's.
* The website's `collab.live` row (`src/lib/constants.ts`, `roadmap: true`): it moves only when a release with CL2 ships, the owner's release step.
* The contract's §11 platform column and the PATCH lines below: the app half updates the contract.

## Design

### API

| # | Endpoint | Auth (role) | PF4b |
|---|---|---|---|
| 5.17 | `PUT /projects/{pid}/presence` | viewer | unchanged, plus `"comments_rev": <int>`; ungated (PF9's web and PF10's Android heartbeat it, a free member's view keeps working) |
| 5.18 | `GET /projects/{pid}/presence` | viewer | `{"present": [...], "comments_rev": <int>}` |
| 5.19 | `GET /projects/{pid}/comments?after_rev=0&state=all` | viewer | `{"comments": [§6.6…], "rev": <current>}`: every comment whose latest change is after `after_rev`, in its latest state, oldest change first. `state` `open`, `resolved` or `all` (default); a tombstone (`state` `deleted`, `text` `""`) goes out with every filter and never again once `after_rev` reaches its revision. `after_rev` < 0 or an unknown `state`: 422 |
| 5.20 | `POST /projects/{pid}/comments` | viewer | `{"parent_id"?, "text", "anchor"}` → 201 the comment; `Idempotency-Key` (same key and body: the first answer; another body: 409 `idempotency_mismatch`). From a device: 403 `plan_required` without `collab.live` |
| 5.21 | `PATCH /projects/{pid}/comments/{cid}` | text: the author; state: the author, an editor, the owner | `{"text"?, "state"?: "open" \| "resolved"}` → 200 the comment |
| 5.22 | `DELETE /projects/{pid}/comments/{cid}` | the author, the owner | 204; the comment becomes a tombstone |
| all | `/v1/projects/{pid}/comments…` | `projects:read` (5.19), `projects:write` (5.20–5.22) | the same handlers; the key's owner is the author and their role applies |

**The comment** (§6.6, in the app's key order): `comment_id` (UUIDv7, 32 hex), `parent_id` (the thread's root, null on a root), `author` `{user_id, name}` (`display_name`: the account's name, else the e-mail's local part; the name at writing if the account is gone), `created_at`, `edited_at`, `text`, `state`, `resolved_by` (a user id), `resolved_at`, `anchor` `{entity, point_mm, view}` with every key present (`view` `{storey, eye_mm, yaw_deg, pitch_deg}` or null). Times RFC 3339 UTC with `Z` (`clock.rfc3339`, whole seconds, as every PF4 time).

**Rules** (the contract, then the app's stub where the contract is silent):

* Text trimmed, then 1–4000 characters (code points) → else 422 on `text`.
* A root needs an entity pin (`entity` 32 hex, optional `point_mm` of three finite numbers) or a view pin (`view.eye_mm` three finite numbers; `storey` 32 hex or null; `yaw_deg` / `pitch_deg` finite numbers, missing = 0); else 422 naming the field (`anchor`, `anchor.entity`, `anchor.point_mm`, `anchor.view`, `anchor.view.eye_mm`, …). Numbers are kept as sent; ids lower-cased.
* A reply (`parent_id`) takes its parent's anchor (its own is ignored) and hangs under the root (a reply to a reply gets the root as parent). An unknown, malformed or deleted parent: 422 on `parent_id`.
* 5.21: text by the author only (403, `data` `{role, needed: "author"}`); state by the author, an editor or the owner (a viewer on another person's comment: 403, `needed` `editor`); a text edit sets `edited_at`; `resolved` sets `resolved_by` / `resolved_at`, `open` clears them; a body with neither field: 422.
* 5.22 by the author or the owner (else 403, `needed` `owner`): `state` `deleted`, the text erased in the database.
* A deleted or unknown comment (or a malformed id) answers 404 `not_found` to 5.21 and 5.22; a non-member gets the project's 404 on every route; no credential 401. Ids in the path and `parent_id` in either case (§6.1).

### Data

* **`project_comments`** (`server/app/projects/models.py` `ProjectComment`, from `create_all`): `comment_id` (PK), `project_id` (FK `projects`, `ON DELETE CASCADE`, indexed), `parent_id`, `author_user_id` (no FK: a comment outlives its author's membership), `author_name` (the name at writing), `created_at`, `edited_at`, `text`, `state` (`open` / `resolved` / `deleted`), `resolved_by`, `resolved_at`, `anchor` (JSON), `rev`; unique `(project_id, rev)` (`uq_project_comments_rev`).
* **`projects.comments_rev`** (BIGINT, nullable; `_ADDED_COLUMNS["projects"]`, its own labelled block at the end; NULL reads 0; new projects start at 0).
* Comments are never in a snapshot, the log or a document; a member who leaves keeps their comments; `jobs.purge_project` deletes a purged project's comments (and the FK cascades).

### The revision

`comments._next_rev` begins every 5.20–5.22 with `UPDATE projects SET comments_rev = COALESCE(comments_rev, 0) + 1 WHERE project_id = … AND deleted_at IS NULL`, then reads the value back, then reads the comment (fresh, `populate_existing`), checks roles and writes it with that `rev`, and commits once. As in `ops.lock_project`, the UPDATE takes SQLite's write lock or the Postgres row lock until the commit; a second writer's UPDATE waits and then adds one to the committed value. So revisions are contiguous and never repeat, and a revision is visible only together with its change. A refused change rolls back (the revision is not spent). 5.19 reads the revision first and then the comments with `after_rev < rev ≤ that`, so a change committing in between is fetched next time rather than skipped.

### The plan gate

5.20 from a **device** (the app) checks the caller's own plan for `collab.live` (every paid tier and the trial carry it): 403 `plan_required`, `data` `{"feature": "collab.live", "plan": …}`, "Comments in the app come with live collaboration, part of a paid plan or the trial. Upgrade to comment; you can still read every comment." A session (the website, the phone) and an API key comment with the role checks only, as they push without `cloud.sync` (§4's light-client rule). 5.17, 5.18, 5.19, 5.21 and 5.22 are ungated.

### Security and privacy

Role checks on every route; 404 for non-members; a deleted comment's text is erased, not hidden; the anchor is validated (no free-form JSON beyond §6.6's keys is stored); 5.20 replays need the same account, route, key and body.

## Deliverables

- [x] `server/tests/contracts/project-log/` = the app's 8 files + README; `APP_BLOBS` += `comments.json`
- [x] `server/app/projects/comments.py` (new), `server/app/projects/{models,jobs,__init__}.py`, `server/app/database.py`
- [x] `server/app/routers/{projects,mobile}.py`, `server/app/routers/v1/{projects,models}.py`, `server/app/mobile/clients.py`, `server/scripts/export_openapi.py`
- [x] `openapi/v1.json`, `openapi/clients.json`, `sdks/` (`gen-sdks.ps1`, 1.1.0), `src/lib/api-clients.d.ts`, `mobile/android/lib/api/gen/` (`gen-clients.ps1`)
- [x] `server/tests/test_pf4b_project_log_1_2.py` (new); header and shape moves in `test_pf4a_project_log_1_1.py`, `test_projects.py`, `test_pf12_api.py`, `test_pf12a_v1_panoramas.py`
- [x] this doc, the tracker row, a README section

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_pf4b_fixture_folder_is_the_apps_eight_files` | pytest | the folder is the app's 8 files + README; `comments.json`'s blob 589a9e56…, LF; the README names 83fdeedad, 689da345d and 1.2.0; the comment pins `presence.json`'s wall; where the app repo is present, `git ls-tree` at both CL2 commits equals `APP_BLOBS` |
| `test_comments_roles` (§10) | pytest | a viewer comments and replies; text: the author only (another editor and the owner 403 `needed` `author`); state: the author, an editor (session), the owner; a viewer cannot resolve another's (403); text and state at once; an upper-case id; delete: the author or the owner (an editor and a viewer on others' 403); 404 for deleted, unknown and malformed ids on 5.21 and 5.22; 422 for `""`, whitespace, 4001 characters (4000 + whitespace passes, trimmed), no anchor (absent, null, `{}`, a point alone), an unknown, deleted or malformed parent, and bad 5.21 bodies; a non-member 404 on all four, no credential 401 |
| `test_presence_comments_rev` (§10) | pytest | 5.17 and 5.18 carry `comments_rev` 0 and nothing else changes; create, reply, edit, resolve, reopen, delete bump it 1…6 and 5.19 `after_rev` N returns exactly that change; from 0 each comment once in its latest state, oldest change first; the tombstone once, never after its rev; `state=open` and `resolved` still return the tombstone; the stored text is erased; the log stays empty; 5.19's own 422s |
| `test_pf4b_apps_comment_round_trips` | pytest | Sam (user 7, "Sam Editor", the editor) pins `comments.json`'s comment; 5.20's answer and 5.19's equal the file key for key, in its order, **`comment_id` and `created_at` masked** (minted by the server; checked as 32 hex and RFC 3339 `Z`) |
| `test_pf4b_reply_takes_its_parents_anchor_and_hangs_under_the_root` | pytest | a reply's own anchor ignored; a reply to a reply (upper-case parent id) under the root with the root's anchor; a late reply under a resolved thread starts open; a point pin, a view pin outside any storey; 10 malformed anchors each name their field (1e999 as raw JSON → `anchor.view.pitch_deg`) |
| `test_pf4b_comment_idempotency_key` | pytest | the same key and body: the same comment, the rev moved once; another body 409 `idempotency_mismatch`, rev unmoved; another key another comment; a bad key 422; a refused create keeps no key |
| `test_pf4b_comment_plan_gate` | pytest | a free viewer's device: 403 `plan_required` `{"feature": "collab.live", "plan": "free"}` with the comments message; presence and 5.19 work; the same person's session comments, then edits, resolves and deletes from the device; a paid device comments |
| `test_pf4b_comments_outlive_a_member_not_the_project` | pytest | a member who left keeps the comment with their name; the owner resolves it; a deleted project 404s at once and its purge leaves no comment row |
| `test_pf4b_comments_rev_from_before_pf4b` | pytest | `comments_rev` NULL reads 0 and the first comment gets 1; `_migrate` adds the column to a `projects` table without it |
| `test_pf4b_concurrent_comments_get_contiguous_revs` | pytest | 9 writers × 3 comments on SQLite: revs 1–27, none twice |
| `test_pf4b_concurrent_comments_postgres` | pytest (`postgres`) | 8 writers released together × 4 comments: revs 1–32; then two concurrent 5.21s on one comment take 33 and 34 |
| `test_pf4b_routes_speak_project_log_1_2` | pytest | 8 routes (`/projects`, comments, presence, members, panoramas, `/v1` record, comments, presence): no header, 1.2, 1.1, 1.0, 1.9 → 200 and `project-log/1.2`; 2.0 → 400 naming 1.2; a 1.1 client comments |
| `test_pf4b_v1_comments_mirror` | pytest | a read key cannot post or patch (403 `needed` `projects:write`); a write key comments as its owner (free plan: not gated), idempotent; list, edit, delete; presence `comments_rev` 3 on `/v1`; another account's key 404; bad state 422 |
| `test_pf4b_api_documents_name_1_2_and_comments` | pytest | `openapi/v1.json` 1.1.0 with the four operations, scopes and 1.2; `after_rev` / `state` (enum); `Comment` has §6.6's keys; `comments_rev` in both documents' presence answers; every project-log operation 1.2; the SDKs' operations, `comments_rev: number`, versions 1.1.0; the TypeScript and Dart light clients carry `comments_rev` |
| PF4, PF4a, PF9, PF10, PF12, PF12a, PF12c, PF14c suites, `test_routes_unique`, `test_site_pf4`, `test_site_pf9` | pytest | green; only the echoed header (and two presence shapes) moved |

## Human test

About 10 minutes, in Windows PowerShell, on a local API. The served site (`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1`) is needed only for step D2.

**A. Two accounts on one project**

0. In the worktree: `cd server`. If `server\.env` has no `LICENCE_SIGNING_KEY` yet, run `.venv\Scripts\python.exe scripts\make_signing_key.py --kind lic` and paste its `LICENCE_SIGNING_KEY=` and `LICENCE_KEY_ID=` lines into `server\.env`. Start the API in its own window: `.\run.bat` (http://127.0.0.1:8000). Keep that window visible: invitation e-mails print there. Back in the first window (still in `server\`):
   ```powershell
   $api = 'http://127.0.0.1:8000'
   $ana = (Invoke-RestMethod -Method Post "$api/auth/register" -ContentType 'application/json' -Body '{"email":"ana@example.com","password":"password123"}').access_token
   $sam = (Invoke-RestMethod -Method Post "$api/auth/register" -ContentType 'application/json' -Body '{"email":"sam@example.com","password":"password123"}').access_token
   .venv\Scripts\python.exe scripts\demo_replica.py login --email ana@example.com --password password123 --trial
   ```
   → "Pro trial started (ends …)", "device DEMO-REPLICA for ana@example.com: plan pro, …".
1. Ana makes a project and invites Sam as a viewer:
   ```powershell
   $A = @{ Authorization = "Bearer $ana"; 'X-Truebex-Contract' = 'project-log/1.2' }
   $S = @{ Authorization = "Bearer $sam"; 'X-Truebex-Contract' = 'project-log/1.2' }
   $p = (Invoke-RestMethod -Method Post "$api/projects" -Headers $A -ContentType 'application/json' -Body '{"name":"House","doc_version":55}').project_id
   Invoke-RestMethod -Method Post "$api/projects/$p/members" -Headers $A -ContentType 'application/json' -Body '{"email":"sam@example.com","role":"viewer"}' | Format-List email, role, state
   ```
   → `email : sam@example.com`, `role : viewer`, `state : invited`; the API window prints the invitation e-mail with a link ending `/invite/project/?t=<token>`.
2. Sam accepts: `$t = '<the token after t=>'`, then `(Invoke-RestMethod -Method Post "$api/projects/invites/accept" -Headers $S -ContentType 'application/json' -Body (@{ token = $t } | ConvertTo-Json)).member | Format-List email, role, state` → `role : viewer`, `state : active`.

**B. Comments and their revision**

3. Sam's heartbeat: `$beat = '{"replica_id":"5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a","client":"web"}'`, then `Invoke-RestMethod -Method Put "$api/projects/$p/presence" -Headers $S -ContentType 'application/json' -Body $beat | ConvertTo-Json -Compress` → `{"ttl_s":30,"others":[],"comments_rev":0}`.
4. Sam (a viewer) pins a comment on a wall:
   ```powershell
   $key = @{ 'Idempotency-Key' = 'aaaaaaaabbbbbbbbccccccccdddddddd' }
   $body = '{"text":"Does the kitchen still fit?","anchor":{"entity":"dc643577cfb582fabd0d7f9edef6b30d"}}'
   $c = Invoke-RestMethod -Method Post "$api/projects/$p/comments" -Headers ($S + $key) -ContentType 'application/json' -Body $body
   $c | ConvertTo-Json -Depth 5 -Compress
   ```
   → one line: `"parent_id":null`, `"author":{"user_id":2,"name":"sam"}`, `"created_at":"…Z"`, `"text":"Does the kitchen still fit?"`, `"state":"open"`, `"anchor":{"entity":"dc643577…","point_mm":null,"view":null}`. The same command again (`(Invoke-RestMethod -Method Post "$api/projects/$p/comments" -Headers ($S + $key) -ContentType 'application/json' -Body $body).comment_id`) prints the same `comment_id` (the key replays).
5. Ana replies: `$r = Invoke-RestMethod -Method Post "$api/projects/$p/comments" -Headers $A -ContentType 'application/json' -Body (@{ parent_id = $c.comment_id; text = 'Yes, with 40 mm to spare.' } | ConvertTo-Json)`; `$r.parent_id; $r.anchor | ConvertTo-Json -Compress` → Sam's `comment_id` and the same wall anchor.
6. Ana resolves Sam's comment: `Invoke-RestMethod -Method Patch "$api/projects/$p/comments/$($c.comment_id)" -Headers $A -ContentType 'application/json' -Body '{"state":"resolved"}' | Format-List state, resolved_by, resolved_at` → `resolved`, `1`, a time ending `Z`.
7. Sam may not edit Ana's reply: `try { Invoke-RestMethod -Method Patch "$api/projects/$p/comments/$($r.comment_id)" -Headers $S -ContentType 'application/json' -Body '{"text":"Mine now"}' } catch { $_.ErrorDetails.Message }` → `{"detail":"Only the comment's author can change its text.","code":"forbidden","status":403,…,"data":{"role":"viewer","needed":"author"}}`.
8. Sam deletes his comment: `Invoke-RestMethod -Method Delete "$api/projects/$p/comments/$($c.comment_id)" -Headers $S` → no output (204).
9. 5.19 from 0: `$list = Invoke-RestMethod "$api/projects/$p/comments?after_rev=0" -Headers $S; "rev $($list.rev)"; $list.comments | Format-Table comment_id, parent_id, state, text -AutoSize` → `rev 4`, then Ana's reply (`open`, "Yes, with 40 mm to spare.") and Sam's comment as `deleted` with no text.
10. Presence moved with it: `(Invoke-RestMethod -Method Put "$api/projects/$p/presence" -Headers $S -ContentType 'application/json' -Body $beat).comments_rev` → `4`; `(Invoke-RestMethod "$api/projects/$p/presence" -Headers $A).comments_rev` → `4`. Nothing new after 4: `Invoke-RestMethod "$api/projects/$p/comments?after_rev=4&state=open" -Headers $S | ConvertTo-Json -Compress` → `{"comments":[],"rev":4}`.
11. The deleted comment is gone for edits: `try { Invoke-RestMethod -Method Patch "$api/projects/$p/comments/$($c.comment_id)" -Headers $A -ContentType 'application/json' -Body '{"state":"open"}' } catch { $_.ErrorDetails.Message }` → `{"detail":"No such comment.","code":"not_found","status":404,…}`.

**C. The plan gate, old clients, `/v1`**

12. Sam on the app without a paid plan: `$out = .venv\Scripts\python.exe scripts\demo_replica.py login --email sam@example.com --password password123; $out` → "… plan free …"; then `$sd = ($out | Select-String 'device token: (\S+)').Matches[0].Groups[1].Value; $D = @{ Authorization = "Bearer $sd"; 'X-Truebex-Contract' = 'project-log/1.2' }` and `try { Invoke-RestMethod -Method Post "$api/projects/$p/comments" -Headers $D -ContentType 'application/json' -Body $body } catch { $_.ErrorDetails.Message }` → `"code":"plan_required"`, `"data":{"feature":"collab.live","plan":"free"}`, "Comments in the app come with live collaboration…". `(Invoke-RestMethod "$api/projects/$p/comments?after_rev=0" -Headers $D).rev` → `4` (reading is not gated).
13. A 1.1 client: `curl.exe -s -i "$api/projects/$p/comments" -H "Authorization: Bearer $sam" -H "X-Truebex-Contract: project-log/1.1" | Select-String -Pattern '^HTTP/|x-truebex-contract'` → `HTTP/1.1 200 OK` and `x-truebex-contract: project-log/1.2`.
14. `/v1` with an API key: `$k = Invoke-RestMethod -Method Post "$api/keys" -Headers @{ Authorization = "Bearer $sam" } -ContentType 'application/json' -Body '{"name":"pf4b","scopes":["projects:read","projects:write"]}'; $K = @{ Authorization = "Bearer $($k.key)" }`, then `(Invoke-RestMethod -Method Post "$api/v1/projects/$p/comments" -Headers $K -ContentType 'application/json' -Body '{"text":"Through the API","anchor":{"view":{"storey":null,"eye_mm":[4200,1800,1600],"yaw_deg":90,"pitch_deg":-10}}}').author` → `user_id 2`, `name sam`; `(Invoke-RestMethod "$api/v1/projects/$p/presence" -Headers $K).comments_rev` → `5`.

**D. Optional**

15. *With the app.* Push the app's fixture project as Ana: `.venv\Scripts\python.exe scripts\demo_replica.py --token <Ana's tbx_dev_ token from step 0> push --fixture tests\contracts\project-log` → "project House (fixture), head 12" and "project id: …"; `$p2 = '<that id>'`, then invite and accept Sam on `$p2` as in steps 1–2 (with `$p2` for `$p`). Start a CL2 development build with `-mwsync=live -mwapi=http://127.0.0.1:8000` (CL1's live switches; CL2's human test) and sign in to this API as ana@example.com (on the trial, so `collab.live`). File > Open from Cloud… > "House (fixture)", select a wall, Comment (CMT), type "Check this wall", Enter. Then as Sam: `(Invoke-RestMethod "$api/projects/$p2/comments?after_rev=0" -Headers $S).comments | Format-Table text, state, parent_id` → "Check this wall", `open`, no parent; `(Invoke-RestMethod -Method Put "$api/projects/$p2/presence" -Headers $S -ContentType 'application/json' -Body $beat).comments_rev` → `1`.
16. *The developer reference.* With the site served (`scripts\autopilot-serve.ps1`), open `/developers/projects/`: four new operations, `projects_list_comments`, `projects_create_comment`, `projects_update_comment`, `projects_delete_comment`, with their scopes.

## Risks / traps

* **The app checkout is CRLF**: the sync script copies the blobs (the folder keeps `-text`, the committed ids are the app's).
* **5.19 has no paging** (the contract has none): a project with thousands of changed comments answers them in one list. Fine at review scale; a `limit` / `more` is a MINOR for the contract if it ever matters.
* **The comment revision shares the project row's lock with pushes**: a comment written during a large push (up to 16 MiB) waits for that push's commit. Short in practice; a separate counter row would decouple them at the cost of a second lock order.
* **Generated files**: PF7e (marketplace-api 1.2.0) runs beside this and may also regenerate `openapi/v1.json`, `openapi/clients.json`, the SDKs and the clients. At merge, re-run `server\scripts\export_openapi.py --v1` / `--clients`, `scripts\gen-sdks.ps1` and `scripts\gen-clients.ps1` instead of hand-merging generated files. Seen on PF7e's branch (read only, 2026-10-20): it changes `CONTRACTS`' `market` / `feeds` lines (apart from this task's `projects` line) and does not bump `API_VERSION`, so `export_openapi.py` merges by itself and the merged API is 1.1.0.
* **The verify gate's `test_market.py::test_categories_root_on_app_taxonomy` fails on `master` too** (As-built).

## As-built

* **Date, branch, commits:** 2026-10-20, `ap/t90-pf4b-the-project-service-follows` from `master` faf1686 (Claude Autopilot T90): `0d34382` (tests first: the fixtures, `test_pf4b_project_log_1_2.py`, the header moves), `8968e7e` (the service, routes, `/v1`, the regenerated documents, SDKs and clients), then this doc, the tracker row and the README section.
* **Copy:** `scripts\sync-contract-fixtures.ps1 -Contract project-log` from app `main` 689da345d: 8 files, `comments.json` new (the script lists it as "updated"), the other seven unchanged; every blob id equal to the app's. `comments.json` first appeared in CL2's 83fdeedad (on `main` since 8692c6ff9).
* **Scope 2 (storage): a `projects.comments_rev` column**, not a counter row: the project row is already the lock that orders the log (`ops.lock_project`), so comments take the same proven pattern; 5.17 / 5.18 / 5.19 read one column of a row they already open; a deleted project needs no second cleanup. Added through `_ADDED_COLUMNS` (`BIGINT`, NULL = 0) for existing databases; `create_all` makes `project_comments`.
* **Scope 6 (the gate): 5.20 from a device needs `collab.live` on the caller's own plan**, as a push from a device needs `cloud.sync`; a session (web, phone) and an API key are not gated, like their pushes (§4). The message is the comments' own (`comments.require_collab`). **5.17 stays ungated**, and so do 5.18, 5.19, 5.21 and 5.22 (a member whose plan lapsed still reads, resolves and deletes; the contract names only 5.17 / 5.20).
* **Scope 7 (versions): the routes answer `project-log/1.2`** (`routers/projects.py`, `routers/mobile.py`, `routers/v1/projects.py`); any 1.x is served. **`mobile/clients.py` `LOG` stays `project-log/1.1`, and the web and Android keep sending 1.1**: they call no comment route and read nothing 1.2 adds, and `openapi/clients.json` names what the light clients speak. Its presence answers document `comments_rev` as an optional integer (`test_pf10_clients.py` checks the real answers name every key), so the generated Dart (`presence_answer.dart`, `presence_list.dart`, `SPEC_SHA256`) and TypeScript (`api-clients.d.ts`) clients were regenerated. The developer docs' header example in `src/lib/constants.ts` still says 1.1 (a header a client may send; not edited, merge hygiene).
* **Scope 8 (`/v1`): mirrored**, `projects_list_comments` (`projects:read`), `projects_create_comment`, `projects_update_comment`, `projects_delete_comment` (`projects:write`), the key's owner as the author with their member role, the idempotency scope `v1.projects.comments`; `HeartbeatResult` / `PresenceList` document `comments_rev`; schemas `Comment`, `CommentAuthor`, `CommentAnchor`, `CommentView`, `CommentList`, `CommentCreate`, `CommentUpdate`. `API_VERSION` 1.0.0 → **1.1.0** with `sdks/js/package.json`, `sdks/python/pyproject.toml` and `_version.py`; `gen-sdks.ps1` and `gen-clients.ps1` regenerated the rest. `/developers/projects/` lists the four operations from `v1.json`.
* **Where the server differs from the app's stub** (each on the lenient or stricter-but-unused side): (1) 5.21 with neither `text` nor `state` is 422 (the stub bumps the rev and changes nothing); (2) 5.19 with an unknown `state` or a negative `after_rev` is 422 (the stub returns only tombstones); (3) the text's length is checked after trimming, in code points (the stub refuses a raw UTF-16 length over 4000), so everything the stub takes is taken; (4) a malformed anchor part (an entity that is not 32 hex, a point that is not three finite numbers, a view without `eye_mm`) is 422 naming the field (the stub ignores a bad entity beside a view and reads a missing eye as 0, 0, 0); missing `yaw_deg` / `pitch_deg` read 0 as in the stub; (5) a view's numbers are kept as sent (the stub rounds them to 0.1 when it answers); (6) a reply's `anchor` must still be an object or absent (the stub ignores anything); (7) 5.22's 204 carries no `X-Truebex-Contract`, like PF4's other 204s (5.5, 5.16); (8) ids in either case (§6.1).
* **Tests moved** (only the echoed header, and the two exact presence shapes that gained `comments_rev: 0`): `test_projects.py` (`test_contract_header_and_error_envelope` 3 lines, `test_presence_expires_after_ttl` 2 shapes), `test_pf4a_project_log_1_1.py` (`APP_BLOBS` + `comments.json`, CL1's commits compared with `CL1_BLOBS`; 5 header lines; `test_pf4a_api_documents_name_1_1_and_id` now expects 1.2 in `v1.json` and 1.1 in `clients.json`), `test_pf12_api.py` (1), `test_pf12a_v1_panoramas.py` (2). Read and unchanged, green: `test_projects_orgs.py`, `test_mobile.py`, `test_pf9_pf12_meet.py`, `test_pf10_clients.py`, `test_pf12_openapi_sdks.py`, `test_pf12c_agent_interface.py`, `test_site_pf4.py`, `test_site_pf9.py`.
* **Counts:** pytest collected 886 → 900 (14 new, all in `test_pf4b_project_log_1_2.py`). **Tests first:** the 14 on faf1686's `server/` (with its 7-file folder): 13 failed and the Postgres one failed too with `TEST_DATABASE_URL` (no `comments` module). With a naive read-then-write revision (`-p naive_rev_plugin`), both concurrency tests fail on `uq_project_comments_rev` (SQLite and Postgres). The touched suites on SQLite (16 files, with the gate's `out/`): 144 passed, 3 skipped (Postgres-only).
* **Postgres 17** (throwaway cluster, session zone Asia/Baghdad, `TEST_APP_DATABASE_URL` + `TEST_DATABASE_URL`): `test_pf4b_project_log_1_2`, `test_pf4a_project_log_1_1`, `test_projects`, `test_projects_orgs`, `test_mobile`, `test_pf9_pf12_meet`, `test_pf10_clients`, `test_pf12_api`, `test_pf12_openapi_sdks`, `test_pf12a_v1_panoramas`, `test_pf12c_agent_interface`, `test_pf14c_utc_times`, `test_routes_unique`: 128 passed, 2 skipped, 271 s; `test_pf4b_concurrent_comments_postgres` 5 runs of 5 green.
* **Self-test** (a real uvicorn on 127.0.0.1:18090, a scratch SQLite database and storage, a throwaway licence key, console mail), the human test's PowerShell lines run literally: Ana's trial ("Pro trial started (ends 2026-11-03T08:19:26Z)"), project `01a15864daf977a681cb8eebeced1f84`, Sam invited as viewer and accepted from the console link. Answers:
  * 5.17 before: `{"ttl_s":30,"others":[],"comments_rev":0}`
  * 5.20 (Sam, viewer, with a key): `{"comment_id":"01a1586523427730bbddfe59ceba4931","parent_id":null,"author":{"user_id":2,"name":"sam"},"created_at":"2026-10-20T08:19:45Z","edited_at":null,"text":"Does the kitchen still fit?","state":"open","resolved_by":null,"resolved_at":null,"anchor":{"entity":"dc643577cfb582fabd0d7f9edef6b30d","point_mm":null,"view":null}}`; again with the key: the same id
  * reply (Ana): `parent_id 01a1586523427730bbddfe59ceba4931`, the same wall anchor; resolve: `state resolved`, `resolved_by 1`, `resolved_at 2026-10-20T08:19:46Z`
  * Sam editing Ana's reply: `{"detail":"Only the comment's author can change its text.","code":"forbidden","status":403,…,"data":{"role":"viewer","needed":"author"}}`; Sam's delete: 204
  * 5.19 `after_rev=0`: `rev 4`; `01a15865247c77ed… 01a1586523427730… open "Yes, with 40 mm to spare."` and `01a1586523427730… deleted` (no text)
  * 5.17 → `4`, 5.18 → `4`; 5.19 `after_rev=4&state=open` → `{"comments":[],"rev":4}`; PATCH of the deleted one → `{"detail":"No such comment.","code":"not_found","status":404,…}`
  * a 1.1 client: `HTTP/1.1 200 OK`, `x-truebex-contract: project-log/1.2`
  * Sam's free device: `{"detail":"Comments in the app come with live collaboration, part of a paid plan or the trial. Upgrade to comment; you can still read every comment.","code":"plan_required","status":403,…,"data":{"feature":"collab.live","plan":"free"}}`; its heartbeat `comments_rev` 4 and its 5.19 `rev` 4
  * `/v1` with Sam's key: author `user_id 2`, `name sam`, the view anchor as sent; `/v1` 5.19 `after_rev=4` → that comment, `rev 5`; `/v1` 5.18 `comments_rev` 5
  * no traceback in the API log.
* **Verify gate** (`scripts/autopilot-verify.ps1` on `8968e7e`): lint and build green; pytest 880 passed, 19 skipped, **1 failed of 900, not this feature's**: `test_market.py::test_categories_root_on_app_taxonomy` compares the platform's copy of the app's taxonomy (`server/app/market/taxonomy/categories.json`) with the live app checkout, and the app's `main` changed that file in 83ca33a3c (MD5, 2026-10-17: `outdoor` aligns `OnTerrain`, three more tags); MK4 (123b88c59) re-wrote the app's marketplace fixtures for it (`taxonomy_sha256` 57e1159e…). The same test fails on faf1686's `server/` (checked); PF4b touches nothing under `server/app/market/`. Re-copying the taxonomy alone would break PF7c's D16 check against the current marketplace fixtures, so the fix is the marketplace re-copy (PF7e, marketplace-api 1.2.0, running beside this task: its branch's 0632238 re-copies `categories.json` with the app's fixtures at 123b88c59). Gate time 671 s (pytest 594 s). Autopilot's own gate run (2026-10-20 08:46) failed on the same single test.
* **Fix attempt 1 (2026-10-20), tried and reverted:** the app's checkout `CAD/taxonomy/categories.json` copied over `server/app/market/taxonomy/categories.json` and `make_market_fixtures.py` re-run (PF7's 5.1 answer then carries `57e1159e…`): `test_market.py` passes, but `test_market_contract_fixtures.py::test_categories_like_the_stub` (PF7c's D16) fails, `57e1159e…` against the copied set's `7720dcfb…`; the other 59 marketplace tests pass. The taxonomy and the marketplace contract set (36 files pinned at one app commit, products, prices and 1.2.0 orders included) only agree once both are re-copied to app main 689da345d, which is all of PF7e. Neither check may be weakened, and copying PF7e's four commits here would ship marketplace-api 1.2.0 under PF4b's name, so the order is the owner's call (final report). `git merge-tree` of this branch with PF7e's (read only): conflicts only in `README.md` and `docs/roadmap/40/README.md` (both end-of-file appends); `openapi/v1.json`, the SDKs' operations and `export_openapi.py` merge cleanly.
* **Decision (2026-10-20, unattended; the recommended option): merge PF7e (T91) first.** PF4b carries no marketplace change; once PF7e is on `master`, Autopilot's merge of `master` into this branch brings the re-copied taxonomy and marketplace set, and the gate's last red test turns green. Checked before relying on it: the read-only merge tree of this branch and PF7e's (`git merge-tree --write-tree`, d6494a72; only the README and tracker hold conflict markers) ran the whole pytest suite with this branch's venv: 802 passed, 113 skipped (the site build checks without `out/` or `node_modules`, the Postgres-only tests), **0 failed**. `test_categories_root_on_app_taxonomy`, PF7c's `test_categories_like_the_stub`, `test_pf7e_marketplace_1_2.py`, `test_pf4b_project_log_1_2.py` and both generated-document drift checks (`test_pf12_openapi_sdks.py`, `test_pf10_clients.py`) passed there: the auto-merged `openapi/v1.json` and SDK operations equal a fresh export. At that merge, put the PF4b and PF7e README sections and tracker rows one after the other (no regeneration needed).
* **Gate re-run 2026-10-20 09:22 (Autopilot), the same single failure; `master` still faf1686, PF7e not merged.** Tried to carry PF7e's two code commits here (`git cherry-pick -x 4c1a1c1 0632238`, leaving its doc and tracker row on its branch): the Autopilot guard refuses `git cherry-pick` in a task run, as it refuses merge and rebase. Copying PF7e's files in some other way would get around that guard, and a hand-made marketplace re-copy needs PF7e's 1.2.0 order code as well (the app's new order fixtures are 1.2.0-shaped), so it would be PF7e done twice. The gate on this branch turns green only when PF7e is on `master` and Autopilot merges `master` in.
* **Decision, again unattended (2026-10-20): merge T91 (PF7e) first**, the recommended option over "accept the red test" and "redo PF7e here". PF4b is complete; its one red gate test is external and goes when T91 lands on `master`. Rechecked then: `master` still faf1686; `test_pf4b_project_log_1_2.py` + `test_pf4a_project_log_1_1.py` 27 passed, 1 skipped (Postgres-only); `test_categories_root_on_app_taxonomy` still the single failure.
* **CL2's carry-over "PF4: the server side of 5.15–5.22" is done** (5.15–5.18 checked against 1.2.0, 5.19–5.22 built). Its other half (PF9 / PF10 / PR5: presence and comments on the web, the phone and the headset) stays theirs.
* **Proposed §11 platform cells** (`contracts/project-log.md`; the app half updates the contract): `PATCH /projects/{pid}/members/{user_id}`, `DELETE /projects/{pid}/members/{user_id}`, `PUT /projects/{pid}/presence` (with `comments_rev`), `GET /projects/{pid}/presence` (with `comments_rev`): "PF4: implemented (2026-10-10; 1.2.0 checked by PF4b 2026-10-20)"; `GET /projects/{pid}/comments`, `POST /projects/{pid}/comments`, `PATCH /projects/{pid}/comments/{cid}`, `DELETE /projects/{pid}/comments/{cid}`: "PF4b: implemented (2026-10-20)"; the other fourteen rows as PF4a proposed ("PF4: implemented (2026-10-10; 1.1.0 PF4a 2026-10-15)"); all mirrored under `/v1/projects` for API keys (PF12, comments PF4b). The header's status → "platform implemented (PF4, 1.1 PF4a, 1.2 PF4b)".
* **Contract lines for the app side** (PATCH = wording):
  * **5.19 (PATCH):** "A `state` filter never hides a deleted comment: its tombstone goes out once with every filter (as the stub does). An unknown `state` or a negative `after_rev` is 422 `validation_failed`."
  * **5.19 (PATCH):** "Each comment comes back in its latest state, once, at the revision of its latest change; `rev` is read before the comments, so a change made meanwhile comes with the next fetch."
  * **5.20 (PATCH):** "`text` is trimmed, then 1–4000 characters. A reply's own `anchor` is ignored; a reply to a reply hangs under the root. A deleted parent is 422. A view pin needs `view.eye_mm`; missing `yaw_deg` / `pitch_deg` read 0."
  * **5.21 (PATCH):** "A body with neither `text` nor `state` is 422."
  * **§7 5.20 (PATCH):** "A server answers 403 `plan_required` to a device without `collab.live`; a session (web, phone) and an API key comment with the role checks only, as they push (§4)."
  * **§4 (PATCH):** the role matrix gains the comment rows of §5 (read and comment: viewer; text: author; state: author, editor, owner; delete: author, owner).
* **Carry-over → which feature:** PF9 / PF10 / PR5 — comments and presence on the web, the phone and the headset (send `project-log/1.2`, add the comment routes to `openapi/clients.json`, show `comments_rev`); the owner — the §11 cells and contract lines above, the optional app step 15, a notifications feature if wanted; PF7e — the marketplace re-copy that turns `test_categories_root_on_app_taxonomy` green; PF12 — no MCP tool for comments (agent-interface names none) and no webhook event for them (`webhooks/events.py` names none; a MINOR when a consumer wants one).
