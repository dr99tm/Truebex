# Cutover: the API moves off the home PC (PF14)

The owner runs this once. Until step 4 the home PC keeps serving `api.truebex.com` through the tunnel;
nothing here changes the website (GitHub Pages behind Cloudflare stays).

**Promises, written down so nobody assumes more** (placeholders until GD3 confirms them):

| | Target | How |
|---|---|---|
| RPO (data that can be lost) | 5 minutes | WAL archived continuously, `archive_timeout = 60 s` |
| RTO (time to come back after losing the VM) | 2 hours | a fresh VM from `infra/tofu` + `deploy.ps1` + a restore from the backup bucket |
| Single point of failure | one VM | Cloudflare, the database backups and the object storage live elsewhere; the VM does not |

## 0. Before the window (days ahead)

1. Prerequisites on the owner's PC (`infra/README.md`): OpenTofu, sops, age, an SSH key, the accounts of
   the providers GD3 chose.
2. `cd infra/tofu`, copy `terraform.tfvars.example` to `terraform.tfvars`, fill it in, keep
   `api_target = "tunnel"`, import the existing `api` record:
   `tofu import 'module.dns.cloudflare_record.api_tunnel[0]' <zone id>/<record id>`.
3. `tofu init`, `tofu apply`. Note the `vm_ipv4` output.
4. Fill and encrypt the secrets (`infra/secrets/README.md`), with `DATABASE_URL` pointing at the
   Compose Postgres and `STORAGE_BACKEND=s3`.
5. `infra\deploy.ps1 -VmHost truebex@<vm_ipv4> -HealthUrl https://api-staging.truebex.com/health/deep`
   → "healthy … worker heartbeat …".
6. Rehearse the copy against staging with a copy of `auth.db` (step 3 below, against the staging
   database), then reset the staging database: `docker compose down -v` is NOT the way (it deletes
   the volume and the backups' timeline); instead drop and recreate the schema:
   `docker compose exec postgres psql -U truebex -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"`
   and restart `api` and `worker` (they recreate the tables).
7. Wait for the first nightly base backup (or run `/opt/truebex/bin/backup-base.sh` by hand), then
   `infra\restore-test.ps1 -VmHost truebex@<vm_ipv4>` → `restore OK`.
8. In the uptime monitor's app on the phone, confirm a test alert arrives.

## 1. Provision (done in step 0)

`tofu apply`; deploy; restore test green; `api-staging.truebex.com` serves the new stack.

## 2. Open the window (15 minutes, announced)

1. On the PC: close the window running `start-server.bat` (the API stops; the tunnel shows 530).
2. Copy `server\auth.db` aside: `copy server\auth.db server\auth.db.bak-cutover`.
3. Precheck: `cd server` and `.venv\Scripts\python.exe -m scripts.sqlite_to_postgres --check-only`
   → `precheck: no problems`. Rows listed here must be fixed in SQLite first; the script never
   truncates anything.

## 3. Copy the data

1. Open an SSH tunnel to the VM's Postgres (it publishes no port):
   `ssh -L 15432:<postgres container ip>:5432 truebex@<vm_ipv4>`
   (`docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' truebex-postgres-1`).
2. Stop the API on the VM so nothing writes while copying: `docker compose stop api worker`.
3. Empty the target (the API created the tables on its first start, that is fine; rows from the
   staging rehearsal are not): drop and recreate the schema as in step 0.6, then
   `.venv\Scripts\python.exe -m scripts.sqlite_to_postgres --sqlite sqlite:///./auth.db --postgres postgresql+psycopg://truebex:<password>@127.0.0.1:15432/truebex`
4. The output ends `ALL TABLES MATCH` (row counts and checksums per table). Anything else: stop,
   start `start-server.bat` again (the PC still serves through the tunnel), investigate.
5. `docker compose start api worker`; `https://api-staging.truebex.com/health/deep` → 200.

## 4. Switch the DNS

1. In `terraform.tfvars`: `api_target = "vm"`. `tofu apply` replaces the tunnel's CNAME with the VM's
   A / AAAA records (proxied, so the change is immediate).
2. In the Cloudflare dashboard, Zero Trust → Tunnels → `win-tunnel`: delete the `api.truebex.com`
   public hostname. This is what prevents a split brain: an API left running on the PC with its own
   `auth.db` would accept writes nobody sees.
3. Keep `start-server.bat` and `start-tunnel.bat` for local work only (README, "Running locally").

## 5. Smoke test (the PC API stays off)

1. `curl https://api.truebex.com/health/deep` → `{"db":"ok","storage":"ok","worker_heartbeat_s":<60}`.
2. Sign in on `https://truebex.com/login/` with a password account and with Google → the dashboard
   shows the same plan and keys as before.
3. Stripe: Dashboard → Developers → Webhooks → the endpoint → "Send test webhook" → 200 in the
   endpoint's log. Wayl: open `/dashboard/billing/` with a paid account (the page re-checks payments).
4. Close the window. Turn the home PC off and repeat 1 and 2 from a phone.

## Rollback (inside the window)

Point `api_target` back to `"tunnel"`, `tofu apply`, re-add the tunnel's public hostname, start
`start-server.bat` with the untouched `auth.db`. After the window, rolling back loses the writes made
on the VM: copy them back by hand or not at all.
