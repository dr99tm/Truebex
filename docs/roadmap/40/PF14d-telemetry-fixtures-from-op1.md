# PF14d — Telemetry fixtures re-copied from OP1, and an e-mail in feedback text refused (launch priority 2)

**Needs merged:** PF14 (on `master`); OP1 (app; landed on the app repository's `main` 2026-10-13 03:42 UTC, commit `90799860`, Autopilot T158). **Unblocks:** the contract's §11 platform rows for the five telemetry endpoints, now tested against what the app really sends; OP1's human-test step 6 (the message reaches the platform's inbox). **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\telemetry.md` 1.0.1 (C.9). The contract file is unchanged here; the PATCH lines for the app side to write are in the As-built.

## Status

**Built (2026-10-13, branch `ap/t65-pf14d-telemetry-fixtures-re-copi`, Autopilot T65); see As-built.** Checked on `master` 9dac34b before the work began (the manager's checks, read-only, then confirmed here):

| # | Where | Before |
|---|---|---|
| 1 | `server/tests/contracts/telemetry/` | PF14's own set (As-built deviation 1: "OP1 copies it to the app repo or replaces it, after which it is re-copied"). OP1 replaced it. As committed on the app's `main`, `config.json` and `config-off.json` were already identical (the "line endings" difference is the app checkout's `core.autocrlf=true`); the other eight files differed; `scrub-context.json` was new |
| 2 | `server/app/telemetry/scanner.py:168` `scan_feedback` | skipped `text` (PF14 deviation 2's proposal, which the app's 1.0.1 PATCH did not adopt): the app's case `email-in-feedback-text` was accepted. The other 8 of the 9 privacy cases were refused naming the case's field |
| 3 | `scanner.py:72` `scrub_log` | no context: it could not reproduce the app's `log-tail-scrubbed.txt` (the machine, the user and the project folders); it did leave the app's scrubbed tail unchanged, so the app's tails were accepted |
| 4 | `server/app/telemetry/service.py:214` `install_id_from_secret` | SHA-256 over the secret's 32 **raw bytes**; OP1 hashes the 64 hex characters, so 5.5 derived a different id from the one on the app's events and deleted none of them |
| 5 | `service.py:311-321` (allow-list), `scanner.py:113-134` (enums), `service.py:129` (`FeedbackIn.kind`) | exact-case matches; a Shipping build can send `Warning`, `Command`, `Bug` (see Design) |
| 6 | `server/app/telemetry/jobs.py:263-267` | symbol tables keyed by the code file (`truebex-win64-shipping.exe`); OP1's frames name the module without its extension, so its crashes could never be named from the callstack |

## Goal

The platform's telemetry tests run against the fixtures the app itself tests with, so a green suite means the real app's events, crash reports and feedback are accepted as sent and its privacy cases are refused as the app expects. An e-mail address in feedback text is refused, as the app's fixture says. Every place where the app's payloads and the server's rules disagree is found, fixed on the server where the contract allows, and written down for the app side where it does not.

## Read first

* `docs/roadmap/40/00-contract.md` (P.2-P.4); PF14's doc (Design "API", As-built deviations 1 and 2, Tests).
* `contracts/telemetry.md` 1.0.1 in full (§3 Changes, §4, §5.2-5.5, §6.3, §6.4, §7, §9).
* The app's fixtures, `Docs/roadmap/fixtures/contracts/telemetry/`, and its client, read-only: `Plugins/CADTOOL/Source/TruebexTelemetry/` (`TelemetryPrivacy.cpp` scrubber and scanner, `TruebexTelemetry.cpp` payload builders, `TelemetryCrash.cpp` frames, `TelemetryPlatform.cpp` multipart, `TelemetryStub.cpp`); the OP1 doc's Scope and As-built.
* `server/app/telemetry/{scanner,service,jobs,symbolicate}.py`, `server/tests/test_telemetry.py`.

## Scope

**In:**

1. `scripts/sync-contract-fixtures.ps1 -Contract <name>`: copies a contract's fixtures from the app repository as committed on `main` (read-only git), checks every copy's blob id against the app's, keeps the folder's README. The telemetry set copied with it.
2. `test_telemetry.py` on the app's set: 5.2, 5.3 and 5.4 accept the fixture payloads end to end, sent as the app builds them (multipart parts byte for byte); every `privacy-violations.json` case answers 422 `privacy_violation` with `data.field` equal to the case's field; the scrubber, given `scrub-context.json`, turns `log-tail-raw.txt` into `log-tail-scrubbed.txt` exactly; production keeps the context-free scrubber, refuses a tail it would change and accepts the app's scrubbed tail.
3. Feedback text: an e-mail-shaped string answers 422 `privacy_violation` naming `text`. Path separators stay allowed (decision below). The reply flow is unchanged.
4. Every place where the app's payloads meet a request model or rule the server refuses: follow the app unless the contract says otherwise; record each difference, and a PATCH line where the contract is silent.
5. PF14 deviation 2's other readings: which the app shares and which differ; the identity rules change only where the app's code shows a different reading and the contract text supports it.

**Out (and where it goes):**

* Writing `telemetry.md` (the PATCH lines and the §11 platform rows): the app side / the owner at merge (P.3 item 4).
* The app's own fixes found here (feedback text and log part cut after scrubbing; enum and key spelling in Shipping): OP1 carry-over, in the As-built.
* The other contracts' fixture folders: the script works for them, but re-copying them is each contract's follow-up.
* Public copy: none. The privacy page's account of what feedback holds is unchanged (the app already replaced addresses in the message before this feature).

## Design

### Fixtures and the copy script

`scripts/sync-contract-fixtures.ps1` runs `git rev-parse`, `git ls-tree` and `git -c core.autocrlf=false archive --format=zip` in the app repository (read-only; the archive goes to `%TEMP%`), expands it, copies each file over `server/tests/contracts/<name>/`, compares `git hash-object --no-filters` of every copy with the app's blob id (it stops on a mismatch), removes files the app no longer has (never `README.md`), and prints the app commit. It reads blobs, not the app's working tree, because that checkout has `core.autocrlf=true`: the working tree holds CRLF copies of LF files. `.gitattributes` already keeps `server/tests/contracts/**` as `-text`.

### Privacy rules (§6.4), app and server

| Rule | OP1 (`TelemetryPrivacy.cpp`) | Server before | Server now |
|---|---|---|---|
| e-mail-shaped string | anywhere in every payload, feedback `text` included | anywhere but feedback `text` | anywhere, feedback `text` included (422 naming `text`, `data.reason` `email`) |
| path separator | every string except the `schema` id, feedback `text` and a crash `message` | event prop values, `callstack`, `exception` | unchanged |
| prop value types | enum / version token `[A-Za-z0-9_.+-]{1,64}`, Unicode letters too; integers; booleans | token had to start with an ASCII letter or digit; listed enums exact-case | token `[\w.:+-]{1,64}` (the app's set plus `:`); enums, names and keys without case |
| log tail | scrubbed with the machine's context before it is shown or sent | refused when the context-free scrubber would change it | the same check, now with the app's own scrubber rules |

**Decision: path separators in feedback text stay allowed.** §6.4's scanner sentence scopes the separator rule to "a path separator in a prop value" (1.0.1 adds callstack frames on the app side); the e-mail rule is unscoped ("an email-shaped string"). A person's message is not a prop value, and people write "and/or", "1/2", "3/4 inch". The app agrees: its scanner exempts feedback `text` from the separator rule ("Free text a person typed (feedback) may hold a slash; never an email"), and its scrubber already replaces project paths and file names in the text before sending.

What the app really does with an address typed into Help > Send feedback...: `SendFeedback` runs the text through the log scrubber (`ScrubLive`), so the address leaves as `<email>`, and the dialog says so ("Email addresses, file names and folders in your message and the log are replaced before sending"). Its scanner would refuse a raw address, but never sees one. The server is the second line: a raw address (another client, or a scrubber miss) is refused.

### The scrubber, ported

`scanner.scrub_log(text, context=None)` is OP1's `TelemetryPrivacy::Scrub`, rule by rule and in its order:

1. e-mail-shaped strings → `<email>` (OP1's `EmailAt`: local part `[alnum._%+-]`, domain `[alnum.-]` with trailing dots and dashes left to the sentence, a dot inside the domain, a top-level part of two or more letters);
2. the profile folder → `%USERPROFILE%`, either separator, any case;
3. a path ending in a project or export file (`.tbxpack .tbxp .tbxa .tbxm .tbxt .dxf .dwg .ifc .pdf .gltf .glb .obj .fbx`) from its root (`X:\`, `X:/`, `\\host\`, `%USERPROFILE%`) to the extension, or a bare such file name → `<project>`;
4. each known project folder, longest first → `<project>`;
5. the machine name, 6. the user name, whole words, any case, three characters or more → `<host>`, `<user>`.

`ScrubContext(profile_dir, user_name, host_name, project_dirs)` is OP1's `FTelemetryScrubContext`; `ScrubContext.from_json` reads `scrub-context.json`. **Production has no context** (only the app knows the machine): rule 2 becomes "any `X:\Users\<name>` or `Documents and Settings\<name>`", except the shared `Public`, `Default`, `Default User` and `All Users` folders, which the app leaves alone. Rules 4 to 6 do nothing. `scan_log` refuses a tail the context-free scrubber would change. Every rule puts different text in place of what it finds, so `scan_log` only asks whether any rule finds anything: one regular-expression pass each. A hostile 256 KiB tail of 43,000 bare `.pdf` names takes 3 ms to refuse (a full scrub of it takes about 5 s).

### Identity, names and modules

* **`install_id`** = the first 32 hex of SHA-256 over the secret's **64 lower-case hex characters** (UTF-8), as OP1 derives it (`FTruebexTelemetry::LoadInstall`, `MintSecret`, its stub's 5.5). PF14 hashed the 32 raw bytes. §4 says "`install_secret` = 32 random bytes (64 hex) in … install.json; `install_id` = the first 32 hex of its SHA-256". The secret exists on disk and on the wire (5.5 `{"install_secret": "<64 hex>"}`) only as those 64 characters, so the text supports the app's reading; OP1's Scope 1 says "SHA-256 of a 64-hex install secret". With PF14's reading, a real app's "Delete my data" never reached its own data.
* **Case.** The app writes event names, prop keys, enum values and the feedback `kind` from `FName`s (`FName::ToString`). FNames are case-preserving only in builds with editor data (UE 5.7 `NameTypes.h`: `WITH_CASE_PRESERVING_NAME` = `WITH_EDITORONLY_DATA`). In the packaged Shipping app an FName is spelled as the engine first registered it: `warning` can leave as `Warning`, `count` as `Count`, `bug` as `Bug`. The app's suites run with editor binaries and never see this. The server refused such a batch whole (422 `privacy_violation`, which the app drops) or dropped the prop. It now matches names and keys against the allow-list without case, and enum values against §6.1's lists without case, and stores §6.1's spelling (`service.allowed_index`, `scanner.canonical_enum`). The feedback `kind` is lower-cased before validation. Prop values that are not enums (`command`, `tool`, `category`) are stored as sent.
* **Module names.** OP1 sends `Truebex-Win64-Shipping+0x1a2b3c` (`FPaths::GetBaseFilename`, `TelemetryCrash.cpp`). The symbol store names the code file `Truebex-Win64-Shipping.exe`. `symbolicate.short_names` adds each table under its code file's and its PDB's stem, so the app's frames are named from the callstack. The full names win a clash.

Nothing changes in the data model, the API's shapes or the site: no migration, no copy, no page.

## Deliverables

- [x] `scripts/sync-contract-fixtures.ps1`
- [x] `server/tests/contracts/telemetry/`: OP1's 11 files byte-exact (app `main` `90799860`) and the folder README
- [x] `server/app/telemetry/scanner.py` (OP1's scrubber with `ScrubContext`; one-pass `scan_log`; e-mail in feedback text; case-free enums; the app's token set)
- [x] `server/app/telemetry/service.py` (`install_id_from_secret`, `allowed_index`, the feedback `kind`)
- [x] `server/app/telemetry/symbolicate.py` (`short_names`), `jobs.py` (stems in the symbol tables)
- [x] `server/tests/test_telemetry.py` on the app's set; `server/tests/fixtures/symbols/Truebex-Win64-Shipping.sym` (platform test file)
- [x] This doc; the tracker row; PF14's carry-over "OP1 (app): copy the fixtures" marked done

## Tests

| Name | Kind | Asserts | On the unchanged code |
|---|---|---|---|
| `test_privacy_violations_rejected` | pytest (§10) | the app's shape `{"cases": [{name, endpoint, field, payload}]}`; all 9 cases → 422 `privacy_violation`, `data.field` = the case's field; nothing stored | failed (`email-in-feedback-text` → `validation_failed`) |
| `test_telemetry_feedback_text_email_refused` | pytest | the app's case → 422, `data` = `{field: text, reason: email}`; the same in a whole message with `reply` and a device token → 422, nothing stored; `Please write to <email>` (what OP1 sends) → 202 with the account e-mail attached; slashes in the text → 202 | failed |
| `test_telemetry_scrub_matches_fixture` | pytest | `scrub_log(raw, ScrubContext.from_json(scrub-context.json)) == scrubbed`, also with CRLF line ends; the context-free scrubber leaves the scrubbed tail alone and changes the raw one; 5.3 and 5.4 refuse the raw tail (`data.field` `log`) and keep the scrubbed one | failed (no `ScrubContext`) |
| `test_telemetry_scrub_rules_follow_the_app` | pytest | each of OP1's six rules (e-mail edges, profile spellings and the shared folders, UNC / `%USERPROFILE%` / bare names, `.tbxpacks` not a match, project folders, whole-word host and user, names under three characters); `scan_log` refuses exactly the tails the scrubber changes | failed |
| `test_telemetry_app_events_batch_end_to_end` | pytest | `events-batch.json` byte for byte → 202 `{"accepted": 7, "dropped": 0}`, every row as sent (props, times, common blocks); the same events spelled as a Shipping build may (`Tool.Open`, `Command`, `MS`, `PDF`, `lit`, `Warning`) → 202, stored in §6.1's spelling | failed at the Shipping spelling (422 `type` on `kind`) |
| `test_telemetry_app_crash_end_to_end` | pytest | the app's multipart (`report`, `minidump`, scrubbed `log`, OP1's boundary and part headers) → 202 with the signature over the five normalised frames; row and files byte-exact; resent → `duplicate: true`; `Truebex-Win64-Shipping.sym` uploaded, `crash.symbolicate` names the three Shipping frames and moves the signature | failed at symbolication (frames unnamed) |
| `test_telemetry_app_feedback_end_to_end` | pytest | the app's multipart (`feedback`, `screenshot`, scrubbed `log`) → 202; row, screenshot and log byte-exact; resent → `duplicate: true`; `kind: "Bug"` → 202, stored `bug` | failed at `Bug` (422) |
| `test_delete_by_install_secret` | pytest (§10) | the secret's id is SHA-256 over its 64 hex characters (`116cea6c…`); everything sent under it is gone after `telemetry.deletions`, other installations kept | failed (raw-byte id) |
| `test_telemetry_scanner_platform_cases` | pytest | PF14's former authored cases the app's set leaves out (e-mail in an unknown prop, in `hw.gpu`, in `gpu_driver`, in feedback `os`; free text in an enum; a string for a boolean; a path in `exception.module`; a token ending in a newline, which `$` let through until the token check became a full match) → 422 naming the field | passed (a guard), except the newline case |
| the rest of `test_telemetry.py` (16) and `test_site_pf14.py` (2) | pytest | PF14's tests, on the app's fixture values where they read them (signature, counts, frames, the reply's quoted text); the CadCore symbol test builds its DLL crash in the test | 8 of them failed on the copied fixtures before their values were updated |
| `npm run lint`, `npm run build`, whole `pytest` | verify gate | green | — |

## Human test

Local API only; the site is unchanged. In PowerShell, from the worktree root (`X:\Truebex-autopilot\t65-pf14d-telemetry-fixtures-re-copi`):

1. Start a local API: `server\run.bat` (port 8000; it creates `server\.env` from the example if missing). Leave it running and open a second PowerShell window in the worktree root.
2. `cd server\tests\contracts\telemetry` and set `$H = 'X-Truebex-Contract: telemetry/1.0'`.
3. `curl.exe -s http://127.0.0.1:8000/telemetry/config -H $H` → the allow-list of `config.json`, `"enabled":true`.
4. `curl.exe -s -X POST http://127.0.0.1:8000/telemetry/events -H $H -H "Content-Type: application/json" --data-binary "@events-batch.json"` → `{"accepted":7,"dropped":0}`.
5. `curl.exe -s http://127.0.0.1:8000/telemetry/crashes -H $H -F "report=@crash-report.json;type=application/json" -F "minidump=@minidump-stub.dmp;type=application/octet-stream" -F "log=@log-tail-scrubbed.txt;type=text/plain"` → `{"crash_id":"5d41402abc4b2a76b9719d911017c592","signature":"2cbffddc585bd1f3","duplicate":false,"known_issue":null}`; the same command again → `"duplicate":true`.
6. `curl.exe -s http://127.0.0.1:8000/telemetry/feedback -H $H -F "feedback=@feedback.json;type=application/json" -F "screenshot=@screenshot.png;type=image/png" -F "log=@log-tail-scrubbed.txt;type=text/plain"` → `{"feedback_id":"a3f1c2d4e5b60718293a4b5c6d7e8f90","received_at":"…Z","duplicate":false}`.
7. The app's e-mail case: `((Get-Content privacy-violations.json -Raw | ConvertFrom-Json).cases | Where-Object name -eq 'email-in-feedback-text').payload | ConvertTo-Json -Compress | Set-Content -Encoding ascii $env:TEMP\fb-email.json`, then `curl.exe -s http://127.0.0.1:8000/telemetry/feedback -H $H -F "feedback=@$env:TEMP\fb-email.json;type=application/json"` → 422, `"code":"privacy_violation"`, `"data":{"field":"text","reason":"email"}`.
8. The raw log tail: step 5 with `log-tail-raw.txt` in place of `log-tail-scrubbed.txt` → 422 `privacy_violation`, `"field":"log"`.
9. Deletion: `Set-Content -Encoding ascii $env:TEMP\del.json '{"install_secret": "7d4e1f0a9b3c2d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6"}'`, then `curl.exe -s -X POST http://127.0.0.1:8000/telemetry/delete -H $H -H "Content-Type: application/json" --data-binary "@$env:TEMP\del.json"` → `"install_id":"116cea6cd6478818630f1281498f01ca"` and a `complete_by` 30 days ahead.
10. With an OP1 build (needs the app workspace; skip if none is at hand): start it with `-UserDir=%TEMP%\TbxPF14d -mwtelemetryendpoint=http://127.0.0.1:8000`, answer the first-start card (usage events On, Save), then Help > Send feedback..., type `Please write to alex.morgan@example.com about the wall gap`, Send → "Thank you -- your feedback was sent." Help > Privacy...: the Feedback payload reads `"text": "Please write to <email> about the wall gap"`. On the API side: `server\.venv\Scripts\python.exe -c "import sqlite3; print(sqlite3.connect('server/auth.db').execute('select text from feedback order by received_at desc limit 1').fetchall())"` (from the worktree root) prints the same `<email>` text. The app replaces the address before sending (it does not refuse it). Step 7 shows the server refusing a raw one.

## Risks / traps

* **The app checkout's line endings.** `core.autocrlf=true` there: copying the working-tree files would commit CRLF variants of the app's LF fixtures. The script reads blobs.
* **The Autopilot guard refuses `git -C <app repo>`** in a task's own tool calls; the script's read-only git runs inside PowerShell. Never run a writing git command there.
* **The context-free profile rule** still refuses a tail holding another real profile folder or an 8.3 short name (`C:\Users\ALEXMO~1\…`, which `GetTempPath` can return) that the app's exact-folder rule leaves. That is a privacy hit, refused as before, and the crash report is dropped. Shipping builds send the product trail, not the engine log, so this mainly concerns Development builds.
* **`scrub_log` with many matches is quadratic** (a 256 KiB tail of bare `.pdf` names: about 5 s). Production calls `scan_log`, which is one pass per rule; keep it that way.
* Bash heredocs on this PC collapse doubled backslashes: Windows paths in tests are raw strings written with the Edit tool.

## As-built

* **Date, branch, commits:** 2026-10-13, `ap/t65-pf14d-telemetry-fixtures-re-copi` (base `master` 9dac34b); `c708e6b` (fixtures, script, tests, server) and the docs commit (this doc, the tracker row, PF14's carry-over).
* **Counts:** pytest 669 → 675 collected (`test_telemetry.py` 19 → 25: six new tests). Tests first: on the unchanged server code with the copied fixtures, all eight new or changed tests in the table above failed (the end-to-end ones at their Shipping-spelling or symbolication step: the app's raw events, crash and feedback bodies were already accepted, as the manager had found), plus 8 of PF14's tests that read the old fixture values; `test_telemetry_scanner_platform_cases` passed (a guard for rules the app's set leaves out). After: 25 of 25. The verify gate: 658 passed + 17 skipped (last bullet).
* **Live run** (uvicorn on scratch SQLite, port 18065, Windows `curl.exe`, the app's fixtures as files): 5.1 equal to `config.json`; 5.2 202 `{"accepted":7,"dropped":0}`; 5.3 202 `signature 2cbffddc585bd1f3`, `duplicate:false`, again `duplicate:true`; 5.4 202 `feedback_id a3f1c2d4…`, `received_at …Z`; `email-in-feedback-text` 422 `privacy_violation` `{"field":"text","reason":"email"}`; all 9 privacy cases 422 naming their fields (`callstack[0]`, `locale`, `events[0].props.plan`, `events[0].props.tool` ×2, `events[0].props.ms` ×2, `events[0].props.command`, `text`); the raw tail 422 `{"field":"log"}`; 5.5 202 `install_id 116cea6c…` with `complete_by` +30 days, and `python -m app.worker --run telemetry.deletions` removed the 7 events sent under that id; `/admin/symbols` took `Truebex-Win64-Shipping.sym` (`code_file` `.exe`), `crash.symbolicate` named the three Shipping frames and `/admin/telemetry/crashes` showed one group `d12f9a5219c4c968` titled `Truebex-Win64-Shipping!FCadWall::RebuildMesh(FCadWallBuildContext&)`; `/admin/feedback` listed the message with screenshot and log.
* **Deviations from the task and why:**
  1. *The app does not refuse an e-mail typed in feedback; it replaces it.* OP1's `SendFeedback` scrubs the text with `ScrubLive` before its scanner runs, so the address leaves as `<email>`. The human test checks that payload, and the curl step checks the server's refusal of a raw address.
  2. *Three server changes beyond the brief's item 3, all under its item 4* (the app's payloads meeting a rule the server refused): FName spelling without case, the feedback `kind` lower-cased, and module stems in symbolication. Plus the token set widened to the app's and the shared `Users` folders exempt from the context-free profile rule.
  3. *`install_id` changed* (item 5): the app's code shows the other reading, and §4's text supports it (Design).
  4. *`scan_log` no longer calls `scrub_log`*: it answers the same question (does any rule fire), proven on the fixtures and edge cases by `test_telemetry_scrub_rules_follow_the_app`, in linear time.
  5. *PF14's CadCore symbol test keeps a crash built in the test* (`cadcore_report`): the app's fixture crashes in the Shipping executable. The app's crash gets its own platform `.sym` test file.
* **App payloads against the server, field by field** (the brief's "not checked"): `events-batch.json`, `crash-report.json` (with OP1's common block, which also carries `locale`, `plan` and `hw`; ignored keys) and `feedback.json` pass the request models; OP1's multipart (`truebex-<24 hex>` boundary, a filename and type on every part) parses; `hw` is `{}` before the RHI is up (all optional); `gpu` has `/` and `\` replaced by spaces in the app. Differences found:

  | # | Where | App | Server | Done |
  |---|---|---|---|---|
  | 1 | names, prop keys, enum values, feedback `kind` | FName spelling (any case in Shipping) | exact case | server matches without case (PATCH line A) |
  | 2 | callstack module | `Truebex-Win64-Shipping` (no extension) | symbols keyed `…exe` | stems added (PATCH line B) |
  | 3 | `install_id` | SHA-256 of the 64 hex characters | of the 32 raw bytes | server follows the app (PATCH line C) |
  | 4 | feedback `text` length | cut to 5,000 **before** scrubbing, which can lengthen it (`PC1` → `<host>`) | 5,000 (contract) | kept; OP1 carry-over: scrub, then cut |
  | 5 | feedback `log` part | the last 256 KiB **then** scrubbed, never trimmed again (`C:\Users\bob` → `%USERPROFILE%` grows); `CrashLogPart` does trim | 256 KiB (contract) → 413, which the app drops | kept; OP1 carry-over: trim after scrubbing as `CrashLogPart` does |
  | 6 | `app.channel` | `[Truebex.Telemetry] Channel`, up to 64 characters | 16 (`String(16)` columns) | kept (`stable`, `beta` fit); contract question D |
  | 7 | separator rule | every string but `schema`, feedback `text`, crash `message` | prop values, `callstack`, `exception` | kept (the server accepts what the app sends; §6.4 names prop values); contract question E |
  | 8 | integer-valued numbers (`12.0`) | its scanner allows them; it writes `%lld` | refused as `type` | kept (never sent) |
  | 9 | enum token characters | `[A-Za-z0-9_.+-]`, Unicode letters | ASCII, leading letter or digit | widened to the app's set (plus `:`) |

* **PF14 deviation 2's readings against the app:**

  | Reading | App (OP1) | Server |
  |---|---|---|
  | `install_id` over the 32 raw bytes | differs: the 64 hex characters | changed to the app's |
  | signature: top five frames, `Module!Function` / `Module!0xoff`, joined by `\n` | computes none; its stub hashes the five raw frames, each followed by `\n`, and that value never leaves the stub; it only shows `known_issue` | unchanged; contract question F |
  | sizes in MiB / KiB | the same (`<< 20`, `* 1024`) | unchanged |
  | `dropped` = events + props | ignores the 5.2 answer body; its stub answers `0`; it drops a whole event with an unknown prop before sending (OP1 deviation 6) | unchanged |
  | 5.4 repeats answer `"duplicate": true` | reads only `feedback_id` from 5.4 (`duplicate` from 5.3) | unchanged (§7 says so for 5.3 and 5.4) |
  | `privacy_violation` carries `data.reason` | its stub sends `data.field` only; the client reads `code` | unchanged (additive) |
  | feedback `text` exempt from the scanner | **not adopted**: e-mails refused, slashes allowed | changed (this feature) |
  | a missing `X-Truebex-Contract` served as current | always sends `telemetry/1.0` | unchanged |
  | the server's log scrubber replaces whole project-file paths and refuses what it would still change | wider rules (13 extensions, bare names, the machine's folders and names) | ported; refusal kept |

* **PATCH lines for the app side to write in `telemetry.md` §3** (1.0.2, wording only; the platform already behaves so):
  * A. §6.1: event names, prop keys and enum values compare without case; the platform stores §6.1's spelling (a Shipping build's FNames are not case-preserving).
  * B. §5.3: a `callstack` frame names its module without a path, with or without the extension (`Truebex-Win64-Shipping+0x1a2b3c`).
  * C. §4: `install_id` is the first 32 hex of SHA-256 over the secret's 64 lower-case hex characters as UTF-8 text.
  * G. §6.4: the platform's separator rule covers event prop values, `callstack` frames and the `exception` block; feedback `text` may hold separators but never an e-mail-shaped string.
* **Contract questions** (for the next MINOR or PATCH): D. a maximum length for `app.channel` and `app.build` (the platform stores 16). E. whether the platform should widen the separator rule to every string, as the app's scanner does. F. whether §6.3's "top five `module!function` frames" means the platform's normalisation (named frames lose parameters and offset, raw ones become `Module!0xoff`, joined by `\n`); only the platform computes signatures, so no client depends on it yet.
* **Contract §11:** PF14's five rows still read "PF14: not yet" in the app's `telemetry.md` (PF14's As-built asked the owner to set them at merge); with this feature they can read "PF14: done (2026-10-09, `ap/t3-pf14-…`; app fixtures since PF14d 2026-10-13)".
* **Carry-over:**
  * **OP1 (app):** write PATCH lines A, B, C and G; in `SendFeedback`, scrub the text before cutting it to 5,000 characters; trim the feedback log part to 256 KiB after scrubbing (as `CrashLogPart` does); serialise names, keys and enum values from the allow-list's strings rather than `FName::ToString` (the server copes either way).
  * **Owner:** the §11 rows; contract questions D, E and F to whichever side next touches the contract.
* **Verify gate:** `scripts/autopilot-verify.ps1` green on `a3c392f`: lint, build, pytest 658 passed + 17 skipped (675 collected; `test_site_pf14.py` 2 of 2 on the built `out/`), 1,241 s in all, pytest 779 s.
