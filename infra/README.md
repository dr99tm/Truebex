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
docker compose --env-file infra/host/local/local.env -f infra/host/compose.yaml -f infra/host/compose.local.yaml up --build
curl http://127.0.0.1/health/deep        # {"db":"ok","storage":"ok","worker_heartbeat_s":…}
docker compose --env-file infra/host/local/local.env -f infra/host/compose.yaml -f infra/host/compose.local.yaml down -v
```

## Postgres tests

The verify gate runs the server tests on SQLite. Before a deploy, run them against Postgres too:

```powershell
# any disposable Postgres, e.g. the local trial's (add a "5432:5432" port to its postgres service)
$env:TEST_DATABASE_URL = 'postgresql+psycopg://truebex:local-trial-only@127.0.0.1:5432/truebex_test'
cd server; .venv\Scripts\python.exe -m pytest -q -m postgres
```

The `postgres`-marked tests drop and recreate the `public` schema of that database.

## Shared plumbing (server/app)

Every feature codes against these; the production adapters are PF14's.

| Module | Settings |
|---|---|
| `storage/` (`local`, `s3`) | `STORAGE_BACKEND`, `STORAGE_DIR`, `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `CDN_BASE_URL` |
| `mail/` (`console`, `smtp`) | `MAIL_BACKEND`, `MAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` |
| `tasks.py` + `worker.py` | `BACKGROUND_TASKS=inline\|worker\|off` |
| `ratelimit.py` (`memory`, `db`) | `RATELIMIT_BACKEND` |
| `contract_http.py` | — |
| `health.py` (`/health/deep`), `ops.py` (heartbeat, backup check, alerts) | `ALERT_EMAIL`, `ALERT_PUSH_URL`, `BACKUP_EXPECTED` |
