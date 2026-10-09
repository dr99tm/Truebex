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
| [ ] | [PF2](PF2-billing-through-the-uk-company.md) billing through the UK company | PF1 | 1 | — | |
| [ ] | [PF3](PF3-organisations-seats-and-sso.md) organisations, seats and SSO | PF1 | 2 | — | |
| [ ] | [PF4](PF4-project-service-log-storage-sync-versions-and-sharing.md) project service: log storage, sync, versions and sharing | PF1 | 2 | — | |
| [x] | [PF5](PF5-share-pages.md) share pages | PF1 | 1 | `server/app/uploads/`, `server/app/shares/`, `/view/{slug}`, `src/viewer/`, `/dashboard/shares/` | 2026-10-09, Autopilot T5; also commits PF1's `server/app/storage/` (see As-built) |
| [ ] | [PF6](PF6-cloud-render-orchestration.md) cloud render orchestration | PF4 | 2 | — | |
| [ ] | [PF7](PF7-marketplace-backend.md) marketplace backend | PF1 | 1 | — | |
| [ ] | [PF8](PF8-supplier-portal-and-app.md) supplier portal and app | PF7 | 1 | — | |
| [ ] | [PF9](PF9-mobile-web-client-and-webxr.md) mobile web client and WebXR | PF4, PF6 | 2 | — | |
| [ ] | [PF10](PF10-android-native-app.md) Android native app | PF9 | 3 | — | |
| [ ] | [PF11](PF11-analysis-and-ai-services.md) analysis and AI services | PF6 | 3 | — | |
| [ ] | [PF12](PF12-public-api-sdks-webhooks-and-the-mcp-package.md) public API, SDKs, webhooks and the MCP package | PF4 | 2 | — | |
| [ ] | [PF13](PF13-website-pricing-features-roadmap-arabic-changelog-analytics.md) website: pricing, features, roadmap, Arabic, changelog, analytics | — | 1 | — | |
| [ ] | [PF14](PF14-operations-off-the-home-pc-telemetry-and-crash-ingestion.md) operations: off the home PC, telemetry and crash ingestion | — | 1 | — | |
