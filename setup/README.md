# Setting up a machine for the Truebex platform

One command installs what is missing and then checks everything:

```powershell
# Windows (owner's PC, a cloud VM). Add components with -With, check only with -Check.
powershell -ExecutionPolicy Bypass -File setup\setup.ps1 [-With postgres,sdk,mobile,host,infra,deploy | -All] [-Check]
```

```bash
# Linux (Claude cloud sessions, CI, a Linux server): site + server only.
bash setup/setup.sh [--check]
```

`setup\requirements.psd1` is the list the Windows script works from; edit it when a tool or version changes and
`setup.sh` when the Linux side does. Both are safe to re-run.

## What the platform needs

| Component | Tools | Notes |
|---|---|---|
| core | Git, Node 22–25 (24 installed), Python 3.12, Edge (self-tests) | `npm ci`, `server\.venv` with `requirements-dev.txt` |
| postgres | PostgreSQL 16+ binaries | Tests start their own throwaway cluster (`initdb`); see CLAUDE.md |
| sdk | JDK 17 | `scripts\gen-sdks.ps1` installs its own Python/npx tools into `.sdk-tools` |
| mobile | Flutter 3.44.1, JDK 17, Android Studio (SDK 36, NDK 27.0.12077973 + 28.2.13676358) | `kotlin.incremental=false` is already set |
| host | cloudflared | Only the machine that serves api.truebex.com |
| infra | OpenTofu ≥1.8, sops, age | `infra\` was never set up from the PC: no age key or `*.sops.env` yet |
| deploy | the `main` deploy checkout at `X:\Truebex_site_files\Truebex` | Procedure in `.claude\skills\truebex-deploy` |

## What git doesn't carry

| Item | Where it comes from |
|---|---|
| `.env.local` | Copied from `.env.example`. Production builds need the production `NEXT_PUBLIC_*` URLs (not secret) |
| `server\.env` | Copied from `server\.env.example`. Real keys (licence signing, Paddle, mail) come from the owner's password manager |
| `T:\unreal5_7_4_projects\truebex_compact` | Clone of `dr99tm/truebex-compact`. Contract-fixture tests skip without it; `scripts\sync-*.ps1` need it |
| `%USERPROFILE%\.cloudflared\` | Tunnel credentials (secret). Keep a copy outside the PC |
| `server\auth.db` | The local API's SQLite database (personal data). Not needed for tests |

Paths that are still hard-coded to the owner's PC: `scripts\autopilot-setup.ps1` (`X:\Truebex`), the deploy scripts
(`X:\Truebex_site_files\Truebex`), and the `T:\…\truebex_compact` app checkout in the sync scripts and tests.
