# PF14a — Deploy skill: roadmap 40 release steps and secrets (launch priority 1)

**Needs merged:** PF1, PF2, PF13, PF14 (all on `master` after T16 and T17). **Unblocks:** the owner's first roadmap 40 deploy; every later feature that adds a release step or a secret (the gate test makes it update the skill). **Contract:** none.

## Status

**Built on branch `ap/t20-pf14a-deploy-skill-roadmap-40-re` (2026-10-10); see As-built.** Before this task, `.claude/skills/truebex-deploy/SKILL.md` on `master` (4758ae1) knew PF1's `sync:releases` and PF14's VM, but none of the steps the other features' As-built sections list around a deploy:

| Area | Where (master 4758ae1) | Before |
|---|---|---|
| Website steps | `.claude/skills/truebex-deploy/SKILL.md:20-26` | push, `.env.local`, `sync:releases` + build, copy, push, Pages, live routes. No `sync:roadmap`, no price check, no `indexnow`, no checks of `/pricing/`, `/checkout/` or `/billing/plans` |
| PF13 owner steps 1–6 | `PF13-…md` As-built, "Owner steps done" | Cloudflare Web Analytics, Search Console, Bing, `indexnow -- --sitemap`, `SOCIAL`, `sync:roadmap`: not in the skill (Search Console, Bing and IndexNow only in `truebex-seo`) |
| PF2 owner steps | `PF2-…md` As-built, carry-over "Owner" | `sync_prices.py` per environment, Paddle notification destinations, Paddle approval: not in the skill |
| Secrets and switches | `SKILL.md:55-58` | wildcards (`PADDLE_*`, `STRIPE_*`, `WAYL_*`, `TELEMETRY_*`); no per-file list, no note that Wayl is dormant or which settings must stay empty |
| Licence keys and releases | `SKILL.md:59-65` | `publish_release.py --key-file` "against the API host's settings", without saying how with the API on the VM; no symbols |
| `publish_release.py --symbols` | `server/scripts/publish_release.py`; promised by `server/scripts/upload_symbols.py:13` and PF14 As-built carry-over | absent |

## Goal

The owner deploys roadmap 40 from one page. `truebex-deploy` lists, in the order they run, every step the merged features need around a deploy (release feed, roadmap statuses, prices, IndexNow, live checks), every secret and switch with the file it lives in, and the site config the owner fills in. A release publishes the app's crash symbols in the same command. A pytest keeps the skill honest: the next feature that adds a release step or a billing secret fails the verify gate until the skill says how to run or set it.

## Read first

* `docs/roadmap/40/00-contract.md` P.2 to P.4.
* As-built of `PF1-…md`, `PF2-…md`, `PF13-…md`, `PF14-…md` (PF2a: not written or merged on 2026-10-10).
* `.claude/skills/truebex-deploy/SKILL.md`, `.claude/skills/truebex-seo/SKILL.md` (Search Console, Bing, IndexNow).
* `server/app/config.py` (every setting), `infra/secrets/*.env.example` and `README.md`, `infra/host/compose.yaml`, `infra/deploy.ps1`, `infra/CUTOVER.md`.
* `scripts/sync-releases.mjs`, `scripts/sync-roadmap.mjs` (argument order), `scripts/indexnow.mjs`, `server/scripts/sync_prices.py`, `server/scripts/publish_release.py`, `server/scripts/upload_symbols.py`.
* `src/lib/constants.ts` (`ANALYTICS`, `VERIFICATION`, `SOCIAL`), `src/lib/site-config.ts`.

## Scope

**In:**

1. Before the build, in order: `npm run sync:releases` (PF1); `npm run sync:roadmap -- <app tracker> <platform tracker>` with `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\README.md` first and `docs/roadmap/40/README.md` second (PF13); a check that `server/app/catalogue.json` `prices_final` is what the owner intends, and that `server/scripts/sync_prices.py` ran against the target environment's provider (dry run first).
2. Secrets and switches and where each lives (`infra/secrets/*.sops.env` → `/opt/truebex/secrets/` on the VM, never the repo): every billing setting `server/app/config.py` reads (`BILLING_PROVIDER`, `PADDLE_*`, `STRIPE_*`, `WAYL_ENABLED` and `WAYL_*`), the licence keys (`LICENCE_SIGNING_KEY`, `RELEASE_PUBLIC_KEYS`, …) and PF14's (core, storage, mail, alerts, telemetry, Postgres and wal-g, host checks, origin certificate).
3. The site config in `src/lib/constants.ts` (`ANALYTICS.cloudflareToken`, `VERIFICATION.google` and `.bing`, `SOCIAL`), noting that an empty value hides the feature, and PF13's one-off owner steps (Cloudflare Web Analytics, Search Console, Bing).
4. After the deploy: `npm run indexnow -- --sitemap`, and the live checks for `/pricing/`, `/changelog/`, `/download/`, `/checkout/` (`noindex`) and `GET /billing/plans`.
5. `server/tests/test_deploy_skill.py` (no build needed): the skill names `sync:releases`, `sync:roadmap`, `sync_prices.py`, `indexnow`, `publish_release.py --symbols` and every `PADDLE_` setting `config.py` defines.
6. PF14's carry-over to PF1: `publish_release.py --symbols <dir>` calls `scripts.upload_symbols.upload()` for that folder after the release is published; a pytest with the upload mocked; the skill's release step names the flag.

**Out (and where it goes):** running any of these steps or deploying (the owner, never a task); the GD5 and GD6 owner decisions (tax wording, social handles, the Arabic review); PF2a (not written yet: when it lands, its settings either appear in the skill or fail this gate).

## Design

**Skill** (`.claude/skills/truebex-deploy/SKILL.md`; structure and voice kept, sections added):

| Section | What it holds |
|---|---|
| Order of a release | merge + tests → API (`infra\deploy.ps1`) → prices (`sync_prices.py`) → app release (`publish_release.py … --symbols`) → website. The site's sync steps read the live API, so the API goes first |
| Website | 11 steps: push `master`; `.env.local`; `sync:releases`; `sync:roadmap` (app tracker, platform tracker); `prices_final` + `sync_prices.py`; build and verify; copy; push `main`; Pages run; live checks (all routes, then `/pricing/`, `/changelog/`, `/download/`, `/checkout/` `noindex` and not in the sitemap, `/billing/plans`); `npm run indexnow -- --sitemap`. `deploy-to-server.bat` covers 6–8 only |
| Site config | `ANALYTICS.cloudflareToken`, `VERIFICATION.google`, `VERIFICATION.bing`, `SOCIAL`: what each turns on, empty = hidden, the one-off owner step |
| App releases | `make_signing_key.py`; `publish_release.py … --symbols`; the production settings set in the shell for that run (the Postgres SSH tunnel of `infra/CUTOVER.md`, `STORAGE_BACKEND=s3`, `S3_*`, `RELEASE_PUBLIC_KEYS`), never in `server/.env`; the `POST /admin/releases` + `POST /admin/symbols` alternative |
| Billing | Paddle default, Stripe secondary, Wayl dormant; a provider is on only with its API key and webhook secret; `docker compose exec api python -m scripts.sync_prices --provider paddle --env production --dry-run`, then without `--dry-run`; `--env` must match `PADDLE_ENV`; the Paddle notification destinations per environment (events `subscription.*`, `transaction.*`) and the Stripe webhook; Paddle seller and domain approval; archiving founding prices |
| API | unchanged, minus the Secrets and Licence bullets (moved) |
| Secrets and switches | where they live and how to change one (`sops`, `infra\deploy.ps1`, no site rebuild); `server.sops.env` by area with "empty means"; `postgres.sops.env`, `host.sops.env`, `origin.*.sops.env`; what `compose.yaml` sets; what never reaches the VM |

**Gate** (`server/tests/test_deploy_skill.py`): reads the skill and `config.py`'s `Settings.model_fields`, `infra/secrets/*.env.example`, `package.json`, `scripts/sync-roadmap.mjs` and `src/lib/constants.ts`. Names are matched whole (`PADDLE_API_BASE` does not count for `PADDLE_API`), so a wildcard like `PADDLE_*` never satisfies it.

**`publish_release.py`:** `--symbols <dir>` and `--dump-syms <exe>`. Before publishing, `symbols_problem()` refuses (argparse error, exit 2, nothing published) a path that is not a folder, a folder with no `.sym` / `.pdb`, or `.pdb` files with no `dump_syms`. After publishing it calls `upload_symbols.upload([dir], version, dump_syms)` and prints one `symbols:` line per file. If the upload fails, the release stays published, the exit code is 1 and the `python -m scripts.upload_symbols` command that retries it is printed.

**Security and privacy:** the skill names settings, never values. Secrets stay in `infra/secrets/*.sops.env` and `/opt/truebex/secrets/`. The `rel-*` seed, the age key and the `tofu` state passphrase never reach the VM. Production settings for a release run are set in the shell only. The values in `constants.ts` are public by design.

## Deliverables

- [x] `.claude/skills/truebex-deploy/SKILL.md`: Order of a release, Website steps 1–11, Site config, App releases, Billing, Secrets and switches
- [x] `server/tests/test_deploy_skill.py` (9 tests)
- [x] `server/scripts/publish_release.py` `--symbols`, `--dump-syms`, `symbols_problem()`
- [x] `server/tests/test_releases.py`: two tests with the upload mocked
- [x] `README.md` release example with `--symbols`
- [x] This doc, and the PF14a row in `docs/roadmap/40/README.md`

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_deploy_skill_names_release_steps` | pytest | `npm run sync:releases`, `npm run sync:roadmap`, `sync_prices.py` (a `--dry-run` and an `--env production` line), `prices_final`, `npm run indexnow -- --sitemap`, and `publish_release.py … --symbols <dir>` in the App releases section |
| `test_deploy_skill_website_steps_in_order` | pytest | in *Website*: `sync:releases` < `sync:roadmap` < `prices_final` < `sync_prices` < `npm run build` < `git push origin main` < `indexnow -- --sitemap` |
| `test_deploy_skill_sync_roadmap_names_both_trackers` | pytest | the script still takes the app tracker first; the skill's command names the app tracker before `docs/roadmap/40/README.md` |
| `test_deploy_skill_names_every_paddle_setting` | pytest | every `paddle_*` field of `Settings`, upper-cased, named whole |
| `test_deploy_skill_names_every_billing_and_licence_setting` | pytest | every `billing_`, `paddle_`, `stripe_`, `wayl_`, `licence_`, `release_`, `signing_` setting; `BILLING_PROVIDER=paddle`; `WAYL_ENABLED=false` |
| `test_deploy_skill_names_every_vm_secret` | pytest | `/opt/truebex/secrets/`, each `infra/secrets/<name>.sops.env`, and every credential (`…KEY`, `…KEYS`, `…SECRET`, `…PASSWORD`, `…TOKEN`, `…_ID`) in the templates |
| `test_deploy_skill_site_config_keys_exist` | pytest | `ANALYTICS.cloudflareToken`, `VERIFICATION.google` / `.bing`, `SOCIAL` named and defined in `constants.ts`; Cloudflare Web Analytics, Search Console, Bing Webmaster Tools, `sitemap.xml` |
| `test_deploy_skill_live_checks` | pytest | `/pricing/`, `/changelog/`, `/download/`, `/checkout/` (routes exist in `src/app/`), `/checkout/ … noindex`, `/billing/plans` |
| `test_deploy_skill_commands_exist` | pytest | every `npm run <x>` is a `package.json` script; every `scripts\<x>.py` / `-m scripts.<x>` exists |
| `test_publish_release_script_uploads_symbols` | pytest | `--symbols` calls the (mocked) `upload([dir], version, None)` once, after the release row exists; `--dump-syms` is passed through; no flag, no call |
| `test_publish_release_symbols_checked_before_publishing` | pytest | missing folder, empty folder, `.pdb` without `dump_syms` → exit 2, no release, no upload; an upload that raises → exit 1, the release stays, the retry command is printed |

## Human test

Window 1, in the worktree: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` (serves `out/` on `http://127.0.0.1:3120/`).

1. Open `.claude/skills/truebex-deploy/SKILL.md` (any Markdown preview). Read *Order of a release*, *Website* 3–5 and 10–11, *Billing* and *Secrets and switches* → the tracker path, the Paddle hosts and the dashboard steps match your accounts; no value of a secret appears anywhere.
2. `http://127.0.0.1:3120/pricing/` → every paid tier says "Price at launch" (`prices_final` is `false`). `/changelog/` and `/download/` load. `http://127.0.0.1:3120/checkout/` → view source: a `robots` meta with `noindex`; `out/sitemap.xml` has no `/checkout/`.
3. Window 2, in the worktree: `npm run indexnow -- --dry-run --sitemap` → prints the IndexNow request with the `truebex.com` URLs from `out/sitemap.xml` and sends nothing. `npm run sync:roadmap -- T:/unreal5_7_4_projects/truebex_compact/Docs/roadmap/40/README.md docs/roadmap/40/README.md --check` → lists the statuses that would change and writes nothing.
4. Window 2, in `server\`: set a scratch API, start the Paddle mock and sync prices:
   `$env:DATABASE_URL='sqlite:///./pf14a-try.db'; $env:STORAGE_DIR='./pf14a-try-storage'; $env:PADDLE_API_KEY='pdl_sdbx_apikey_mock'; $env:PADDLE_WEBHOOK_SECRET='pdl_ntfset_mock_secret'; $env:PADDLE_API_BASE='http://127.0.0.1:8098'`, then
   `Start-Process -WorkingDirectory $PWD .venv\Scripts\python.exe '-m uvicorn tests.mock_paddle:app --port 8098'`, then
   `.venv\Scripts\python.exe -m scripts.sync_prices --provider paddle --env sandbox --dry-run` → `36 prices, 36 new`, every line "(would create)". Without `--dry-run` → `36 prices, 36 new` with `pri_…` ids; again → `36 prices, 0 new`. With `--env production` → refused (`PADDLE_ENV=sandbox`).
5. Same window: `Start-Process -WorkingDirectory $PWD .venv\Scripts\python.exe '-m uvicorn app.main:app --port 8000'`, then `curl.exe -s http://127.0.0.1:8000/billing/plans` → `"provider":"paddle"`, `"providers":["paddle"]` (no `wayl`), Pro, Studio and Team with 6 prices each.
6. Same window: `.venv\Scripts\python.exe scripts\make_signing_key.py --kind rel --kid rel-try-2026-10 --out $env:TEMP\rel-try.json`; `Set-Content $env:TEMP\notes.md '### 1.1.0'`; then
   `.venv\Scripts\python.exe scripts\publish_release.py --version 1.1.0 --channel stable --file ..\package.json --notes $env:TEMP\notes.md --key-file $env:TEMP\rel-try.json --symbols tests\fixtures\symbols` → a warning that the kid is not in `RELEASE_PUBLIC_KEYS` (expected here), the version, SHA-256 and storage key, then `symbols:     Truebex-CadCore.pdb  4C1D9A0E5B7F4A3C9E2D1F0A8B7C6D5E1  symbols/…/Truebex-CadCore.sym`. The same with `--version 1.1.1 --symbols nowhere` → `publish_release.py: error: --symbols nowhere is not a folder`, and `curl.exe -s http://127.0.0.1:8000/releases/feed` shows `"latest":"1.1.0"` with no 1.1.1.
7. Close the two started windows; delete `server\pf14a-try.db` and `server\pf14a-try-storage\`.

## Risks / traps

* The gate matches whole names: a feature that adds `PADDLE_SOMETHING` to `config.py`, or a credential to an `infra/secrets/*.env.example`, turns the verify gate red until the skill names it. That is the point; name the setting in *Secrets and switches* with what empty means.
* The order test reads the first occurrence of each step inside *Website*: mentioning `npm run build` or `indexnow` early in that section (for example in step 2) fails it. Put cross-references in other sections.
* A provider is on only with both its API key and its webhook secret: a key alone leaves `/billing/plans` at `provider: null` and checkout at 503.
* `sync_prices.py` writes `provider_prices` into the database of the settings it runs with: on the VM, run it inside the `api` container; run locally, it fills the local database.
* `publish_release.py` with the production settings writes production data from the owner's PC: set the variables in that shell only and close it afterwards; never put them in `server/.env`.
* `--symbols` with `.pdb` files needs `dump_syms` (MIT / Apache-2.0) on the PC that publishes. Without it the script refuses before publishing; `.sym` files need nothing.
* Git Bash rewrites `/pricing/`-style arguments (`indexnow.mjs` undoes it); the skill's paths are Windows or relative.

## As-built

* **Date, branch, commits:** 2026-10-10, `ap/t20-pf14a-deploy-skill-roadmap-40-re` from `master` 4758ae1 (after T16 and T17). `e4b8937` (skill, gate, `--symbols`, README), then the commit with this doc and the tracker row.
* **Counts:** pytest 180 → 191 collected (`test_deploy_skill.py` 9, `test_releases.py` +2). The skill's *Website* went from 7 steps to 11, plus five new sections (*Order of a release*, *Site config*, *App releases*, *Billing*, *Secrets and switches*). No site or API behaviour changed, so `out/` is unchanged.
* **Self-tests beyond pytest:**
  * Mutations of the skill or its sources, each of which turned the gate red: `PADDLE_API_BASE` removed; `--symbols` removed from the release command; a new `paddle_retain_key` setting in `config.py`; `indexnow` moved before the build; a `MONITOR_API_TOKEN=` line added to `host.env.example`; the two trackers swapped.
  * `publish_release.py --symbols` for real (no mock) on a scratch SQLite database and local storage, with a key from `make_signing_key.py`: release row, `symbol_files` row, the installer and `.sym` blobs in the Breakpad layout. A missing folder was refused with exit 2 before anything was published.
  * `sync-roadmap.mjs` with the skill's arguments and `--check`: it read both trackers in that order (2 statuses would change; nothing written).
  * `python -m scripts.sync_prices` (the skill's container form) against `tests/mock_paddle.py`: dry run listed 36 prices and wrote nothing; `--env production` was refused against `PADDLE_ENV=sandbox`; a real run created 36; a second run created 0.
  * A local API on that database: `GET /billing/plans` answered `provider: paddle`, `providers: [paddle]`, and 6 prices for Pro, Studio and Team. With the API key but no webhook secret it answered `provider: null`, so the skill now says a provider needs both.
* **Deviations and why:**
  1. The gate goes beyond `PADDLE_`. It covers every billing and licence setting, every credential in the VM secret templates, the order of the steps, the tracker order and that each command the skill names exists. Scope 2 asks the skill to name all of these, and "the next feature that adds a billing secret fails the gate" holds only if the gate checks them.
  2. The symbols folder is checked before anything is published (a release cannot be unpublished). `--dump-syms` is passed through because `upload()` takes it. An upload that fails after publishing exits 1 and prints the retry command instead of hiding the error.
  3. The *Secrets* and *Licence API* bullets moved out of *API* into *Secrets and switches* and *App releases*, so each setting is described in one place.
  4. Running the release script against the VM: the skill sets the production settings in the shell for that run (the Postgres SSH tunnel of `infra/CUTOVER.md`, the data bucket's `S3_*`), because the `rel-*` seed must never reach the VM. `POST /admin/releases` plus `POST /admin/symbols` is the alternative without a tunnel.
  5. `PADDLE_API_BASE` is named as "empty on the VM": it is a test and mock override, not a secret.
* **Contract:** none; nothing to record in the Unreal repo's `contracts/`.
* **Carry-over → which feature:**
  * PF14's "PF1: `publish_release.py --symbols`" is done here.
  * PF2a (not merged on 2026-10-10): its settings and steps go into the skill, which the gate enforces for settings.
  * The owner: the one-off steps the skill now lists (Paddle approval and notification destinations, `sync_prices.py` per environment, Cloudflare Web Analytics, Search Console, Bing, `SOCIAL`), run at the first roadmap 40 deploy.
