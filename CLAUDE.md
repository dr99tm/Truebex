# Truebex platform

The website (Next.js, static export to `out/`) and the platform API (FastAPI, `server/`) behind truebex.com, plus
the SDKs (`sdks/`), the MCP package (`packages/mcp/`), the render worker (`worker/`) and the Android client (`mobile/`).
The desktop app it serves is a separate Unreal Engine project (`truebex-compact`), the source of truth for brand and
for every cross-workspace contract.

## Branches

- `master` is development. Work goes here (normally through Autopilot task branches `ap/t<N>-…`).
- `main` is the deployed site only: built `out/` plus `.github/workflows/static.yml`, which publishes GitHub Pages on
  every push. Never push to `main` unless you are deploying; the repo skill `.claude/skills/truebex-deploy` has the
  procedure. Also read `.claude/skills/truebex-brand-voice` before writing site copy and `truebex-seo` for pages.

## Plans and tracker

- Roadmap 40: `docs/roadmap/40/` (`00-contract`, `README.md` tracker, one doc per feature PF1–PF14…). A feature's
  doc is its contract; update its tracker row and As-built section when it lands.
- README.md and the tracker gain one section/row per task at the end, so parallel branches conflict only there:
  keep both sides, in landing order (they are CRLF on Windows checkouts).

## Verify

The acceptance gate is `scripts/autopilot-verify.ps1` (lint + build + pytest, 40-minute limit on the owner's PC).
Off Windows, run the same pieces:

```bash
npm ci && npm run lint && npm run build
cd server && python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

- Python 3.12. About 980 tests; `server/tests/conftest.py` restores a template SQLite database per test and sets
  bcrypt rounds to 4, so the default run needs no services.
- `postgres`-marked tests (and the whole suite on Postgres) need a throwaway cluster and two databases:
  `TEST_APP_DATABASE_URL` (whole app) and `TEST_DATABASE_URL` (marked tests), both `postgresql+psycopg://…`.
  The full suite on Postgres takes 30+ minutes: split it into 6–8 groups, one database pair each, with `-rfE`.
- `test_market.py::test_categories_root_on_app_taxonomy` compares with the Unreal app's live checkout on the owner's
  PC; it skips or fails where that checkout is absent. That is expected, not a regression.
- Site checks (`server/tests/test_site_*.py`) read `out/`: build first, or they skip.
- Timing tests are guarded on purpose (`test_pf14g_timing_bounds.py`, the `wakeups` fixture). If one fails under
  load, report the load; never loosen a bound. Known load-only flakes: the Paddle webhook signature second boundary
  and the long-poll meet test (both pass alone).
- Order trap: running `test_uploads.py` before `test_render_shares.py` by hand gives 3 setup errors (worker resolver
  left installed). Alphabetical order never hits it.
- A webhook delivery test must not assume order: `delivery.deliver_due` sends up to 8 at once.

## Rules

- Bumping `server/scripts/export_openapi.py` `API_VERSION` also bumps `sdks/js/package.json`,
  `sdks/python/pyproject.toml` and `sdks/python/truebex/_version.py`. Never hand-merge or hand-write generated files
  (`openapi/v1.json`, `sdks/**/_operations.*`, `models.py`, `schema.d.ts`): regenerate with `export_openapi.py --v1`,
  `sdks/generate.py` and `scripts/gen-sdks.ps1`, then run their `--check` modes.
- Contract fixtures under `server/tests/contracts/` are byte copies of the app's committed blobs (pinned by blob or
  tree id in the tests). Re-copy them with `scripts/sync-contract-fixtures.ps1 -Contract <name>`; never edit them,
  including the app's own README in a fixture folder.
- The app sends some enum values through UE `FName`, whose case changes in Shipping builds (`Warning`, `Team`,
  `Editor`…). Compare those without case (`server/app/enums.py canonical()`).
- Never put a built `out/` copy inside the repo tree: ESLint lints it. Don't run `npm run dev` on the owner's PC
  (it used ~30 GB of RAM); use `npm run build` and `scripts/serve-out.py`.
- `/auth/register` refuses `@….test` addresses (EmailStr): use `example.com` in tests.
- Pages: a private page needs `robots` noindex and no canonical; only `out/index.html` may name
  `https://truebex.com/` as canonical (`tests/test_site_pf13b.py`).
- Write non-ASCII or invisible characters in source as `chr(0x…)` / `String.fromCodePoint(…)`, and scan written
  files for stray control bytes: tool escapes have turned `\a` into BEL and `K` into the Kelvin sign before.
- Production deploy and anything touching the live API, billing or DNS needs the owner's OK.
