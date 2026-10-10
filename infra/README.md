# infra/: the Truebex API host (PF14)

The API, its worker, Postgres and Caddy run with Docker Compose on one Linux VM behind Cloudflare.
Everything needed to rebuild that host from nothing lives here. The website stays on GitHub Pages.

```
Cloudflare (proxied DNS, TLS "Full (strict)")
   │  443, Cloudflare ranges only (provider firewall)
   ▼
Caddy (origin certificate, JSON access log 14 days) ──▶ api (uvicorn ×2) ──┐
                                                       worker (jobs)     ├──▶ Postgres 18 ──wal-g──▶ backup bucket (2nd provider)
                                                                         └──▶ data bucket (versioned; CDN for public prefixes)
Hosted uptime monitor ──▶ /health, /health/deep every 60 s, several regions ──▶ e-mail + phone push
```

| Path | What |
|---|---|
| `tofu/` | OpenTofu: the VM and its firewall (`modules/vm`), buckets (`modules/buckets`), Cloudflare DNS, mail records and the origin certificate (`modules/dns`), uptime checks and the host heartbeat (`modules/monitoring`) |
| `host/cloud-init.yaml` | first boot: the `truebex` user (SSH key only), Docker, unattended upgrades, journald 14 days, ufw |
| `host/compose.yaml`, `host/Caddyfile` | the four services; `host/postgres/` adds wal-g to Postgres |
| `host/bin/` | `backup-base.sh` (nightly), `restore-test.sh` (weekly), `host-check.sh` (every minute) |
| `host/systemd/` | the timers for those, and the monthly reboot window |
| `host/compose.local.yaml`, `host/local/` | the same stack on a laptop, plain HTTP on 127.0.0.1:80 |
| `secrets/` | SOPS + age encrypted env files (templates: `*.env.example`) |
| `deploy.ps1`, `restore-test.ps1` | deploy from the owner's PC; run the restore test now |
| `CUTOVER.md` | the one-time move off the home PC, with RPO and RTO |

## Placeholders from GD3

`guides/GD3-*.md` (cloud cost and infrastructure) is not written yet. Until it is, the code uses:

| Decision | Placeholder | Where |
|---|---|---|
| VM provider, size, region | Hetzner Cloud `cpx31` (4 vCPU / 8 GB / 160 GB SSD), `nbg1` (EU; no UK region) | `tofu/variables.tf` |
| Data bucket | the VM provider's S3-compatible object storage, versioned | `tofu/terraform.tfvars.example` |
| Backup bucket | a second provider's S3-compatible storage (Backblaze B2, EU) | same |
| Backup retention | 30 nightly bases + their WAL, bucket expiry 37 days | `host/bin/backup-base.sh`, `modules/buckets` |
| Uptime monitor | Better Stack (multi-region, 60 s, e-mail + push, heartbeat) | `modules/monitoring` |
| Mail relay | any SMTP relay with DKIM (`MAIL_BACKEND=smtp`) | `secrets/server.env.example` |
| RPO / RTO | 5 min / 2 h | `CUTOVER.md` |

Changing a provider means changing its module; the API only sees S3, SMTP and Postgres URLs.

## Prerequisites (owner's PC)

* [OpenTofu](https://opentofu.org) ≥ 1.8, [sops](https://github.com/getsops/sops), [age](https://github.com/FiloSottile/age),
  OpenSSH (built into Windows), Git.
* Docker Desktop only for `-BuildLocally` and the local trial; by default the image is built on the VM.
* Accounts: Cloudflare (API token: Zone DNS edit, SSL and Certificates edit), the VM provider (API
  token), the two object storage providers (one admin key each for `tofu`, then one key per role), the
  uptime monitor (API token, phone app signed in).

## First time

1. `cd infra/tofu`, `copy terraform.tfvars.example terraform.tfvars`, fill it in.
   `$env:TF_VAR_state_passphrase = '<long passphrase>'` (it encrypts `terraform.tfstate`, which holds
   the origin key; keep the passphrase with the age key).
2. Records that already exist in the zone must be imported before tofu manages them, e.g.
   `tofu import 'module.dns.cloudflare_record.api_tunnel[0]' <zone id>/<record id>`. Mail records stay
   unmanaged (`manage_mail_records = false`) until the existing SPF and DMARC are imported: two SPF
   records break mail.
3. `tofu init`, `tofu apply`.
4. Secrets: `secrets/README.md`. The origin certificate comes from `tofu output`.
5. `..\deploy.ps1 -VmHost truebex@<vm_ipv4> -HealthUrl https://api-staging.truebex.com/health/deep`.
6. Then `CUTOVER.md`.

## Deploying a new version

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File infra\deploy.ps1 -VmHost truebex@<vm_ipv4>
```

It deploys the committed HEAD of `server/` and `infra/host/`, decrypts the secrets only for the copy,
restarts what changed and waits for `/health/deep` (database, storage, worker heartbeat under 60 s).
Run the Postgres tests first (below): parallel features add tables against SQLite, and drift shows only
on Postgres.

## Backups and restore

* **Continuous:** Postgres archives every WAL segment with `wal-g wal-push` (at least every 60 s), encrypted
  with `WALG_LIBSODIUM_KEY`, to the backup bucket at the second provider.
* **Nightly:** `truebex-backup.timer` (02:30 UTC) runs `bin/backup-base.sh`: a base backup, then
  `wal-g delete retain FULL 30`, then the `backup.base` marker.
* **Weekly:** `truebex-restore-test.timer` (Sunday 05:00 UTC) restores the latest base plus WAL into a
  scratch container and compares every table's row count with production. On demand:
  `infra\restore-test.ps1 -VmHost truebex@<vm_ipv4>` → `restore OK`.
* **Data bucket:** versioned; replaced or deleted objects stay 30 days.
* **Point in time:** on a fresh VM, `wal-g backup-fetch $PGDATA LATEST` plus
  `recovery_target_time = '…'` in `postgresql.auto.conf` (the restore test's
  `host/postgres/restore-into.sh` is the template).

A deletion request (telemetry 5.5, an account deleted) reaches the backups when they rotate out
(30 days), as the privacy page says.

## Alerts

| What | Checked by | Within |
|---|---|---|
| API down (`/health`), database / storage / worker down (`/health/deep` 503) | the hosted monitor, 60 s, several regions | 3 minutes |
| The host itself down, or its checks stopped | the monitor's heartbeat (`host-check.sh` pings every minute) | 5 minutes |
| Disk > 85 %, memory < 10 % available, load > 2 × cores, a container restarted or unhealthy, Caddy 5xx > 5 % over 5 minutes, origin certificate < 14 days, PF6 queue depth | `bin/host-check.sh` every minute | 1 minute |
| Last WAL archive > 15 minutes old, last base backup > 26 h old | the worker's `backup.check` job every 15 minutes | 15 minutes |

The monitor alerts by e-mail and by push to its phone app. The host checks and `backup.check` send a
phone push to `ALERT_PUSH_URL` (an ntfy-style topic) and an e-mail to `ALERT_EMAIL` through the API's
mail adapter, once when a problem starts and once when it clears.

First steps when one fires: `ssh truebex@<vm>`, `cd /opt/truebex`, `docker compose ps`,
`docker compose logs --tail 200 api worker`, `journalctl -u truebex-backup -n 50`, `df -h`.

## Logs and retention

* Container logs go to journald, kept 14 days (cloud-init). Caddy's JSON access log rolls at 50 MiB and
  keeps 14 days. The API never logs tokens, request bodies or addresses beyond Caddy's access log.
* Telemetry retention (raw events 13 months, crash files 180 days, feedback 2 years, deletions within
  30 days) is applied by the worker's jobs (`server/app/telemetry/jobs.py`).

## Local trial (no Cloudflare, no backups)

```powershell
docker compose --env-file infra/host/local/compose.trial -f infra/host/compose.yaml -f infra/host/compose.local.yaml up --build
curl http://127.0.0.1/health/deep        # {"db":"ok","storage":"ok","worker_heartbeat_s":…}
docker compose --env-file infra/host/local/compose.trial -f infra/host/compose.yaml -f infra/host/compose.local.yaml down -v
```

## Postgres tests

The verify gate runs the server tests on SQLite. Before a deploy, run them against Postgres too:

```powershell
# any disposable Postgres, e.g. the local trial's (add a "5432:5432" port to its postgres service)
cd server
$env:TEST_DATABASE_URL = 'postgresql+psycopg://truebex:local-trial-only@127.0.0.1:5432/truebex_test'
.venv\Scripts\python.exe -m pytest -q -m postgres            # init/migrate twice, upserts, the copy script
$env:TEST_APP_DATABASE_URL = 'postgresql+psycopg://truebex:local-trial-only@127.0.0.1:5432/truebex_app'
.venv\Scripts\python.exe -m pytest -q                        # the whole suite with the app on Postgres
```

Both databases are disposable: the `postgres`-marked tests drop and recreate the `public` schema of
`TEST_DATABASE_URL`, and every test recreates the tables of `TEST_APP_DATABASE_URL`.

## Shared plumbing (server/app)

Every feature codes against these; the production adapters are PF14's.

| Module | Settings |
|---|---|
| `storage/` (`local`, `s3`) | `STORAGE_BACKEND`, `STORAGE_DIR`, `STORAGE_URL_SECRET` (local signed URLs), `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `CDN_BASE_URL` |
| `mail/` (`console`, `smtp`) | `MAIL_BACKEND`, `MAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` |
| `tasks.py` + `worker.py` | `BACKGROUND_TASKS=inline\|worker\|off` |
| `ratelimit.py` (`memory`, `db`) | `RATELIMIT_BACKEND` |
| `contract_http.py` | — |
| `health.py` (`/health/deep`), `ops.py` (heartbeat, backup check, alerts) | `ALERT_EMAIL`, `ALERT_PUSH_URL`, `BACKUP_EXPECTED` |

## Tiles and the CDN (PF6)

Cloud renders write their tiles content-addressed to the data bucket at `tiles/<sha256>.jpg` (immutable,
`Cache-Control: public, max-age=31536000, immutable`); job manifests and everything else stay private.
Viewers fetch tiles from `TILES_BASE_URL`, which defaults to `CDN_BASE_URL/tiles` on the `s3` backend.

1. `modules/buckets` gives the data bucket a CORS rule (GET and HEAD from any origin: WebGL refuses
   cross-origin textures without it) and a policy that lets anyone read `tiles/*` only
   (`public_prefixes`). A hash is unguessable and appears only in manifests served to the job's account
   or a live share.
2. In `terraform.tfvars` set `cdn_target` to the bucket's virtual-hosted endpoint,
   `<data_bucket>.<host of data_s3_endpoint>` (e.g. `truebex-data.fsn1.your-objectstorage.com`).
   `modules/dns` then adds the proxied CNAME `cdn.<zone>` and an origin rule that sends the bucket's own
   host name, so the bucket answers. `tofu apply`.
3. Check: `curl -I https://cdn.truebex.com/tiles/<a tile's sha256>.jpg` → 200, `image/jpeg`, the
   immutable `Cache-Control`, `cf-cache-status: HIT` on the second request.
4. Set `CDN_BASE_URL=https://cdn.truebex.com` in `secrets/server.env` (leave `TILES_BASE_URL` empty)
   and deploy. Until the CDN exists, tiles are served by the API's own `/tiles/` route.

`releases/` and `shares/` are also served from `CDN_BASE_URL` by the storage adapter; PF1 and PF5 add
their prefixes to `public_prefixes` when they move there.

## Render queue and workers (PF6)

* `bin/queue-depth` (installed by `deploy.ps1` beside the `.sh` scripts) prints the number of queued
  render jobs (`python -m app.render.depth` in the worker container). `host-check.sh` alerts when it
  passes `QUEUE_DEPTH_MAX` (default 50, in `secrets/host.env`).
* The worker process runs the render jobs: `render.leases.reap` (15 s), `render.jobs.expire` (5 min),
  `render.autoscale` (30 s), `render.tiles.gc` (weekly), `render.overage.charge` (6 h).
* GPU workers are separate Windows machines (`../worker/`, `worker/bootstrap.ps1`): until GD3 names a
  cloud provider they form the `static` pool, registered by hand with a token from Admin → Render. They
  need outbound HTTPS to the API, the data bucket and the CDN only.
