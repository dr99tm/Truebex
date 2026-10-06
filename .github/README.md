# Truebex: deployed site (branch `main`)

> ⚠️ **Generated output. Do not edit files on this branch by hand.**
> Every deploy wipes this branch and replaces it with a fresh build.

This branch holds the static build of **https://truebex.com**. Pushing to
`main` runs [`workflows/static.yml`](workflows/static.yml), which publishes
the branch to GitHub Pages.

## Where the source is

The source code is on the **[`master`](https://github.com/dr99tm/Truebex/tree/master)**
branch. Its [README](https://github.com/dr99tm/Truebex/blob/master/README.md)
documents the architecture, environment variables, the auth API, payments,
and known issues.

| Branch | Contents |
|---|---|
| `master` | Source code (Next.js, FastAPI auth server, Apps Script). **Edit here.** |
| `main` (this one) | Built site, deployed to GitHub Pages |
| `gh-pages` | Stale old build, not served |

## How this branch gets updated

From the source checkout (`X:\Truebex`, branch `master`), run
`deploy-to-server.bat`. It will:

1. Build the site (`npm run build` → `out/`).
2. Back up this folder (`X:\Truebex_site_files\Truebex`).
3. Delete everything here except `.git/` and `.github/`.
4. Copy `out/` in, then commit and push `main`, which triggers the Pages deploy.

Files in `.github/` (this README and the workflow) survive deploys and are not
published to the site.
