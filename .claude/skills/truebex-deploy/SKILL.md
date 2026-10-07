---
name: truebex-deploy
description: Ship truebex.com and keep the Truebex API online. Use when asked to deploy, publish, sync, "put it online", restart the API/tunnel, or verify the live site — covers the dev repo (master) → deploy repo (main) → GitHub Pages flow and the api.truebex.com server + cloudflared tunnel.
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

Runs on this PC: `start-server.bat` (uvicorn on 127.0.0.1:8001, Python 3.12 venv in `server/.venv`) + `start-tunnel.bat` (cloudflared, `%USERPROFILE%\.cloudflared\config.yml`, routes `api.truebex.com → localhost:8001`).

- Health: `curl https://api.truebex.com/health` → `{"status":"ok"}`. HTTP 530 / Cloudflare error 1033 = tunnel down; connection refused locally = server down.
- Start both detached so they outlive the session: `Start-Process X:\Truebex\start-server.bat -WindowStyle Minimized` and the same for `start-tunnel.bat`.
- After changing `server/`: run `server\.venv\Scripts\python.exe -m pytest -q` (all green), then restart the server window. Schema changes must be additive (`database._ADDED_COLUMNS`); back up `server/auth.db` first.
- Secrets live only in `server/.env` (never commit). Feature switches there: `GOOGLE_CLIENT_ID`, `STRIPE_*`, `WAYL_*` — the site picks them up at runtime via `/config` and `/billing/plans`, no rebuild needed.

## Gotchas

- `next dev` on this machine can spawn hundreds of PostCSS workers and exhaust RAM. Prefer `npm run build` + `py -3.12 -m http.server 3001` in `out/` for local checks.
- The deploy repo needs `git config --global --add safe.directory X:/Truebex_site_files/Truebex` (foreign file ownership on X:).
- Pages has no `CNAME` file on `main`; the custom domain is set in repo Settings → Pages.
