# 00 — Contract for the platform half of roadmap 40 (read me before ANY platform task)

The request, the understanding and the app half live in the Unreal project:
`T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\` (`00-request.md`, `00-understanding.md`,
`00-contract.md`). Its C.9 names the **contract documents** both halves build against, in
`T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\` (the app side is authoritative;
a change is made there first, with a dated note). This file holds only what is specific to this
workspace.

## P.1 Ground truth (2026-10-09)

* **Site**: Next.js 16 static export (`next.config.ts`: `output: "export"`, `trailingSlash: true`,
  `assetPrefix: "/"`), Tailwind 4, `src/app/` routes (landing `page.tsx` with SoftwareApplication +
  FAQPage JSON-LD, `login/`, `signup/`, `dashboard/` with `keys/`, `usage/`, `billing/`,
  `developers/`, `privacy/`, `terms/`, `sitemap.ts`, `robots.ts`, `manifest.ts`). ALL copy lives
  in `src/lib/constants.ts` (`FEATURES` = shipped only, `ROADMAP`, `PRICING_PLANS`, `FAQS`,
  `SITE`). Brand and claims rules: `.claude/skills/truebex-brand-voice/SKILL.md`; per-page SEO
  checklist: `.claude/skills/truebex-seo/SKILL.md`. Deploy flow (never run by a task):
  `.claude/skills/truebex-deploy/SKILL.md`.
* **API** `server/` (FastAPI + SQLAlchemy + SQLite `auth.db`, additive migrations in
  `database._ADDED_COLUMNS`): routers `auth` (email + password, Google ID token), `keys`
  (hashed API keys shown once), `usage` (per key / endpoint / UTC day, `X-RateLimit-*`),
  `billing` (Stripe Checkout subscriptions + portal + signed webhooks; Wayl 30-day links with
  server-side verification; `plans.py` catalogue free / pro / enterprise; `billing/service.py`
  `effective_plan`), `v1` (`/v1/ping`, `/v1/account`, API-key auth, metered). Tests:
  `server/tests/` (pytest; `conftest.py` sets the env; `mock_wayl.py`). Runs in production on
  the owner's PC behind a Cloudflare tunnel (`start-server.bat`, `start-tunnel.bat`) — PF14 moves it.
* **No** licence or entitlement concept, no device model, no release feed, no organisations,
  no project storage, no share pages, no jobs, no marketplace, no supplier accounts, no mobile
  client, no telemetry ingestion.
* **Demo form**: Google Apps Script (`google-apps-script/`).

## P.2 How a task runs here

Claude Autopilot in this workspace: base branch `master`, worktrees under `X:\Truebex-autopilot\`,
setup `scripts/autopilot-setup.ps1` (copies `.env.local`, `npm ci`, creates `server\.venv` with
Python 3.12 and installs `requirements-dev.txt`), the verify gate `scripts/autopilot-verify.ps1`
(`npm run lint`, `npm run build`, `pytest -q` in `server/`, then checks `out/index.html` exists and
carries the API URL). Try it = `scripts/autopilot-serve.ps1` (serves `out/` on a port derived from
the task id). **Never run `next dev`** on this machine (it exhausts RAM). Never deploy from a task
(the owner deploys with the deploy skill after merging). Never commit secrets (`.env*`, `server/.env`).

## P.3 Conventions every task keeps

1. **Copy**: every public string in `src/lib/constants.ts`; only shipped app features in
   `FEATURES`; planned work in `ROADMAP`; no competitor or engine names; numbers with units.
2. **Pages**: the per-page SEO checklist (metadata, one h1, canonical with trailing slash,
   server-rendered text, sitemap entry, JSON-LD kept in step); dashboard and account pages
   `noindex`.
3. **API**: a router per area under `server/app/routers/`, a service module under
   `server/app/<area>/`, Pydantic models, additive SQLAlchemy migrations only, every endpoint
   with a pytest (happy path + auth failure + validation failure), webhooks verified server-side,
   a plan or entitlement changed only from an event the server verified itself.
4. **Contracts**: the endpoints a feature implements are the ones its contract document names;
   the task updates the document's *implemented by* table on its branch (in the Unreal repo's
   folder: that write is outside the worktree, so record the change in the As-built and the
   owner applies it at merge).
5. **Data that grows** (projects, logs, tiles, bundles, catalogues) goes to object storage and
   Postgres from PF14 on; until PF14 lands a task keeps SQLite + the local filesystem behind
   one storage interface so the swap is one adapter.
6. **Tests before features**: write the pytest names from the doc's Tests table first.
7. **Done**: scope whole, lint + build + pytest green, the doc's As-built and Status filled, ONLY
   the feature's own tracker row ticked in `docs/roadmap/40/README.md`, a human test the owner
   can click through on the served `out/` and the local API.

## P.4 The feature doc (template)

```
# PF<n> — <Title> (launch priority <1|2|3>)
**Needs merged:** … **Unblocks:** … **Contract:** contracts/<name>.md (or none)
## Status            where any existing code is (path:line, verified) / nothing yet; 00-understanding.md §n
## Goal              one paragraph in the owner's terms
## Read first        contract docs, code paths, skills
## Scope             In: numbered, the whole deliverable. Out (and where it goes): with owners
## Design            API (endpoints, auth, request/response JSON) · Data (tables, migrations, storage) ·
                     UI (pages, components, copy keys) · Jobs / workers · Security and privacy
## Deliverables      checklist of files, endpoints, pages, scripts, docs
## Tests             | Name | Kind (pytest / build check / manual) | Asserts |
## Human test        numbered steps on the served site + local API, each with what the tester sees
## Risks / traps     known gotchas (static export, no-cors form, SQLite, tunnel, RAM)
## As-built          date, branch, commits, counts, deviations, carry-over
```

## P.5 Entitlements and plans

The plan catalogue (`server/app/plans.py`) and the entitlement matrix are copied from
`T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\guides\GD7-*.md` once it exists; until
then PF1 ships the tiers named in the licence contract with a placeholder matrix and a TODO row
in its As-built.
