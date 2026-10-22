# PF11b — The AI proxy follows ai-proxy 1.1.2 (AI3, AI5's create script, AI7's tool-less turns): the app's fixtures and four scripted conversations re-copied, `usage_url` on 5.2, the ai-proxy/1.1 echo (launch priority 3)

**Needs merged:** PF11 (and PF2b, PF2c, PF2e, PF12, all on `master` fdfa389 = d222f29 plus the brand folder); AI3 on the app side ("Truebex AI tier through the platform", app `main` e2eed8bda, 2026-10-21, T114), T183 (AI5 meeting AI3, app `main` 319fed6f8) and T184 (AI7 meeting AI3, app `main` f6a980856). **Unblocks:** AI3's human test step 6 against the platform (the owner, once api.truebex.com is up). **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\ai-proxy.md` **1.1.2** (2026-10-22; the app side is authoritative, C.9). Every `/ai` route now answers `X-Truebex-Contract: ai-proxy/1.1`.

## Status

**Built 2026-10-22** on `ap/t94-pf11b-the-ai-proxy-follows-ai-pr` (Autopilot T94); see As-built. What was behind on `master` d222f29, checked against app `main` e2eed8bda, 319fed6f8 and f6a980856 before the work:

| # | Where (master d222f29) | Before |
|---|---|---|
| 1 | `server/tests/contracts/ai-proxy/` | PF11's stand-ins (`make_ai_proxy_fixtures.py`, PF11 deviation 1): 9 files, every one of the 8 the app shares differing from the app's; the app's folder (AI3 d0345609e, T183 a3fd173a0) has 26: three balances, `count.json`, seven envelopes, `refusal.sse` in place of `refusal.json`, four scripted conversations (`window/`, `paint/`, `echo/`, `create/`, a `script.json` each) |
| 2 | `server/app/ai/credits.py` `balance_json` | no `usage_url` (1.1.0's optional key); `top_up_url` `<site>/dashboard/cloud/#ai-credits` |
| 3 | `routers/ai.py:26`, `ai/proxy.py:46` | `contract("ai-proxy", 1, 0)`, `CONTRACT = "ai-proxy/1.0"`: the app's `ai-proxy/1.1` was served (only the MAJOR is checked) and answered 1.0; the 1.0 strings also in `tests/ai_helpers.py`, `test_ai_proxy.py`, `test_pf11_pf12_meet.py`, `scripts/demo_ai.py` |
| 4 | `ai/validate.py:177-180`, `ai/adapters/anthropic.py:62-63` | a `tool_choice` without tools accepted and forwarded alone to Anthropic (the self-hosted adapter dropped it) |
| 5 | `tests/fakes/fake_provider.py`, `scripts/fake_ai_upstream.py` | served one `.sse` file per queued answer; no `script.json`, no `${name}` placeholders |
| 6 | `scripts/demo_ai.py` | a new `metadata.session_id` for every turn of one conversation |
| 7 | `scripts/demo_analysis.py:28` | `render-jobs/1.0` (PF6a deviation 6) |

Already fine, verified only: the header check accepts any 1.x; `credits_remaining` = allowance + top-ups; the codes of all seven app envelopes exist; 409 `duplicate_request`; `metadata.session_id` kept in `ai_usage` and never sent upstream; a tool-less request (no tools, no `tool_choice`) served, streamed or whole, with neither key sent upstream.

## Goal

The app's Truebex AI panel (AI3) and its unattended-run summaries (AI7) work against the real platform exactly as they do against the app's own stub: the same four scripted conversations stream through the platform's proxy byte for byte, the balance answer carries the link the app shows ("see your usage") to the page that really lists a person's AI turns, and the platform's tests are the app's own files, so what passes here passes with the real app.

## Read first

* `docs/roadmap/40/00-contract.md` P.2-P.4; `PF11-analysis-and-ai-services.md` (Design, As-built deviations 1 and 3); `PF6a-render-jobs-1-1-0.md` and `PF7e-marketplace-api-1-2-0.md` (how a fixture set is re-copied and pinned).
* `ai-proxy.md` 1.1.2: *Changes* 2026-10-21 and both 2026-10-22 lines; 5.2 (`usage_url`, `credits_remaining`); 5.3's `tools` row; §8's "The app's side (1.1.0)" and "Size"; §9 (the file table, `script.json`, the placeholders, the variants); §10; §11.
* App repo, read only: `Docs/roadmap/40/AI3-truebex-ai-tier-through-the-platform.md` (As-built, Carry-over); `Plugins/TruebexAgent/Source/TruebexAgent/Private/Assistant/AssistantProxy.cpp` (`OnBalance`, the header, the key per attempt, the 401 mapping), `Provider_TruebexProxy.cpp` (`BodyOf`), `Plugins/FastEye/Source/FastEye/Private/Agent/FastEyeAiProxyStub.cpp` (script pick, captures, rule names).

## Scope

**In** (nothing was cut):

1. **PF11's own set where tests need it.** `git mv` the three window turns (cache read and write tokens; the proxy's whole stream in each file) to `server/tests/fixtures/ai/window/`, with a README; `make_ai_proxy_fixtures.py` writes (and `--check`s) only those, there. Then `scripts\sync-contract-fixtures.ps1 -Contract ai-proxy`: 26 files, every blob id equal, PF11's `refusal.json` and the folder's `.gitattributes` removed (the root `.gitattributes` keeps `server/tests/contracts/** -text`). The folder README rewritten for the app's set; the folder pinned by `APP_BLOBS` and its git tree id.
2. **The fake provider plays `script.json`** as the stub does: the script by the newest user words (`window`, `paint`, `create`; `echo` the rest) or by name, the turn by the assistant replies since those words, each `.sse` without its `truebex_credits`; **`${name}` filled** from the capture (the dotted path of the earlier turn's `tool_result`, read from the request the proxy forwarded; a quote or backslash refused like the stub's `capture-value`). `scripts/fake_ai_upstream.py` answers every request that way.
3. **5.2 `usage_url`** = `<site>/dashboard/cloud/#ai-usage`, a new anchor on the Cloud page's Recent turns panel (`AiCredits.tsx`, the same `scroll-mt-24` as `#ai-credits`; the page scrolls to it once the data is in). `top_up_url` stays `/dashboard/cloud/#ai-credits`; `allowance_remaining` stays (additive).
4. **The 1.1 echo** on `/ai/models`, `/ai/balance`, `/ai/messages`, `/ai/messages/count`; 1.0 clients served; `ai_helpers.AI`, the meet test and `demo_ai.py` send 1.1.
5. **`message_start`** relayed untouched (PF11 deviation 3); `truebex_credits` keeps `served_by` (additive).
6. **`credits_remaining` never null today** for a plan holding `ai.metered` (kept); the unlimited case is a PATCH proposal (As-built).
7. **Fold-in:** `demo_analysis.py` sends `render-jobs/1.1`; README's PF11 section names render-jobs 1.1.0 and ai-proxy 1.1.2.
8. **1.1.2's tool-less turns:** served, streamed or not, neither key upstream; a `tool_choice` without tools is **422 `validation_failed` on `tool_choice`** (5.3 and 5.4); the Anthropic adapter sends `tool_choice` only with tools.

**Out (and where it goes):**

* Going live (api.truebex.com up), `ANTHROPIC_API_KEY` in `server/.env`, and AI3's human test step 6 on the Shipping release: **the owner**.
* GD7's rates and allowances; `truebex-fast` in the app's `models.json` is stub data, so no alias is added for it: **GD7**.
* Images in a request (AI3 sends none), the own-key path (**AI2**), local models (**AI4**).
* The contract's §11 cells and PATCH lines: the app half writes the contract (proposed in As-built).

## Design

### API

No new endpoint.

| Route | PF11b |
|---|---|
| all four `/ai` routes | `contract("ai-proxy", 1, 1)`: 1.0, 1.1 or no header served and answered `ai-proxy/1.1`; 2.0 gets 400 `contract_version` with `data.supported` `["ai-proxy/1.1"]` |
| `GET /ai/balance` (5.2) | adds `"usage_url": "<SITE_URL>/dashboard/cloud/#ai-usage"` (`credits.usage_url()`); the rest unchanged |
| `POST /ai/messages`, `/ai/messages/count` | `tool_choice` with no (or an empty) `tools` → 422 `validation_failed`, `data.fields[0].field` `tool_choice`, nothing forwarded |

The four scripted conversations through the proxy (§6.2 at `truebex-assist`'s 5.1 rates, each turn's `usage`; the files' own `truebex_credits` are the stub's ledger):

| Turn | Usage (in / out) | §6.2 | The file says |
|---|---|---|---|
| `window/01-find`, `02-place`, `03-end` | 5120 / 58, 5420 / 47, 5730 / 18 | 22, 23, 24 | 21, 16, 9 |
| `paint/01-find`, `02-fill`, `03-end` | 5040 / 41, 5310 / 52, 5600 / 16 | 21, 23, 23 | 24, 19, 11 |
| `echo/01-end` | 900 / 4 | 4 | 2 |
| `create/01-layout`, `02-end` | 5480 / 164, 6900 / 26 | 26, 29 | 38, 12 |
| `refusal.sse` | 1200 / 12 | 6 | 3 |

### Data

None: no table or column. `ai_usage` rows of a conversation share its `session_id`.

### UI

`src/components/cloud/AiCredits.tsx`: the Recent turns panel sits in `<div id="ai-usage" className="scroll-mt-24">` (`USAGE_ANCHOR`); the scroll-once effect also follows `#ai-usage` (falling back to the section's top when the plan has no AI). `src/lib/ai.ts` `AiBalance` gains `usage_url`. No copy changed.

### Jobs / workers

None.

### Security and privacy

Unchanged: no message text, tool input or image is stored; the fake provider and `fake_ai_upstream.py` are test tools that hold no key.

## Deliverables

- [x] `server/tests/contracts/ai-proxy/` (the app's 26 files + the platform's README), `server/tests/fixtures/ai/` (PF11's three window turns + README)
- [x] `server/app/ai/credits.py` (`usage_url`), `ai/proxy.py` and `routers/ai.py` (1.1), `ai/validate.py` (tool_choice only with tools), `ai/adapters/anthropic.py`
- [x] `server/tests/fakes/fake_provider.py` (`script()`, `stub_like`, `contract_bytes`), `scripts/fake_ai_upstream.py`, `scripts/make_ai_proxy_fixtures.py` (`--check`), `scripts/demo_ai.py` (1.1, one session per conversation, `summary`), `scripts/demo_analysis.py` (render-jobs/1.1)
- [x] `src/components/cloud/AiCredits.tsx`, `src/lib/ai.ts`
- [x] `server/tests/test_pf11b_ai_proxy_1_1.py`, `test_site_pf11.py` build check, the moved assertions; this doc, the tracker row, README

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_pf11b_contract_folder_is_the_apps_at_the_recorded_commit` | pytest | the folder = the app's 26 blobs at a3fd173a0 + README, LF, tree 907992a92; `git ls-tree` / `rev-parse` agree where the app repo is present |
| `test_pf11b_pf11s_own_turns_live_in_fixtures_ai` | pytest | PF11's three turns (cache tokens) in `fixtures/ai/`; `make_ai_proxy_fixtures.py --check`; it never names the contract folder |
| `test_pf11b_scripted_conversation_through_the_proxy[window, paint, echo, create]` | pytest | one session each through streamed 5.3; every turn byte-equal to its file outside `truebex_credits` (placeholders filled); the proxy's `truebex_credits` before `message_stop`, §6.2's charge, the ledger's remaining; the fake's pick; history and every `tool_result` byte-equal upstream; `ai_usage` per turn |
| `test_pf11b_streamed_refusal` | pytest | `refusal.sse` through, `stop_reason` refusal, charged 6, the turn recorded |
| `test_pf11b_tool_less_turn_served` | pytest | AI7's summary (no tools, no `tool_choice`) 200, charged 4, neither key upstream, streamed and whole (the guard: served on d222f29 already) |
| `test_pf11b_tool_choice_without_tools_refused` | pytest | 422 on `tool_choice` for auto / none, no or empty tools, 5.3 and 5.4; nothing forwarded |
| `test_pf11b_balance_has_the_apps_keys_and_types` | pytest | Studio 4388, low 412, empty 0: the fixtures' keys and types, the ledger's values, the platform's `usage_url` and `top_up_url` |
| `test_pf11b_models_and_count_have_the_apps_shapes` | pytest | 5.1 per model and 5.4 keys and types; `truebex-assist`'s entry equal |
| `test_pf11b_error_envelopes_match_the_apps` | pytest | the seven envelopes: code, status, envelope keys, data keys (extras named), retry_after_s nullness; detail and request_id masked |
| `test_pf11b_routes_speak_ai_proxy_1_1` | pytest | the four routes answer 1.1 to 1.0, 1.1, none; 2.0 is 400 |
| `test_pf11b_no_route_or_script_left_on_1_0` | pytest | no `ai-proxy/1.0` in `server/app`; helpers and demos on 1.1; `demo_analysis.py` render-jobs/1.1 |
| `test_pf11b_usage_url_opens_the_recent_turns_panel` | pytest | `usage_url`'s fragment is the Recent turns panel's id in `AiCredits.tsx` |
| `test_site_pf11_recent_turns_carry_the_usage_anchor` | build check | the Cloud page's own chunks carry `"ai-usage"` beside `"ai-credits"` |
| the existing AI, billing and site suites | pytest | green, assertions moved only where they read re-copied files (As-built) |
| headless Edge (`cdp_pf11b.mjs`, scratch) | self-test | `/dashboard/cloud/#ai-usage` lands on Recent turns with the demo's turns; `#ai-credits` still on the section |

## Human test

About 10 minutes, Windows PowerShell, three windows. The API runs on :8000 against a fresh database, its model provider is `fake_ai_upstream.py` (the app's scripted conversations, no key spent).

Window 1, in the worktree root:

1. `cd server; .venv\Scripts\python.exe scripts\fake_ai_upstream.py --port 8790` → `fake model provider on http://127.0.0.1:8790 (the app's scripted conversations: window, paint, create, echo)`.

Window 2, in the worktree root:

2. Paste:
   ```powershell
   cd server
   $k = .venv\Scripts\python.exe scripts\make_signing_key.py --kind lic
   $env:LICENCE_SIGNING_KEY = (($k | Select-String '^LICENCE_SIGNING_KEY=').Line -replace '^LICENCE_SIGNING_KEY=', '')
   $env:LICENCE_KEY_ID = (($k | Select-String '^LICENCE_KEY_ID=').Line -replace '^LICENCE_KEY_ID=', '')
   $env:DATABASE_URL = 'sqlite:///./pf11b-try.db'
   $env:ANTHROPIC_API_KEY = 'sk-ant-local-fake'
   $env:ANTHROPIC_BASE_URL = 'http://127.0.0.1:8790'
   $env:SITE_URL = 'http://127.0.0.1:3194'
   $env:CORS_ORIGINS = 'http://127.0.0.1:3194'
   .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
   → `Uvicorn running on http://127.0.0.1:8000`.

Window 3, in the worktree root:

3. `$env:NEXT_PUBLIC_AUTH_URL='http://127.0.0.1:8000'; npm run build` (about 3 min; the verify gate's `out/` points at production), then `$env:AUTOPILOT_TASK_ID='T94'; powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` → `serving … on http://127.0.0.1:3194/`.

Window 4 (any PowerShell), in the worktree root:

4. Paste:
   ```powershell
   cd server
   Invoke-RestMethod -Method Post http://127.0.0.1:8000/auth/register -ContentType 'application/json' -Body '{"email":"ai-demo@example.com","password":"password123"}' | Out-Null
   $login = .venv\Scripts\python.exe scripts\demo_replica.py --api http://127.0.0.1:8000 login --email ai-demo@example.com --password password123 --trial
   $login
   $t = (($login | Select-String '^device token: ').Line -replace '^device token: ', '')
   .venv\Scripts\python.exe scripts\demo_ai.py --token $t balance
   ```
   → `Pro trial started (ends …)`, `device DEMO-REPLICA for ai-demo@example.com: plan pro, …`, then the 5.2 answer: `"credits_remaining": 2000`, `"plan": "pro"`, `"top_up_url": "http://127.0.0.1:3194/dashboard/cloud/#ai-credits"`, `"usage_url": "http://127.0.0.1:3194/dashboard/cloud/#ai-usage"`.
5. `.venv\Scripts\python.exe scripts\demo_ai.py --token $t window` → `I'll find the study's north wall first.`, `[tool call] find {"kind": "wall", "room": "Study", "facing": "n"}`, `[credits] 22 charged, 1978 left (served by anthropic truebex-assist)`; then `Placing a 1.2 m window.`, `[tool call] place {"kind": "window", "host": "0199c6a2e00070018000000000000001", "width_mm": 1200}` (the wall the demo's find returned), `[credits] 23 charged, 1955 left …`; then `Done: a 1.2 m window on the study's north wall.`, `[credits] 24 charged, 1931 left …`, `[stop] end_turn`. Window 1 prints `answered window/01-find.sse (turn 1 of window)` and turns 2 and 3.
6. `.venv\Scripts\python.exe scripts\demo_ai.py --token $t summary` (a tool-less turn, as the app's unattended-run summaries send) → `Noted.`, `[credits] 4 charged, 1927 left …`, `[stop] end_turn`.
7. Browser: `http://127.0.0.1:3194/login/`, sign in as ai-demo@example.com / password123, then open `http://127.0.0.1:3194/dashboard/cloud/#ai-usage` → once the page's data is in it scrolls down to **Recent turns** (on this short page: to the page's end, the panel fully in view under "Buy credits", above "Recent jobs"), four rows newest first: `truebex-assist` 4 —, 24 —, 23 `place`, 22 `find`.
8. Open `http://127.0.0.1:3194/dashboard/cloud/#ai-credits` → the page scrolls to the AI section's top: "AI credits", "Credits left" 1,927.
9. Clean up: Ctrl+C in windows 1-3; in `server`: `Remove-Item pf11b-try.db`; in the root: `Remove-Item -Recurse -Force out` (it points at the local API; the next serve rebuilds against `.env.local`).

Optional, the owner's (not run by this task): AI3's human test step 6, the app's Shipping release signed in to a Studio account against the live API, with `ANTHROPIC_API_KEY` in `server/.env` and no `ANTHROPIC_BASE_URL`: "Put a window on the north wall of the study, 1.2 m wide" streams, calls `find` then `place`, the window appears, the header shows the charge; Settings > AI's usage link opens the Cloud page's Recent turns. Needs api.truebex.com up.

## Risks / traps

* **Two fixture sets.** `fake.sse("window/01-find.sse")` and `fixture_bytes` read PF11's own turns (`tests/fixtures/ai/`); `contract_bytes`, `fake.script()` and `fake_ai_upstream.py` read the app's. A test that needs §6.2's cache arithmetic or a whole-stream comparison uses PF11's; a test of the app's behaviour uses the app's.
* **The next re-copy:** run the sync script, then update `APP_BLOBS`, `APP_TREE`, `APP_COMMIT`, `APP_MAIN` in `test_pf11b_ai_proxy_1_1.py`, and `CHARGED` / `STUB_CHARGED` if a file's usage moves. The folder README is the platform's own (unlike the marketplace folder's): the script keeps it.
* **`served_by.model` says `truebex-assist`** against the fake: the app's files put the alias in `message_start`, which the proxy relays and reads as the answering model. A real provider names its model there (`claude-opus-5-5`).
* **`out/` from the gate points at production:** rebuild with `NEXT_PUBLIC_AUTH_URL` before step 7; `SITE_URL` makes `usage_url` open on the served build.
* **A short Cloud page** cannot scroll the Recent turns panel to the top: the browser stops at the page's end with the panel in view.
* **Headless Edge's launcher detaches its children:** stop them by the profile path before the next run (they hold `--user-data-dir`).

## As-built

* **Date, branch, commits:** 2026-10-22, `ap/t94-pf11b-the-ai-proxy-follows-ai-pr` from `master` fdfa389. `cb69662` (tests first), `3e58dcd` (the copy and the change), `6e33d42` (`demo_ai.py`: one session per conversation, `summary`), then the docs commit (this doc, the tracker row, the README section).
* **Copy:** `scripts\sync-contract-fixtures.ps1 -Contract ai-proxy` from the app's `main` **7fdde1e6f** ("copied 26 files … each byte-exact to the app's blob"; updated 26, unchanged none, removed `.gitattributes`, `refusal.json`). The folder's last commit there is **a3fd173a0** (T183, 1.1.1; AI3's d0345609e made it); T184's 1.1.2 (a4d178703) moved no file. The folder's tree at a3fd173a0 is **907992a926585ba8b9fd06b1ba7315fdc090a6cb**; the committed blobs (`git ls-tree -r HEAD server/tests/contracts/ai-proxy/`, README aside) equal `git ls-tree -r a3fd173a0 -- Docs/roadmap/fixtures/contracts/ai-proxy/` blob for blob. Of PF11's 9 files, the 8 the app shares were replaced (all differed), `refusal.json` removed; 18 are new. PF11's three window turns moved first (`git mv`) and `make_ai_proxy_fixtures.py --check` still writes them byte for byte.
* **Counts:** pytest collected 915 → 931 (15 in `test_pf11b_ai_proxy_1_1.py`, 1 in `test_site_pf11.py`). **Tests first:** on the base all 15 failed (folder, missing files, 1.0 echo, no `usage_url`, a `tool_choice` without tools forwarded: 502 from the fake); the build check fails on a base build (no `ai-usage` anywhere in `src/` at d222f29); with the change all pass. The touched suites (`test_pf11b`, `test_ai_proxy`, `test_ai_credits`, `test_ai_topup_billing`, `test_pf11_pf12_meet`, `test_pf2c_billing_tidy`, `test_pf2e_one_off_customer`, `test_site_pf11`, `test_site_pf3b`) on SQLite: 55 passed, 7 skipped (the `out/` build checks and a Postgres-only test); with `out/` built, `test_site_pf11.py` 4 of 4 and `test_site_pf3b.py` 3 of 3. **Postgres 17** (throwaway cluster, session zone Asia/Baghdad, `TEST_APP_DATABASE_URL` + `TEST_DATABASE_URL`): the same suites 57 passed, 5 skipped (the `out/` build checks). The verify gate: the last bullet.
* **Decisions:**
  * **`usage_url`** = `<SITE_URL>/dashboard/cloud/#ai-usage`, the Recent turns panel of the Cloud page's AI section (new anchor, `scroll-mt-24` as `#ai-credits`). The stub's `/dashboard/usage/` is the site's page of developer API requests, which shows no AI turn. `top_up_url` stays `/dashboard/cloud/#ai-credits`, where packs are bought (the stub's `/dashboard/billing/` sells plans, not packs).
  * **Placeholders: filled**, as the stub fills them: `${wall}` and `${room}` from the capture of the `tool_result` the proxy forwarded (`window/02-place.sse`'s host is the wall the request's `find` returned; `paint/02-fill.sse`'s target the room). `${remaining}` sits only in `truebex_credits`, which the fake drops.
  * **`message_start`: relayed untouched** (PF11 deviation 3; the app reads neither `model` nor `served_by`). The app's files carry the alias there, so against them `served_by.model` and `ai_usage.provider_model` read `truebex-assist`; a real provider names its model.
  * **A `tool_choice` without tools: 422 `validation_failed` on `tool_choice`** (1.1.2: "a request without tools may not carry `tool_choice`"; the app never sends one; its stub records `tool-choice`), rather than forwarding it alone. The Anthropic adapter also sends `tool_choice` only with tools, like the self-hosted one.
  * **`credits_remaining` never null today**: every plan holding `ai.metered` has a number (catalogue `ai_credits_month` 0 → `credits.json` `allowance_month`). A plan with no limit (null) would answer `credits_remaining` null, which the app's `OnBalance` counts as an error: a PATCH proposal below, no code change.
* **The stub's charges against §6.2** (each file's usage at `truebex-assist`'s rates; the platform charges these, the files' `truebex_credits` say the stub's): window 22, 23, 24 (21, 16, 9); paint 21, 23, 23 (24, 19, 11); echo 4 (2); create 26, 29 (38, 12); refusal 6 (3).
* **Self-test beyond pytest** (`.sdk-tools/scratch/live/`: `start.sh` up / api / web, `cdp_pf11b.mjs`): `fake_ai_upstream.py` on :18794 playing the app's scripts, uvicorn on :18094 (fresh SQLite, a throwaway licence key, `ANTHROPIC_BASE_URL` at the fake, `SITE_URL` the served build), `serve-out.py` :3194 on an `out/` built against that API; a Pro-trial account (`demo_replica.py login --trial`). `demo_ai.py`:
  ```text
  ### balance
  {"credits_remaining": 2000, "allowance_monthly": 2000, "top_up_remaining": 0, "resets_at": "2026-11-01T00:00:00Z", "plan": "pro",
   "top_up_url": "http://127.0.0.1:3194/dashboard/cloud/#ai-credits", "usage_url": "http://127.0.0.1:3194/dashboard/cloud/#ai-usage",
   "allowance_remaining": 2000}
  ### count
  {"input_tokens": 5120, "max_credits": 185}
  ### window
  you: Put a window on the north wall of the study, 1.2 m wide
  I'll find the study's north wall first.
  [tool call] find {"kind": "wall", "room": "Study", "facing": "n"}
  [credits] 22 charged, 1978 left (served by anthropic truebex-assist)
  [tool result] {"matches": [{"ref": "0199c6a2e00070018000000000000001", "kind": "wall", "room": "Study", "facing": "n", "length_mm": 3600}]}
  Placing a 1.2 m window.
  [tool call] place {"kind": "window", "host": "0199c6a2e00070018000000000000001", "width_mm": 1200}
  [credits] 23 charged, 1955 left (served by anthropic truebex-assist)
  [tool result] {"placed": true, "ref": "b43d1b81ea1d3e5c9dd2dccbc587b53d", "host": "0199c6a2e00070018000000000000001"}
  Done: a 1.2 m window on the study's north wall.
  [credits] 24 charged, 1931 left (served by anthropic truebex-assist)
  [stop] end_turn
  ### summary (no tools, no tool_choice)
  Noted.
  [credits] 4 charged, 1927 left (served by anthropic truebex-assist)
  [stop] end_turn
  ### balance
  {"credits_remaining": 1927, …, "allowance_remaining": 1927}
  ```
  The fake logged `window/01-find.sse`, `02-place.sse`, `03-end.sse` (turns 1-3 of window) and `echo/01-end.sse`; the three window rows of `ai_usage` share one `session_id` (5120/58 → 22 `find`, 5420/47 → 23 `place`, 5730/18 → 24). The end of one raw stream (`curl -N`, the first window turn; `X-Truebex-Contract: ai-proxy/1.1`, `text/event-stream`):
  ```text
  event: message_delta
  data: {"type":"message_delta","delta":{"stop_reason":"tool_use","stop_sequence":null},"usage":{"output_tokens":58}}

  event: truebex_credits
  data: {"charged":22,"remaining":1905,"served_by":{"provider":"anthropic","model":"truebex-assist"}}

  event: message_stop
  data: {"type":"message_stop"}
  ```
  Headless Edge, signed in as that account: `/dashboard/cloud/#ai-usage` scrolled to the page's end with Recent turns fully in view (top 279 px of 808, the page too short to bring it to the 96 px margin), five rows 22 `find`, 4, 24, 23 `place`, 22 `find`; `#ai-credits` still lands on the section's top (96 px); no console error: 8 of 8 checks. The human test's PowerShell lines were run as written in Windows PowerShell 5.1 (other ports): the same output.
* **Readings** ("PATCH" = a dated line for the contract's *Changes* the app side should consider):

  | # | Reading | Stub (app) | Platform | Action |
  |---|---|---|---|---|
  | R1 | 5.2's URLs | `/dashboard/billing/`, `/dashboard/usage/` | `/dashboard/cloud/#ai-credits`, `/dashboard/cloud/#ai-usage` | PATCH 1 |
  | R2 | `charged` in the `.sse` files | the stub's ledger (above) | §6.2 from the usage | asserted; PATCH 3 if the app wants them consistent |
  | R3 | `message_start.message.model` | the alias | relayed as the provider sends it | kept (decision above) |
  | R4 | 401 for a revoked, signed-out or unknown device token | `unauthenticated` | `device_revoked` (licence-api §7's code, shared `_resolve_device`); no token or a non-token is `unauthenticated` | pinned in the test; the app's panel maps every 401 to its sign-in prompt and keeps the token (`AssistantProxy.cpp:549`, §8). PATCH 4 |
  | R5 | `data` of an envelope with nothing to say (401, 500, the per-minute 429) | `{}` | `null` (the shared envelope) | masked: no keys on either side. PATCH 5 |
  | R6 | extra `data` keys | — | `plan_required` `data.plan`; `rate_limited` (two in flight) `data.in_flight`; `too_large` `data.limit` | additive (§3), named in the test |
  | R7 | `retry_after_s` values | 429: 30, 503: 1 | in flight 2, the per-minute bucket's wait, 503 the provider's `retry-after` (else 10) | nullness and `Retry-After` asserted, values not |
  | R8 | `credits_exhausted` `data.plan_needed` | `team` | the next purchasable tier with a bigger allowance, else the plan's own (Studio → `studio`: Team's allowance is the same placeholder) | values not compared (GD7) |
  | R9 | `models.json` | `truebex-assist`, `truebex-fast` | `truebex-assist` (its entry equal) | stub data; GD7 |
* **Assertions moved for the re-copied files and the header** (nothing else in the existing suites changed; every other read of the window turns now finds PF11's own in `tests/fixtures/ai/` through `fake_provider.py`, unchanged):
  * `test_ai_proxy.py::test_ai_models_balance_and_count`: `models == models.json` → the app's `models.json` without the stub's `truebex-fast`; `set(balance-studio.json) <= set(bal)` → the app's `balance-studio.json` (now with `usage_url`, which the platform answers).
  * `test_ai_proxy.py::test_contract_header_and_error_envelope`: the echo and `data.supported` 1.0 → 1.1. `ai_helpers.AI` and `test_pf11_pf12_meet.py:112` send 1.1.
* **Deviations and why:**
  1. *`demo_ai.py`* sent a new `metadata.session_id` with every turn; one conversation now keeps one (§5's `session_id` row), and `summary` sends a tool-less turn (AI7's shape) for the human test.
  2. *`fake_ai_upstream.py`* plays the app's scripts by the stub's rules instead of looping PF11's window turns, so `demo_ai.py window` shows the capture working (`place`'s host is the wall the demo's `find` returned).
  3. *R4* is pinned, not changed: changing the code on `/ai` alone would split one device token's 401 across the platform.
* **Carry-over → which feature:**
  * AI3's carry-over **"PF11: the real endpoints"**: **done on the platform's side** (this task), except going live: the owner (api.truebex.com up, `ANTHROPIC_API_KEY`), then AI3's human test step 6 on the release build.
  * The owner / app side: the §11 cells and PATCH lines below.
  * GD7: rates, allowances, an alias per tier if wanted (`truebex-fast` is the stub's).
* **Contract §11 cells proposed for the platform column:**
  * `GET /ai/models`: "PF11: implemented (2026-10-10, `ap/t14`; 1.1.2 on 2026-10-22, PF11b `ap/t94`): the aliases the plan may use (`truebex-assist`), rates from the alias table".
  * `GET /ai/balance`: "PF11: implemented (allowance + top-ups; PF11b: `usage_url` = `/dashboard/cloud/#ai-usage`, the AI section's Recent turns; `top_up_url` `/dashboard/cloud/#ai-credits`; additive `allowance_remaining`)".
  * `POST /ai/messages`: "PF11: implemented (streamed and whole, §6.2 from the provider's usage, `truebex_credits` with additive `served_by`, §7 / §8; PF11b: the app's four scripts and `refusal.sse` pass through byte for byte, tool-less turns, `tool_choice` only with tools)".
  * `POST /ai/messages/count`: "PF11: implemented (the provider's count; `max_credits` = input plus `max_tokens` at the output rate)".
  * The header line: "platform not yet" → "platform implemented (PF11 2026-10-10, PF11b 2026-10-22; live when api.truebex.com is up)".
* **PATCH lines proposed:**
  1. "2026-10-22 · 1.1.2 (PATCH) · PF11b: 5.2's `top_up_url` and `usage_url` are whatever the platform answers. The platform's: `https://truebex.com/dashboard/cloud/#ai-credits` (where packs are bought) and `https://truebex.com/dashboard/cloud/#ai-usage` (the AI section's Recent turns); the examples' `/dashboard/billing/` and `/dashboard/usage/` are the stub's (the site's `/dashboard/usage/` lists API requests)."
  2. "5.2: `credits_remaining` is a number for every plan holding `ai.metered`. A plan with no monthly limit (`limits.ai_credits_month` null) would answer `credits_remaining` and `allowance_monthly` null, which the app's reader counts as an error (the site's Cloud page already shows null as "No monthly limit"): the contract should say either 'null = no limit; show it as unlimited' or 'never null' before such a plan exists (GD7)."
  3. "§9: the `.sse` files' `charged` values are the stub's. By §6.2 at `truebex-assist`'s 5.1 rates their usage costs window 22, 23, 24; paint 21, 23, 23; echo 4; create 26, 29; refusal 6: the stub takes these, or computes `charged` from the usage, if both sides should agree."
  4. "§7: a revoked, signed-out or unknown device token is 401 `device_revoked` on every platform route (licence-api §7's code); `unauthenticated` is no token or one that is no device token. The panel reads every 401 alike (§8)."
  5. "§7: `data` is `null` or `{}` when an error has nothing to add; readers treat both alike."
* **Merge note:** touches `server/app/ai/` (`credits.py`, `proxy.py`, `validate.py`, `adapters/anthropic.py`), `server/app/routers/ai.py`, `server/tests/contracts/ai-proxy/`, `server/tests/fixtures/ai/`, `server/tests/fakes/fake_provider.py`, the AI tests, `server/scripts/` (`demo_ai.py`, `demo_analysis.py`, `fake_ai_upstream.py`, `make_ai_proxy_fixtures.py`) and `src/components/cloud/AiCredits.tsx`, `src/lib/ai.ts`. PF12d (packages/mcp, tools.json, constants.ts, developer-docs.ts, the PF12 tests) shares none of them. README.md (two words in the PF11 section's first lines, one section at the end) and the tracker (one row at the end) are the usual end-of-file conflicts.
