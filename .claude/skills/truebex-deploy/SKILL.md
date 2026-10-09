---
name: truebex-deploy
description: Ship truebex.com and keep the Truebex API online. Use when asked to deploy, publish, sync, "put it online", restart or check the API, run the restore test, or verify the live site — covers the dev repo (master) → deploy repo (main) → GitHub Pages flow and the api.truebex.com VM (infra/deploy.ps1, health checks, backups).
---

# Deploying Truebex

Two clones of `github.com/dr99tm/Truebex`:

| Repo | Path | Branch | Holds |
|---|---|---|---|
| Dev | `X:\Truebex` | `master` | source |
| Deploy | `X:\Truebex_site_files\Truebex` | `main` | built `out/` + `.github/` (README, Pages workflow) |

Pushing `main` runs `.github/workflows/static.yml` → GitHub Pages → truebex.com.
`gh-pages` is a stale leftover; ignore it.

## Website

1. Commit and push `master` (`git push`; upstream is set).
2. `.env.local` must hold production URLs (`NEXT_PUBLIC_AUTH_URL=https://api.truebex.com`). A build made for local testing (`NEXT_PUBLIC_AUTH_URL=http://127.0.0.1:8000`) must never be deployed — rebuild first.
3. `rm -rf out && npm run build`. Verify: `grep -rl api.truebex.com out/_next` finds a file.
4. In the deploy repo: delete everything except `.git` and `.github`, `cp -a /x/Truebex/out/. .`, `diff -rq . /x/Truebex/out -x .git -x .github` must be empty.
5. `git add -A && git commit -m "Deploy: build master <sha> (<summary>)" && git push origin main`.
6. Wait for the Pages run: `curl -s "https://api.github.com/repos/dr99tm/Truebex/actions/runs?branch=main&per_page=1"` → `head_sha` = the deploy commit, `conclusion: success`.
7. Verify live: every route returns 200 (`/`, `/login/`, `/signup/`, `/dashboard/`, `/developers/`, `/sitemap.xml`, `/robots.txt`), and the homepage's chunk names match `out/` (cache-bust with `?nc=$RANDOM`).

`deploy-to-server.bat` automates 3–5 (plus a backup folder per run).

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
- **Secrets** live only in `infra/secrets/*.sops.env` (encrypted, age key on the owner's PC) and
  `/opt/truebex/secrets/` on the VM (0600). Feature switches (`GOOGLE_CLIENT_ID`, `STRIPE_*`, `WAYL_*`,
  `TELEMETRY_*`): edit with `sops`, redeploy; the site reads them at runtime, no site rebuild.
- **Admins:** `docker compose exec api python -m scripts.make_admin <email>` on the VM.
- `start-server.bat` / `start-tunnel.bat` are for local use only. Never route `api.truebex.com` to the
  PC again: a second API with its own `auth.db` would take writes nobody sees (`infra/CUTOVER.md`).

## Gotchas

- `next dev` on this machine can spawn hundreds of PostCSS workers and exhaust RAM. Prefer `npm run build` + `py -3.12 -m http.server 3001` in `out/` for local checks.
- The deploy repo needs `git config --global --add safe.directory X:/Truebex_site_files/Truebex` (foreign file ownership on X:).
- Pages has no `CNAME` file on `main`; the custom domain is set in repo Settings → Pages.
