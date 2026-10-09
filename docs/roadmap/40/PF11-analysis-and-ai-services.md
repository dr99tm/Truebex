# PF11 — Analysis and AI services (launch priority 3)

**Needs merged:** PF6. **Unblocks:** none. **Contracts:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\render-jobs.md` (v1.0.0: the analysis kinds and result, PF11 per its §11) and `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\ai-proxy.md` (v1.0.0: the metered assistant proxy, PF11 per its §11).

## Status

No analysis runner, AI proxy, credits or hosted model exists (`00-contract.md` P.1). What this builds on, verified with Grep on 2026-10-09:

| Area | Where | Today |
|---|---|---|
| Provider-failure answer | `server/app/routers/billing.py:124-129` | 502 with a plain message; the proxy maps upstream failures the same way (`ai-proxy.md` §7) |
| Plan-limit answer | `server/app/routers/keys.py:45-47` | 403; credits and plan checks answer like it |
| From PF6 (Needs) | the queue, worker tokens and claim protocol, `WorkerPool`, cost units and `meter_daily`, the Cloud usage page | analysis kinds and the `cpu-8` and `gpu-ai` classes plug in |
| From PF1, PF2 | device tokens, entitlement features `analysis.reports` and `ai.metered`, `limits.ai_credits_month`; PF2's checkout for one-off top-ups | |

What the owner meant: app-side `00-understanding.md` §6 ("wind and airflow through OpenFOAM jobs on the cloud workers") and §10 ("a metered Truebex AI tier through the platform; local models on the GPU for instant suggestions").

## Goal

Heavy analyses run on the platform's workers instead of the designer's PC — "submit a wind study and see the pressures on the facade an hour later" (`00-understanding.md` §6) — with the cost of each run estimated before and charged after; and people without a model key of their own use the in-app assistant through a metered proxy that charges credits, passes tools through untouched and keeps no message content (§10), with open models hosted on the platform's GPUs where they are cheaper for heavy generation.

## Read first

* **`contracts/render-jobs.md` v1.0.0** — §4 (worker tokens), §5.1 (kinds `wind`, `energy` and their inputs and params), §6.3 (`truebex-analysis/1` results: fields on faces, spaces or points, grids, the report), §6.4 (cost units, class weights), §10–11.
* **`contracts/ai-proxy.md` v1.0.0** — §4 (device tokens with `ai.metered` only), §5 (models, balance, messages, count), §6.1 (the alias table and the Anthropic adapter: refusal fallback, thinking on, cache breakpoints), §6.2 (credits), §7 errors, §8 retry, §9 fixtures (copied into `server/tests/contracts/ai-proxy/`), §10 platform tests.
* `contracts/agent-interface.md` §6.5 (the tools the proxy passes through).
* `guides/GD2-*.md` (validation cases and tolerances), `guides/GD3-*.md` (CPU and GPU classes, prices) and `guides/GD7-*.md` (credit rates, allowances, top-ups) are not written yet: placeholders.
* The `claude-api` skill (model ids, streaming events, usage fields, refusal fallbacks) for the Anthropic adapter.

## Scope

**In:**
1. Analysis job runners as worker images on the PF6 queue: `wind` (OpenFOAM, GPL-3.0, run as a service, never distributed), `energy` (EnergyPlus, BSD-3-Clause) and `acoustics` (an open room-acoustics ray tracer, permissive licence; the kind is a MINOR addition to `render-jobs.md` §5.1 proposed below), each a Linux container run by PF6's worker wrapper in a container mode on CPU workers (`cpu-8`).
2. Results written as `truebex-analysis/1` (§6.3): fields on faces with entity ids per triangle, fields on spaces, grids, a summary, an optional report PDF; validated on completion (422 `output_invalid`).
3. A weather library for `energy` (`params.weather` ids → EPW files with source and licence recorded) and the wind terrain classes.
4. The AI proxy of `ai-proxy.md`: `GET /ai/models`, `GET /ai/balance`, `POST /ai/messages` (streamed or whole), `POST /ai/messages/count`; the alias table; the Anthropic adapter; tools and tool results passed through byte for byte; the `truebex_credits` event; no message content kept.
5. Metered credits for the Truebex AI tier: the monthly allowance from `limits.ai_credits_month` (reset on the 1st, no roll-over), top-ups bought on the website through PF2, the §6.2 charge per turn, refusal when empty, usage records kept 400 days.
6. Hosted open models on GPU workers for heavy generation: an open-weight language model with a licence that allows commercial hosting, served by an OpenAI-compatible inference server (Apache-2.0) on `gpu-ai` workers, reached through a `selfhosted` adapter behind an alias, with a fallback alias when no server is warm; and a `texture` generation kind (seamless PBR maps for AI5's materials) behind `AI_TEXTURE_ENABLED` until its MINOR addition to `render-jobs.md` lands.
7. Cost per run metered and shown: an estimate before submission (wind: cells × iterations; energy: zones × timesteps; acoustics: rays × sources), cost units charged on success with the class weight, shown in 5.1's answer, in the app (AN3), on the Cloud usage page by kind, and per AI turn in the `truebex_credits` event and the dashboard.
8. Tests: the `ai-proxy.md` §10 platform tests, analysis tests against stub solvers and fixture outputs, a pytest per endpoint.

**Out (and where it goes):**
* Exporting the watertight geometry and the energy model, showing fields on the model, report sheets → AN2, AN3, AN4 (app); validation against reference cases → GD2 (no public claim before it, `00-understanding.md` §6).
* People flow, comfort and structural solvers → AN5, AN6 (app, local).
* The own-key assistant and local models on the user's GPU → AI2, AI4 (app); the assistant panel → AI3.
* Provider choice for GPU and CPU machines, prices → GD3; credit rates and allowances → GD7.

## Design

### API

| Endpoint | Contract | Platform behaviour |
|---|---|---|
| `POST /jobs` with `wind`, `energy` (and `acoustics`) | `render-jobs.md` 5.1 | feature `analysis.reports` (403 `plan_required`); inputs as a `job-input` upload; the estimate in cu from the kind's model; class `cpu-8` |
| `POST /workers/claim` … `complete` | 5.7–5.10 | analysis workers claim only analysis kinds (token scope); `complete` validates §6.3 |
| `GET /jobs/{id}/output` | 5.5 | the result with signed file URLs for the binary arrays and the report |
| `GET /ai/models` | `ai-proxy.md` 5.1 | aliases the plan may use with limits and `credits_per_mtok` from `server/app/ai/aliases.json` (rates `from GD7`) |
| `GET /ai/balance` | 5.2 | allowance left, top-ups left, reset date, `top_up_url` |
| `POST /ai/messages` | 5.3 | device token with `ai.metered`; body ≤ 8 MB; §5 rules checked (alias, `tool_choice` auto or none, images, `max_tokens`); credits > 0 and covering the input estimate; `Idempotency-Key` refused when repeated within 10 min (409 `duplicate_request`); ≤ 2 turns in flight and 60 a minute per account (429) |
| `POST /ai/messages/count` | 5.4 | the provider's token count for the body and `max_credits` (input plus `max_tokens` at the output rate) |

The alias table (`server/app/ai/aliases.json`, platform configuration, changed without an app release):

| Alias | Adapter | Provider model | Notes |
|---|---|---|---|
| `truebex-assist` | `anthropic` | `claude-opus-5-5` (`ai-proxy.md` §6.1) | thinking always on (the model cannot turn it off); effort set explicitly per alias; refusal fallback `fallbacks: "default"` with beta `server-side-fallback-2026-07-01`; cache breakpoint after `tools` and `system` |
| a second alias, `from GD7` | `selfhosted` | an open-weight model on `gpu-ai` | for heavy generation and unattended runs (AI7); falls back to `truebex-assist` when no server is warm |

**Decision: the Anthropic adapter uses the official `anthropic` Python SDK and relays the provider's server-sent events line by line** (the SDK's streaming-response access to the raw lines), reading only `usage` from `message_start` and `message_delta`, so `tool_use` blocks reach the app byte-equal (`test_tool_use_passthrough`) and one `event: truebex_credits` is inserted before `message_stop`. Rejected: re-serialising parsed stream events (key order and escaping could change a block); raw HTTP calls beside the SDK (two clients to keep in step).

| Upstream answer | Proxy answer (`ai-proxy.md` §7) |
|---|---|
| 400 invalid request | 422 `upstream_rejected` with `data.provider_message` |
| 429 rate limit, 529 overloaded | 503 `upstream_busy` with `retry_after_s` from `retry-after` |
| 5xx, network failure before output | 502 `upstream_failed`, nothing charged |
| failure after output began | in-band `event: error` with the envelope; charged for what the provider billed |
| `stop_reason: "refusal"` | passed through with `stop_details`; credits for the tokens billed |

### Data

| Table / file | Fields | Notes |
|---|---|---|
| `analysis_weather` | `weather_id`, `name`, `location`, `source`, `licence`, `storage_key` | EPW files; the source and licence of each recorded for GD2 |
| `server/app/analysis/` runners | `wind/` (case template: domain sized from the building height, refinement around the building, a log-law inlet from the terrain class, steady RANS, residual target and iteration cap from GD2), `energy/` (EnergyPlus with the uploaded model and the weather file, outputs read from its SQL output), `acoustics/` | each runner a container image `truebex-analysis-<kind>:<version>` with `run.sh` reading `/job/job.json` and writing `/job/out/` |
| `ai_balances` | `account_kind`, `account_id`, `allowance_remaining`, `top_up_remaining`, `resets_at` | integers |
| `ai_credit_ledger` | `id`, `account`, `delta`, `kind` (`grant`, `expire`, `top_up`, `usage`, `refund`, `adjust`), `ref`, `balance_after`, `at` | append-only |
| `ai_usage` | `at`, `account`, `session_id`, `alias`, `provider_model`, `served_by`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `credits`, `tool_names` | kept 400 days; no text, no tool input, no image |
| `ai_servers` | `server_id`, `alias`, `base_url`, `state`, `warm_until` | the self-hosted inference servers PF6's pool runs |

Spend order: allowance, then top-ups (`ai-proxy.md` §6.2). Top-ups are one-off purchases through PF2's interface (a `create_checkout` with a one-time price; added there if PF2 lacks it).

### UI

| Page | Change |
|---|---|
| `src/app/dashboard/cloud/page.tsx` (PF6) | analysis kinds in the by-kind table with each run's cost; an AI section: credits left, allowance, reset date, recent turns (time, alias, credits, tools used), a Buy credits button (PF2 checkout) |
| `src/app/dashboard/admin/render/page.tsx` (PF6) | the CPU and `gpu-ai` classes, warm inference servers, AI spend by alias against provider cost |

### Jobs / workers

| Piece | What it does |
|---|---|
| `worker/truebex_worker.py --mode container` (PF6's wrapper) | claims analysis kinds; `docker run --network none --cpus <n> --memory <m> -v <job>:/job <image>`; uploads `/job/out/*`; reports `wall_s` and the class |
| `infra/worker/analysis/` | Dockerfiles for the three runners, pinned solver versions, built per release and pushed to the private registry |
| `ai.allowance.grant` | 00:00 UTC on the 1st: expires the unused allowance (ledger `expire`), grants the plan's `ai_credits_month` |
| `ai.servers.scale` | every 60 s: keeps `gpu-ai` inference servers warm in GD3's hours or while turns arrive; cold start is minutes (weights load), so the fallback alias answers meanwhile |
| `texture` runner (behind `AI_TEXTURE_ENABLED`) | an open image-generation model whose licence allows commercial hosting; writes albedo, normal and roughness maps that tile seamlessly; output schema proposed with the kind |

Contract changes this feature needs (written in the app repo's contracts first by the owner, C.9):

| Contract | Change (MINOR) |
|---|---|
| `render-jobs.md` §5.1, §6.3 | kind `acoustics` (CPU; inputs: room surfaces with absorption per band; params: sources, bands; result: grids and per-space fields) |
| `render-jobs.md` §5.1 | kind `texture` (GPU `gpu-ai`; params: prompt, size, seamless; output: map files) |

### Security and privacy

* The proxy stores no message text, tool input or image; logs carry token counts, tool names and credits only (`ai-proxy.md` §2).
* Provider keys live only in `server/.env`; the app never sends its own key on this path; the proxy answers only device tokens with `ai.metered`.
* Solver containers run with no network, capped CPU and memory, as a non-root user, on inputs the account uploaded; a job never sees another account's files.
* Self-hosted models run on workers that hold no user credentials; prompts reach them inside the platform's network only.

## Deliverables

- [ ] `server/app/analysis/` (kind registry, estimates, result validation, `weather.py`), the runner images under `infra/worker/analysis/`, PF6's wrapper container mode
- [ ] `server/app/ai/` (`aliases.json`, `adapters/anthropic.py`, `adapters/selfhosted.py`, `credits.py`, `proxy.py`), `server/app/routers/ai.py`; `anthropic` pinned in `server/requirements.txt`; `ANTHROPIC_API_KEY` and `SELFHOSTED_*` in `.env.example`
- [ ] `server/tests/fakes/fake_provider.py` (serves the contract's `.sse` fixtures as an upstream), `server/tests/fakes/stub_solver/` (returns `wind-result.json` and its arrays)
- [ ] `server/tests/contracts/ai-proxy/` and the analysis files of `server/tests/contracts/render-jobs/` copied from the app repo (copied, never edited)
- [ ] dashboard additions; contract §11 rows and the two render-jobs MINOR proposals recorded in As-built

## Tests

The first ten names are the `ai-proxy.md` §10 platform tests.

| Name | Kind | Asserts |
|---|---|---|
| `test_messages_requires_ai_metered` | pytest | 403 `plan_required` without the feature; 403 `forbidden` for a session token |
| `test_tool_use_passthrough` | pytest | a fake provider's `tool_use` reaches the client byte-equal; the next `tool_result` reaches the provider byte-equal |
| `test_stream_events_and_credits_event` | pytest | the §5 event order with `truebex_credits` before `message_stop`; `ping` at least every 15 s |
| `test_credits_charged_from_usage` | pytest | §6.2 arithmetic with cache read and write tokens; rounded up |
| `test_refuse_when_credits_empty` | pytest | refusal at zero with `plan_needed` and `top_up_url`; a started turn may end below zero |
| `test_forced_tool_choice_rejected` | pytest | `{"type": "tool"}` → 422 `validation_failed` |
| `test_upstream_errors_mapped` | pytest | 422 / 502 / 503 as §7; nothing charged before output |
| `test_no_content_retained` | pytest | after a turn no table holds the message text or tool input |
| `test_alias_mapping_server_side` | pytest | editing the alias table changes `served_by` with no client change |
| `test_contract_header_and_error_envelope` | pytest | header echoed; MAJOR 2 → 400; envelope in responses and in-band `error` events |
| `test_ai_models_balance_and_count` | pytest | 5.1 rates from the table; 5.2 buckets; 5.4 `max_credits`; 401 without device token |
| `test_ai_duplicate_request_and_rate_limits` | pytest | a repeated `Idempotency-Key` within 10 min → 409; a third turn in flight → 429 |
| `test_ai_allowance_grant_and_no_rollover` | pytest | the 1st: unused allowance expires, the new one is granted; top-ups survive |
| `test_ai_topup_checkout_via_billing` | pytest | Buy credits calls PF2's checkout (mocked); a verified webhook adds `top_up` credits |
| `test_ai_selfhosted_adapter_and_fallback` | pytest | Messages-format requests translate to the inference server and back; with no warm server the fallback alias answers |
| `test_analysis_submit_requires_feature` | pytest | `wind` without `analysis.reports` → 403 `plan_required`; without `inputs.files.geometry` → 422 |
| `test_analysis_stub_solver_round_trip` | pytest | the wrapper runs the stub solver image's output through `complete`; the result passes §6.3; cu charged at the `cpu-8` weight |
| `test_analysis_result_validation` | pytest | a field whose `count` differs from its array length → 422 `output_invalid` |
| `test_energy_output_parser` | pytest | a fixture EnergyPlus output yields `eui_kwh_m2_y`, `heating_kwh_y`, `cooling_kwh_y` and per-space fields |
| `test_texture_kind_behind_flag` | pytest | `texture` → 422 unknown kind while `AI_TEXTURE_ENABLED` is off |
| `npm run lint`, `npm run build` | build check | green |

## Human test

1. Local API with PF6 merged; Docker Desktop on this PC; build the `wind` image (`infra/worker/analysis/wind/build.ps1`); issue a worker token for `wind`, `energy` and run `worker\truebex_worker.py --mode container`.
2. Submit a wind job from the app (an AN3 build: Analyse → Wind → Submit) or with `curl` (`kind: wind`, the fixture STL uploaded as `job-input`, `speed_ms` 5, `direction_deg` 225) → the answer shows `cost_units_estimate`.
3. The worker console shows the container running the mesh, the solve and the export (minutes on a small house); the job ends `succeeded` with `cost_units`.
4. `GET /jobs/{id}/output` → a `truebex-analysis/1` result with `pressure_coefficient` on faces and the `comfort_lawson` grid; in the AN3 build the facade shows the false-colour pressures with the legend's unit.
5. Dashboard → Cloud: the wind run with its cost next to the panorama jobs.
6. AI: put an Anthropic key in `server/.env`; activate a device on a plan with `ai.metered` (or a Studio stub entitlement per AI3); in an AI3 build ask "Put a window on the north wall of the study, 1.2 m wide" → the assistant streams, calls `find` then `place`, the window appears; the panel shows the credits charged.
7. Dashboard → Cloud → AI shows the turn's credits and tools; the database holds no text of the conversation.

## Risks / traps

* A real OpenFOAM case on a house takes many CPU minutes and gigabytes: tests use the stub solver; the real image is exercised in the human test and on the workers only.
* OpenFOAM is GPL-3.0: running it as a service is allowed; shipping it inside the app would not be (the app keeps its local coarse estimate, AN3).
* Results are reports, never certificates; no number is claimed publicly before GD2's case passes (`00-understanding.md` §6).
* The default model always thinks: the adapter never sends a disabled thinking setting, and `tool_choice` is `auto` or `none` only (`ai-proxy.md` §5).
* Byte-equal passthrough breaks the moment anything re-serialises a block: the adapter must relay raw event lines.
* Credits are money: the ledger is append-only and every balance change has a reference; the monthly grant must be idempotent per month.
* Hosted models need a licence that allows commercial hosting and a GPU class from GD3; until both exist the second alias stays off.

## As-built

* Date, branch, commits:
* Counts (pytest before → after); measured wall time and cu per kind on the first workers:
* Deviations from Design and why:
* GD2 / GD3 / GD7 inputs adopted (cases, classes, credit rates):
* Contract §11 rows for the owner to set to "PF11: done" in `contracts/ai-proxy.md` and `contracts/render-jobs.md`; the MINOR proposals (`acoustics`, `texture`):
* Carry-over → which feature:
