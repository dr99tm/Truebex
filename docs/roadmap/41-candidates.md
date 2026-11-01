# Roadmap 41: platform candidates (2026-11-01)

Every row in `docs/roadmap/40/README.md` is ticked. This list gathers what roadmap 40 left open on the
platform side: the carry-overs and "Still open" lines in the PF docs' As-built sections that no later doc
closed, the gaps found while setting up CI on Linux, and missing tests. It is ranked by value to launch
against effort. The top part is work a platform task can do alone. The items further down wait on the app
half, a GD guide, or the owner.

Each item gives one line of reasoning, then the files involved. Contract rules (00-contract.md P.3) still
apply: tests come before features, migrations are additive only, and a contract change goes into the app
repo's `contracts/` first.

## Ready now (platform alone)

1. **Comments and presence in the web and Android clients.** The server has served project-log 1.2
   (5.19–5.22, `comments_rev` on presence) since PF4b, but both clients still send 1.1 and have no comment
   routes, so a shipped server feature is invisible to users (PF4b carry-over → PF9 / PF10).
   Files: `openapi/clients.json`, `scripts/gen-clients.ps1`, `src/lib/projects.ts`, `src/lib/app.ts`,
   `src/viewer/`, `mobile/android/lib/api/api.dart`, `server/app/projects/comments.py`.
2. **A floating seat without a lease must not open `cloud.sync`.** `seat_source` counts a floating seat that
   has no lease, so a device that was refused one (pool full) can still push. That is an entitlement leak
   to close before paid organisation seats go live (PF4 As-built "Still open").
   Files: `server/app/licence/seats.py` (`seat_source`), `server/app/orgs/seats.py` (`best_seat`),
   `server/app/projects/quotas.py` (`plan_of`), `server/tests/test_projects_orgs.py`.
3. **An organisation billing e-mail.** Stripe receipts and invoices for an organisation go to whoever
   bought the seats. Businesses expect a finance address (PF3e / PF2e carry-over). The owner decides the
   field and the wording.
   Files: `server/app/orgs/models.py`, `server/app/billing/org_billing.py` (`org_customer`),
   `server/app/billing/stripe_provider.py`, `src/app/dashboard/organisation/`, `src/lib/constants.ts`.
4. **AI credits: charge per attempt on a mid-stream fallback, and write the `refund` ledger rows.** Credits
   are money. PF3b's usage tab already subtracts refunds, but nothing writes them yet (PF11 "Later",
   PF3b).
   Files: `server/app/ai/proxy.py`, `server/app/ai/credits.py`, `server/app/ai/models.py`,
   `server/app/orgs/usage.py`, `server/tests/test_ai_credits.py`.
5. **Remove the pre-merge `try/except ImportError` guards.** All three modules have been merged since 2026-10-10,
   so the guards are dead code. If one of those imports breaks, though, the guard would silently leave a
   supplier statement `pending`, send no billing mail, or answer 404 for a share, with no test failing.
   Files: `server/app/market/commissions.py` (`_pf2_invoice`), `server/app/billing/notices.py` (`send_mail`),
   `server/app/render/live.py` (`_pf5_resolver`).
6. **Flutter tests in CI.** `.github/workflows/ci.yml` runs eslint, the build and pytest, but not
   Android's 44 Flutter tests or `flutter analyze`. Today only the owner's PC runs those
   (`scripts/verify-mobile.ps1`). A second CI job would protect item 1's Android work.
   Files: `.github/workflows/ci.yml`, `mobile/android/pubspec.yaml`, `mobile/android/test/`.
7. **`listing_<plan>` targets in `sync_prices.py`.** Supplier listing fees stay `pending` until the script
   can create their prices. The code can land now and the numbers when GD7 does (PF2d / PF8a / PF3e
   carry-over).
   Files: `server/scripts/sync_prices.py`, `server/app/market/listing_plans.json`,
   `server/app/supplier/listing.py`.
8. **Redraw the share card when a share is renamed.** The link-preview card keeps the old title on a public,
   shareable surface (PF5a Out, PF5b carry-over). The owner should confirm this is wanted.
   Files: `server/app/shares/card.py`, `server/app/shares/service.py`, `server/tests/test_shares_pf5a.py`.
9. **Partition `telemetry_events` by month on Postgres.** This matters only once volume calls for it. Do it
   after the VM cutover, when real numbers exist (PF14 "Later").
   Files: `server/app/telemetry/service.py`, `server/app/telemetry/jobs.py`, `infra/host/`.

## Needs a contract change or the app half first

10. **Send the MCP socket-path fix upstream, then bump `SERVER_VERSION`.** CI found that `pipePath()`
    re-prefixed absolute Unix socket paths. The bug is fixed in `packages/mcp/lib/wire.mjs` on this branch,
    but `scripts/sync-mcp.ps1` would overwrite the fix unless the app's `Tools/mcp/lib/wire.mjs` gets it too.
    The same sync should take `SERVER_VERSION` 1.0.0 → 1.3.0 to match `tools.json`, `get_tunables` not
    log-safe, and hex entity ids (PF12b / PF12c / PF12d carry-overs).
    Files: `packages/mcp/lib/{wire,server}.mjs`, `packages/mcp/package.json`, `scripts/sync-mcp.ps1`.
11. **A longer-lived credential for the web and Android clients.** Today the 24 h session signs phone users
    out every day. This first needs a licence-api §6.2 rule for Android fingerprints (PF9 / PF10 carry-over).
    Files: `server/app/config.py`, `server/app/licence/links.py`, `server/app/mobile/`,
    `mobile/android/lib/auth/`.
12. **Name who is behind an agent edit ("Sam's API key").** Needs a project-log §5.13 / §6.2 MINOR (PF9a
    carry-over).
    Files: `server/app/projects/ops.py`, `src/viewer/outbox.ts`, `mobile/android/lib/sync/`.
13. **Comment webhooks, an MCP tool and notifications.** Needs a contract MINOR and an owner call (PF4b Out).
    Files: `server/app/webhooks/events.py`, `server/app/projects/comments.py`, `packages/mcp/tools.json`.
14. **Organisation-owned projects (`account_kind` "org", `projects.org_id`) and pooled organisation
    usage.** Waits for project-log (PF4, PF3b carry-over).
    Files: `server/app/projects/models.py`, `server/app/projects/quotas.py`, `server/app/orgs/usage.py`.

## Waits on a GD guide or the owner (listed so nobody starts them blind)

* Real prices, quotas and estimates replace the GD7 / GD3 placeholders in `server/app/plans.py`,
  `catalogue.json`, `projects/quotas.py`, `render/quotas.py`, `render/estimates.json` and `ai/credits.json`.
* A EULA page (`EULA_URL` empty, `server/app/config.py`): needs GD5 wording.
* Arabic marketplace and supplier pages (`src/app/market/`, `src/app/suppliers/`): needs GD6 review.
* PR5 id and depth tiles: waits for the app's T134. The `texture` job kind needs a render-jobs MINOR
  and a model whose licence allows commercial hosting.
* Owner actions, not tasks: the VM cutover (`infra/CUTOVER.md`), production signing keys,
  `ANTHROPIC_API_KEY`, `WEBHOOK_SECRET_KEY`, Paddle approval and `sync_prices` per environment, the
  QS-17 / QS-18 switches, npm / PyPI publishing (`mcpPublished`, `sdksPublished` in
  `src/lib/constants.ts`), and the contract §11 cells.

## Tests that do not run in CI (and why)

CI on ubuntu-latest runs the whole suite with a Postgres 16 service. Six tests skip there by design:

| Test | Why it skips |
|---|---|
| `test_ops.py` (WMI disk check) | Windows only |
| `test_render_worker.py` (Ctrl+C worker) | needs Windows PowerShell |
| `test_pf12_mcp_package.py` (`mcp-bundle-manifest`) | needs PowerShell (`pwsh`) |
| `test_pf6a_render_jobs_1_1.py`, `test_pf7e_marketplace_1_2.py`, `test_pf11c_render_jobs_1_2.py` (app blob checks) | need the Unreal app repository beside this one |

The share-fixture check (`test_pf5b_share_fixtures_up_to_date`) compares the fixture JPEGs by their pixels off Windows
(`make_share_fixtures.py --check --portable`). The byte-exact check still runs on the owner's PC.
