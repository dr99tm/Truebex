# Roadmap 40, platform half (2026-10-09)

The web platform's share of roadmap 40: the licence API, billing through the UK company, organisations,
the project service, share pages, cloud render orchestration, the marketplace backend and the supplier
portal, the mobile web client and the Android app, analysis and AI services, the public API, the website
and operations. The app half, the request and the understanding live in the Unreal project:
`T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\` (its `00-contract.md` C.9 names the contract
documents both halves build against, in `contracts\` there).

| File | What it is |
|---|---|
| `00-contract.md` | the rules for this workspace: stack, gates, conventions, the doc template |
| `PF<n>-*.md` | one doc per feature |
| `README.md` | this tracker |

## How to run a feature

One Claude Autopilot task per row, started from its doc: `Roadmap 40 platform feature PF1: docs/roadmap/40/PF1-licence-api-releases-and-downloads.md`.
A task ticks ONLY its own row, on its own branch.

## Tracker

| Done | Feature | Needs | Prio | Code today | Notes |
|---|---|---|---|---|---|
| [x] | [PF1](PF1-licence-api-releases-and-downloads.md) licence API, releases and downloads | — | 1 | `server/app/licence/`, `server/app/releases/`, `/download/`, `/dashboard/link/` | 2026-10-09, Autopilot T1; PF13 merge notes in its As-built |
| [x] | [PF2](PF2-billing-through-the-uk-company.md) billing through the UK company | PF1 | 1 | `server/app/billing/`, `src/app/checkout/`, `src/app/dashboard/billing/` | built before PF1 merged: one catalogue, one `tasks.py`, one `seats` column at merge (As-built 13) |
| [x] | [PF2a](PF2a-catalogue-prices.md) catalogue prices per the pricing plan | PF2, PF13 | 1 | `server/app/catalogue.json`, `src/components/pricing/` | 2026-10-10, Autopilot T18: owner's prices, `prices_final` true, Team annual only, founding annual only (owner to confirm); pytest 116 + 24 skipped → 157 |
| [x] | [PF2b](PF2b-subscription-consumer-rules.md) subscription consumer rules: DMCC reminders, cooling-off, easy exit, EU withdrawal | PF2, PF14 | 1 | `server/app/billing/consumer.py`, `notices.py`; `BILLING.rules` | 2026-10-10, Autopilot T19: built switched off; the owner flips each switch after QS-17 / QS-18 (switch table in its As-built) |
| [x] | [PF3](PF3-organisations-seats-and-sso.md) organisations, seats and SSO | PF1 | 2 | `server/app/orgs/`, `server/app/sso/`, `/dashboard/organisation/`, `/invite/`, `/login/sso/` | 2026-10-09, Autopilot T9; merged with PF1/PF2/PF13/PF14 2026-10-10 (T22, As-built) |
| [ ] | [PF4](PF4-project-service-log-storage-sync-versions-and-sharing.md) project service: log storage, sync, versions and sharing | PF1 | 2 | — | |
| [x] | [PF5](PF5-share-pages.md) share pages | PF1 | 1 | `server/app/uploads/`, `server/app/shares/`, `/view/{slug}`, `src/viewer/`, `/dashboard/shares/` | 2026-10-09, Autopilot T5; also commits PF1's `server/app/storage/` (see As-built) |
| [ ] | [PF6](PF6-cloud-render-orchestration.md) cloud render orchestration | PF4 | 2 | — | |
| [x] | [PF7](PF7-marketplace-backend.md) marketplace backend | PF1 | 1 | `server/app/market/`, `/market/checkout/`, `/dashboard/orders/`, `/dashboard/admin/market/` | 2026-10-09, Autopilot T6; fixtures, contract §11 rows and MINOR proposals in its As-built |
| [x] | [PF8](PF8-supplier-portal-and-app.md) supplier portal and app | PF7 | 1 | `server/app/supplier/`, `server/app/mail/`, `/supplier/` | 2026-10-10, Autopilot T7; PF2 guard and merge notes, contract §11 rows in its As-built |
| [ ] | [PF9](PF9-mobile-web-client-and-webxr.md) mobile web client and WebXR | PF4, PF6 | 2 | — | |
| [ ] | [PF10](PF10-android-native-app.md) Android native app | PF9 | 3 | — | |
| [ ] | [PF11](PF11-analysis-and-ai-services.md) analysis and AI services | PF6 | 3 | — | |
| [ ] | [PF12](PF12-public-api-sdks-webhooks-and-the-mcp-package.md) public API, SDKs, webhooks and the MCP package | PF4 | 2 | — | |
| [x] | [PF13](PF13-website-pricing-features-roadmap-arabic-changelog-analytics.md) website: pricing, features, roadmap, Arabic, changelog, analytics | — | 1 | `ap/t2-pf13-website-pricing-features-ro` | 2026-10-09, Autopilot T2: pytest 24 → 51; 23 pages, sitemap 14 URLs. Prices, handles and tokens wait for GD7 / GD6 / the owner. Carry-over: PF1 `record_download`, one catalogue / changelog at merge |
| [x] | [PF14](PF14-operations-off-the-home-pc-telemetry-and-crash-ingestion.md) operations: off the home PC, telemetry and crash ingestion | — | 1 | `server/app/telemetry/`, `infra/` | branch `ap/t3-pf14-operations-off-the-home-pc`; cutover is the owner's (`infra/CUTOVER.md`) |
| [x] | [PF14a](PF14a-deploy-skill-release-steps.md) deploy skill: roadmap 40 release steps and secrets | PF1, PF2, PF13, PF14 | 1 | `.claude/skills/truebex-deploy/`, `server/tests/test_deploy_skill.py` | 2026-10-10, Autopilot T20: release steps, secrets by file, site config and live checks in the skill; the gate fails on an unnamed step or setting; `publish_release.py --symbols` |
