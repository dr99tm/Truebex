---
name: truebex-deploy
description: Ship truebex.com and keep the Truebex API online. Use when asked to deploy, publish, sync, "put it online", publish an app release, change a secret, price or billing switch, restart or check the API, run the restore test, or verify the live site — covers the dev repo (master) → deploy repo (main) → GitHub Pages flow and its release steps (sync:releases, sync:roadmap, sync_prices.py, indexnow), the site config in constants.ts, and the api.truebex.com VM (infra/deploy.ps1, secrets, health checks, backups).
---

# Deploying Truebex

Two clones of `github.com/dr99tm/Truebex`:

| Repo | Path | Branch | Holds |
|---|---|---|---|
| Dev | `X:\Truebex` | `master` | source |
| Deploy | `X:\Truebex_site_files\Truebex` | `main` | built `out/` + `.github/` (README, Pages workflow) |

Pushing `main` runs `.github/workflows/static.yml` → GitHub Pages → truebex.com.
`gh-pages` is a stale leftover; ignore it.

Only the owner deploys, after merging. Never from a task.

## Order of a release

1. Merge to `master`, run the tests (*API*, before a deploy).
2. API first: `infra\deploy.ps1` (*API*). The site's sync steps read the live API, and `/billing/plans` and
   `/config` serve the switches at runtime.
3. Prices, if `catalogue.json` `prices` or `founding` changed: `sync_prices.py` against that API (*Billing*).
4. A new app version: `publish_release.py ... --symbols` (*App releases*).
5. The website (*Website*), which ends with the live checks and IndexNow.

## Website

1. Commit and push `master` (`git push`; upstream is set).
2. `.env.local` must hold production URLs (`NEXT_PUBLIC_AUTH_URL=https://api.truebex.com`). A build made for local testing (`NEXT_PUBLIC_AUTH_URL=http://127.0.0.1:8000`) must never be deployed — rebuild first.
3. `npm run sync:releases` (PF1): writes `src/content/releases.json` (stable) and `releases-beta.json` from `https://api.truebex.com/releases/feed`; commit them if they changed.
4. `npm run sync:roadmap -- T:/unreal5_7_4_projects/truebex_compact/Docs/roadmap/40/README.md docs/roadmap/40/README.md` (PF13; the app tracker first, then the platform tracker). It sets each item's `status` in `src/content/roadmap.json` from the trackers' ticked rows (ticked → shipped, a branch in "Code today" → in progress); commit it if it changed. A plan id missing from both trackers stops it: fix the tracker or the item's `plan_ids`. The public words and `FEATURES` never change by themselves.
5. Prices (PF2): `server/app/catalogue.json` `prices_final` must be what the owner intends. `false` keeps every paid tier at "Price at launch" on `/pricing/`, the home page, `/ar/` and the JSON-LD offers, with no founding block; `true` publishes the catalogue's prices and founding offer. Before a price goes public, the target environment's provider must hold it: `sync_prices.py` was run against that environment, dry run first (*Billing*). A price the provider does not have cannot be bought.
6. `rm -rf out && npm run build`. Verify: `grep -rl api.truebex.com out/_next` finds a file, `/download/` shows the feed's latest version (a fixture or local-test feed must never be deployed), and `out/pricing/index.html` shows prices only when `prices_final` is true.
7. In the deploy repo: delete everything except `.git` and `.github`, `cp -a /x/Truebex/out/. .`, `diff -rq . /x/Truebex/out -x .git -x .github` must be empty.
8. `git add -A && git commit -m "Deploy: build master <sha> (<summary>)" && git push origin main`.
9. Wait for the Pages run: `curl -s "https://api.github.com/repos/dr99tm/Truebex/actions/runs?branch=main&per_page=1"` → `head_sha` = the deploy commit, `conclusion: success`.
10. Verify live (cache-bust with `?nc=$RANDOM`): every route returns 200 (`/`, `/login/`, `/signup/`, `/dashboard/`, `/pricing/`, `/roadmap/`, `/ar/`, `/download/`, `/changelog/`, `/developers/`, `/sitemap.xml`, `/robots.txt`), and the homepage's chunk names match `out/`. Then:
    - `/pricing/`: the prices step 5 intended, or "Price at launch" on every paid tier.
    - `/changelog/`: the latest version from step 3, with its `#<version>` anchor; `/changelog/feed.xml` loads.
    - `/download/`: the same latest version, and its button downloads (`/releases/<version>/download` → 302 → 200).
    - `/checkout/`: 200 with `noindex` in its HTML (`curl -s https://truebex.com/checkout/ | grep -c noindex` ≥ 1), and not in `/sitemap.xml`.
    - `curl -s https://api.truebex.com/billing/plans`: `provider` is `paddle` (whatever `BILLING_PROVIDER` names), the catalogue's tiers and prices, `founding` as intended, and no `wayl` in `providers`.
    - `/viewer/viewer.js` (PF5): share pages on the API's origin load the viewer from the site, so `curl -sI https://truebex.com/viewer/viewer.js` must answer 200 with `access-control-allow-origin: *`.
11. `npm run indexnow -- --sitemap` (PF13): tells Bing and the other IndexNow engines about every URL in `out/sitemap.xml` → `indexnow: 200` or `202`. `--dry-run` prints the request first. The key file `public/9453d000061b1c7726749ca61a17a0db.txt` must be live at `https://truebex.com/9453d000061b1c7726749ca61a17a0db.txt`.

`deploy-to-server.bat` automates 6–8 (plus a backup folder per run). It runs none of 3–5 or 9–11; do those by hand around it.

## Site config (`src/lib/constants.ts`)

Public by design (served in every page; none is a secret). An empty value hides the feature: no beacon, no tag, no link. Edit, commit, then the *Website* steps.

| Key | Turns on | Owner step (once, after the first deploy) |
|---|---|---|
| `ANALYTICS.cloudflareToken` | Cloudflare Web Analytics beacon on public pages only (cookieless) | Cloudflare dashboard → Web Analytics → add truebex.com → copy the site's beacon token |
| `VERIFICATION.google` | `google-site-verification` meta tag | Search Console: domain property by DNS TXT at Cloudflare (the tag is only needed for a URL-prefix property); submit `https://truebex.com/sitemap.xml` |
| `VERIFICATION.bing` | `msvalidate.01` meta tag | Bing Webmaster Tools: import from Search Console (no tag needed), or verify with the tag; submit the sitemap |
| `SOCIAL` (each `url`) | the footer's Follow column and the Organization `sameAs` | the handles from the launch plan (GD6) |

A local build can try the beacon and tags without editing the file (`TRUEBEX_ANALYTICS_TOKEN`, `TRUEBEX_GOOGLE_SITE_VERIFICATION`, `TRUEBEX_BING_SITE_VERIFICATION`); a release never needs them. Search Console, Bing and IndexNow in more depth: `truebex-seo`.

## App releases (PF1, PF14)

Per app version, before *Website* step 3. The `rel-*` seed signs the manifest and never goes in the repo, an env file or the VM.

- **Keys, once:** `server\scripts\make_signing_key.py --kind rel --out <file kept off the VM>`; its public half goes into `RELEASE_PUBLIC_KEYS` (*Secrets*) and the app's `Config/LicenceKeys.json` before the first release (licence contract §3). `--kind lic` makes `LICENCE_SIGNING_KEY`.
- **Publish**, from `X:\Truebex\server` with the production settings in the shell (below):

  ```powershell
  .venv\Scripts\python.exe scripts\publish_release.py --version 1.1.0 --channel stable --platform win64 `
      --file D:\builds\Truebex-Setup-1.1.0.exe --notes notes.md --key-file <rel-* key file> `
      --symbols D:\builds\1.1.0\Symbols
  ```

  It hashes and signs the installer, stores it in the data bucket and registers the row, then hands the
  `--symbols` folder (the Shipping `.pdb` / `.sym` files from the package gate) to
  `scripts.upload_symbols.upload()`, so that version's crash reports get function names. `.pdb` files need
  `dump_syms` on PATH or `--dump-syms <exe>`. The folder is checked before anything is published; if the upload
  fails afterwards, the release stays published and the script prints the
  `python -m scripts.upload_symbols --version <v> <folder>` that retries it.
- **Production settings:** environment variables override `server/.env`, so set them in the shell for this
  run only: `DATABASE_URL` through an SSH tunnel to the VM's Postgres (`ssh -L 15432:<postgres container ip>:5432
  truebex@<vm>`, as in `infra/CUTOVER.md`; host `127.0.0.1:15432`), `STORAGE_BACKEND=s3` with the data bucket's
  `S3_*`, and `RELEASE_PUBLIC_KEYS`. Never write them into `server/.env`.
- **Without the tunnel:** sign elsewhere and upload through `POST /admin/releases` (up to 90 MB), and each
  `.sym` through `POST /admin/symbols`.
- Then `npm run sync:releases` and a site deploy (*Website*).

## Billing (PF2)

Paddle is the default provider (`BILLING_PROVIDER=paddle`; reseller and merchant of record). Stripe stays for
business invoices and as the one-setting switch `BILLING_PROVIDER=stripe`. Wayl is dormant (`WAYL_ENABLED=false`)
and never offered on the site. A provider is on only when its API key and its webhook secret are both set
(*Secrets*); with `BILLING_PROVIDER`'s provider off, `/billing/plans` answers `provider: null` and checkout 503.

- **Prices → provider**, whenever `catalogue.json` `prices` or `founding` change and once for each new
  environment, against that API's own database (on the VM, in `/opt/truebex`):
  `docker compose exec api python -m scripts.sync_prices --provider paddle --env production --dry-run` lists every
  price as `exists` or `created` and writes nothing. If the list is right, run it again without `--dry-run`: it
  creates the missing products and prices and fills `provider_prices`. `--env` must match the VM's `PADDLE_ENV`
  (`sandbox` while it holds sandbox keys); the script refuses a mismatch. Stripe: `--provider stripe`, whose key's
  mode must match `--env`. Locally: `.venv\Scripts\python.exe scripts\sync_prices.py --provider paddle --env sandbox --dry-run`
  in `server/`. A changed amount is a new price; the old row stays inactive, so existing subscribers keep their tier.
- **Paddle notification destinations**, one per environment: Paddle → Developer tools → Notifications → New
  destination, URL `https://api.truebex.com/billing/webhooks/paddle` (production account) or
  `https://api-staging.truebex.com/billing/webhooks/paddle` (sandbox account), events `subscription.*` and
  `transaction.*`. Its secret key
  (`pdl_ntfset_…`) is that environment's `PADDLE_WEBHOOK_SECRET`.
- **Stripe webhook:** `https://api.truebex.com/billing/webhooks/stripe` with `checkout.session.completed`,
  `checkout.session.expired` and `customer.subscription.created/updated/deleted/paused/resumed`; its signing secret
  is `STRIPE_WEBHOOK_SECRET`.
- **Marketplace Stripe webhook (PF7):** `https://api.truebex.com/market/webhooks/stripe` with
  `checkout.session.completed`, `checkout.session.async_payment_succeeded` and (Connect) `account.updated`; its
  signing secret(s) are `STRIPE_CONNECT_WEBHOOK_SECRET` (empty = the endpoint answers 404). Orders stay quote-only
  while `MARKET_PAYMENTS_ENABLED=false`, which it stays until the marketplace terms (GD5) are signed off.
- **Paddle approval:** the seller account and the domain truebex.com, before production (the pricing, terms and
  privacy pages must be live first). Paddle.js runs only on approved domains: the overlay is on `/checkout/`.
- When the founding offer closes, archive the founding prices in Paddle and Stripe.

## API (api.truebex.com)

Runs on one Linux VM with Docker Compose (PF14): Caddy :443 with the Cloudflare origin certificate
(only Cloudflare's ranges reach it) → `api` (uvicorn ×2) and `worker` (background jobs) → Postgres 18
with WAL archived by wal-g to a backup bucket at a second provider. Everything is in `infra/`
(`infra/README.md`); `/opt/truebex` on the VM holds the Compose files, scripts and decrypted secrets.

- **Deploy** (owner only, from `X:\Truebex` after merging and running the tests):
  `powershell -NoProfile -ExecutionPolicy Bypass -File infra\deploy.ps1 -VmHost truebex@<vm>`.
  It deploys the committed HEAD of `server/` and `infra/host/`, decrypts `infra/secrets/*.sops.env`
  with sops only for the copy, builds the image on the VM, `docker compose up -d`, and waits until
  `/health/deep` is 200 with a worker heartbeat under 60 s. Staging first:
  `-HealthUrl https://api-staging.truebex.com/health/deep`.
- **Before a deploy:** `server\.venv\Scripts\python.exe -m pytest -q` (SQLite), and the Postgres run
  with `TEST_DATABASE_URL` / `TEST_APP_DATABASE_URL` set (`infra/README.md`, Postgres tests): tables
  added on SQLite can drift on Postgres. Schema changes stay additive (`database._ADDED_COLUMNS`).
- **Health:** `curl https://api.truebex.com/health` → `{"status":"ok"}`;
  `curl https://api.truebex.com/health/deep` → `{"db":"ok","storage":"ok","worker_heartbeat_s":<60}`.
  Cloudflare 521/522 = the VM or Caddy is down; 502 = Caddy is up, the API is not; 503 from
  `/health/deep` names what failed. On the VM: `cd /opt/truebex; docker compose ps;
  docker compose logs --tail 200 api worker`.
- **Backups:** `infra\restore-test.ps1 -VmHost truebex@<vm>` → `restore OK` (also weekly by itself);
  nightly base backups at 02:30 UTC (`journalctl -u truebex-backup`).
- **Alerts:** the hosted monitor (e-mail + phone push), `host-check.sh` every minute, the worker's
  `backup.check`; see `infra/README.md#alerts`.
- **Admins:** `docker compose exec api python -m scripts.make_admin <email>` on the VM.
- **Organisation seats by hand** (Enterprise contracts; PF2's checkout does not sell organisation seats yet):
  `docker compose exec api python -m scripts.grant_org_seats --org <slug> --tier enterprise --seats <n> [--until YYYY-MM-DD]`
  (`--revoke` ends it). The tier and seats reach the members through the organisation, never their personal plan.
- `start-server.bat` / `start-tunnel.bat` are for local use only. Never route `api.truebex.com` to the
  PC again: a second API with its own `auth.db` would take writes nobody sees (`infra/CUTOVER.md`).

## Secrets and switches

Every secret lives only in `infra/secrets/*.sops.env` (encrypted with sops; the age key is on the owner's PC,
with an offline copy) and, decrypted by `infra\deploy.ps1`, in `/opt/truebex/secrets/` on the VM (0600). Never in
the repo unencrypted, a chat or a task; `server/.env` holds local values only. Change one with
`sops infra\secrets\server.sops.env`, save, run `infra\deploy.ps1`: the containers restart with it, and the site
reads the switches at runtime through `/config` and `/billing/plans`, with no site rebuild. Templates:
`infra/secrets/*.env.example` (`infra/secrets/README.md`); `server/.env.example` explains each setting.

`server.sops.env` → `secrets/server.env` (the `api` and `worker` containers):

| Area | Settings | Empty or default means |
|---|---|---|
| Core | `SECRET_KEY` (JWTs; a new one signs everyone out), `DATABASE_URL` (holds the Postgres password), `CORS_ORIGINS`, `SITE_URL`, `API_URL` | — |
| Google sign-in | `GOOGLE_CLIENT_ID` (public) | no Google button |
| Billing | `BILLING_PROVIDER=paddle` (or `stripe`) | — |
| Paddle | `PADDLE_ENV` (`sandbox` / `production`), `PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET` (the notification destination's), `PADDLE_CLIENT_TOKEN` (public: Paddle.js on `/checkout/` through `/config`); `PADDLE_API_BASE` stays empty on the VM (local mock and tests only) | Paddle is on only with both `PADDLE_API_KEY` and `PADDLE_WEBHOOK_SECRET` |
| Stripe | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO` (the original Pro price, kept for its subscribers), `STRIPE_TAX_ENABLED` | Stripe is on only with both `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` |
| Wayl (dormant) | `WAYL_ENABLED=false`, `WAYL_API_KEY`, `WAYL_WEBHOOK_SECRET`, `WAYL_API_BASE`, `WAYL_ENV`, `WAYL_PRICE_PRO_IQD` | off unless `WAYL_ENABLED=true` and both keys are set |
| Licence (PF1) | `LICENCE_SIGNING_KEY` (the `lic-*` seed), `LICENCE_KEY_ID`, `RELEASE_PUBLIC_KEYS` (public `rel-*` halves only), `SIGNING_KEYS_EXTRA` (older `lic-*` public keys during a rotation), `TRIAL_DAYS` | no signing key = activation, entitlements and trials answer 503 |
| Storage (PF14) | `STORAGE_BACKEND=s3`, `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` (the data bucket only), `CDN_BASE_URL`; `STORAGE_URL_SECRET` (local backend only) | no CDN = presigned URLs |
| Mail (PF14) | `MAIL_BACKEND=smtp`, `MAIL_FROM`, `SUPPORT_EMAIL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | — |
| Alerts, telemetry (PF14) | `ALERT_EMAIL`, `ALERT_PUSH_URL`; `TELEMETRY_EVENTS_ENABLED` (the events kill switch), `TELEMETRY_INGESTION_ENABLED` | ingestion off = 503 |
| Organisations, SSO (PF3) | `SSO_SECRET_KEY` (a Fernet key sealing each organisation's SSO client secret: set it once and keep it), `SAML_SP_ENTITY_ID`, `AUDIT_RETENTION_DAYS` (730) | no `SSO_SECRET_KEY` = derived from `SECRET_KEY`, so a new `SECRET_KEY` makes every organisation re-enter its SSO secret; no entity id = each organisation's metadata URL |
| Share pages (PF5) | `SHARE_BASE_URL` (the links' origin), `SHARE_MAX_DAYS` (30), `SHARE_MAX_BYTES` (1 GiB per bundle) | no `SHARE_BASE_URL` = links are `{API_URL}/view/{slug}`; the bundles live in the data bucket with the installers |
| Marketplace (PF7) | `MARKET_PAYMENTS_ENABLED` (`false` until GD5 signs off the marketplace terms), `STRIPE_CONNECT_WEBHOOK_SECRET` (the `/market/webhooks/stripe` endpoint's; uses `STRIPE_SECRET_KEY`), `MARKET_READS_PER_MINUTE` (120), `EMBEDDING_MODEL`, `EMBEDDING_DIR` | payments off = every supplier takes requests for quote only; no webhook secret = 404; no `EMBEDDING_MODEL` = picture search off (the weights from `scripts/fetch_models.py` are not in the image) |
| Supplier portal (PF8) | `FEED_PULL_HOUR_UTC` (2: the daily read of registered feed URLs), `MARKET_MEDIA_FIXTURES` (local trials only) | `MARKET_MEDIA_FIXTURES` stays empty on the VM |

`infra/host/compose.yaml` sets `BACKGROUND_TASKS=worker`, `RATELIMIT_BACKEND=db` and (worker) `BACKUP_EXPECTED=true`;
they are not in the file.

The other files:

| Encrypted | On the VM | Settings |
|---|---|---|
| `postgres.sops.env` | `secrets/postgres.env` (Postgres, wal-g) | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`; the backup bucket's `WALG_S3_PREFIX`, `AWS_ENDPOINT`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (write to that bucket only); `WALG_LIBSODIUM_KEY` (without it no backup can be read: keep a copy with the age key) |
| `host.sops.env` | `secrets/host.env` (`bin/host-check.sh`) | `ALERT_PUSH_URL`, `HEARTBEAT_URL`, `QUEUE_DEPTH_MAX` |
| `origin.pem.sops.env`, `origin.key.sops.env` | `secrets/origin.pem`, `secrets/origin.key` (Caddy) | the Cloudflare origin certificate, from `tofu output` |

Never on the VM: the `rel-*` seed (*App releases*), the age key, the `tofu` state passphrase.

## Gotchas

- `next dev` on this machine can spawn hundreds of PostCSS workers and exhaust RAM. Prefer `npm run build` + `py -3.12 -m http.server 3001` in `out/` for local checks.
- The deploy repo needs `git config --global --add safe.directory X:/Truebex_site_files/Truebex` (foreign file ownership on X:).
- Pages has no `CNAME` file on `main`; the custom domain is set in repo Settings → Pages.
- Git Bash rewrites a leading `/` path argument (`/pricing/` → `C:/Program Files/Git/pricing/`); `indexnow.mjs` undoes it, other scripts do not: pass Windows or relative paths.
- `server/tests/test_deploy_skill.py` reads this file: a feature that adds a release step, a billing or licence setting or a VM secret fails the gate until this skill names it.
