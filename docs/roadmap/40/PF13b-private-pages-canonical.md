# PF13b — Only the home page names https://truebex.com/ as its canonical (launch priority 2)

**Needs merged:** PF13 (the root layout, `seo.ts`, the site build checks), PF7b (`/market/basket/` drops the inherited canonical); both on `master` 988334f. **Unblocks:** nothing waits on it; it closes PF7b's As-built carry-over ("an SEO tidy-up for PF13's owner"). **Contract:** none. No endpoint or app code changes; site metadata and one build check.

## Status

**Built (2026-10-14, branch `ap/t77-pf13b-no-page-but-the-home-page`, Autopilot T77); see As-built.** Checked on `master` 988334f, in the source and in its built `out/`, before the work began:

| Area | Where (master 988334f) | Before |
|---|---|---|
| Root canonical | `src/app/layout.tsx:43` `alternates: { canonical: "/" }`; `:66` `robots` index, follow | Every page that names no canonical of its own inherits `<link rel="canonical" href="https://truebex.com/"/>` |
| Home page | `src/app/page.tsx:19` `alternates: { canonical: "/", languages: HOME_LANGUAGES }` | its own canonical and the en / ar / x-default alternates |
| Public pages | `src/lib/seo.ts:43` `pageMetadata` (`/pricing/`, `/features/*`, `/roadmap/`, `/changelog/`, `/ar/`, `/developers/*`, `/suppliers/`); explicitly in `/terms/`, `/privacy/`, `/download/`, `/signup/`, `/login/`, `/app/`, `/app/project/`, `/invite/project/` | their own canonical |
| `/market/basket/` | `src/app/market/basket/page.tsx:13` `alternates: { canonical: null }` (PF7b; `test_pf7b_basket.py:439`, `:455`) | no canonical |
| Inherited | 40 `index.html` files besides the home page, and `404.html` (below) | `https://truebex.com/` |
| `/account/` | `src/app/account/page.tsx`, a client component that `router.replace("/dashboard/")` | no metadata of its own: the layout's `index, follow` and googlebot `index, follow, max-image-preview:large`, and the root canonical |

The 41 files that named `https://truebex.com/` in 988334f's `out/`: 22 `/dashboard/*` pages (the dashboard, billing, keys, usage, cloud, link, orders, projects, projects/view, shares, webhooks, the organisation's overview, audit, invites, members, seats, sso and usage, and admin growth, market, render and telemetry); 11 `/supplier/*` pages (the portal, analytics, billing, catalogue, catalogue/product, imports, inbox, join, prices, signup, team); `/market/checkout/`, `/checkout/`, `/login/sso/`, `/invite/`, `/account/`, `/404/`, `/_not-found/`, and `404.html`. The task text counted 37 `index.html` pages; the build had three more dashboard pages (admin/render, cloud, webhooks). All were noindex except `/account/`.

## Goal

A search engine sees one consistent signal per page. The home page is the only page that names `https://truebex.com/`. A public page names its own URL. A private page (the dashboard, the supplier portal, a checkout, a per-person page, a redirect) is `noindex` and names no canonical. It never points a crawler at the home page, so a private page's `noindex` cannot be carried over to the home page.

## Read first

* `docs/roadmap/40/00-contract.md` P.3 (the per-page SEO checklist), P.4.
* `PF7b-buy-this-look-basket-page.md` (Risks: "Root canonical"; As-built: "Carry-over").
* `.claude/skills/truebex-seo/SKILL.md` (how the site is wired, the per-page checklist).
* `src/app/layout.tsx`, `src/app/page.tsx`, `src/lib/seo.ts`, `src/app/account/page.tsx`, `server/tests/test_site_pf13.py` (`Doc`, `page()`, `html_files()`).

## Scope

**In:**

1. Remove `alternates.canonical` from `src/app/layout.tsx`, so a page has a canonical only when it names its own. The home page's canonical and en / ar / x-default alternates stay byte-identical, and so do `/ar/`'s.
2. `/account/` becomes noindex through `src/app/account/layout.tsx` (`robots: { index: false, follow: true }`), and it keeps redirecting to `/dashboard/`.
3. `/market/basket/` keeps its `canonical: null`.
4. The build gate first, watched failing on 988334f's build: `server/tests/test_site_pf13b.py`, reusing `test_site_pf13.py`'s `Doc`, `page()` and `html_files()`. It checks every `out/**/*.html` outside `_next`: a canonical, when present, is the page's own URL; no noindex page names another URL; every sitemap URL has exactly its own canonical; `/account/` is noindex; only `out/index.html` names `https://truebex.com/`. It skips like the other site tests when `out/` is not built.
5. One line in the `truebex-seo` per-page checklist: a private page is noindex and has no inherited canonical.

**Out (and where it goes):**

* **The 404 page's second robots tag.** Next writes its own `<meta name="robots" content="noindex"/>` into the not-found page (`404.html`, `/404/`, `/_not-found/`), ahead of the layout's `index, follow` and googlebot `index, follow, max-image-preview:large`. That was true before this task too, and it is unchanged. Search engines apply the most restrictive directive, so the page is treated as `noindex`. GitHub Pages also answers the 404 status for `404.html`. Giving the not-found page metadata of its own (a `not-found.tsx` with `robots`) would remove the contradicting tags. It is a separate tidy-up for PF13's owner, not needed for this task's signal.
* **`og:url` on private pages.** They still carry the root layout's `og:url` `https://truebex.com/` (the dashboard, the supplier portal, the checkouts, `/account/`, the 404 page). It is a sharing hint, not a canonical, and the pages are noindex. If the owner wants it gone, the root's `openGraph.url` is the place to change, and every public page sets its own through `pageMetadata` (PF13's owner).
* **IndexNow / Search Console:** the changed pages are private, so there is nothing to ping. The sitemap is unchanged.
* **Arabic versions of these pages:** none exist. The dashboard and the portal are English only (LO1 / GD6).
* **Sitemap:** unchanged (23 URLs, byte-identical apart from the build-time `lastmod`).
* **`/app/`, `/app/project/`, `/invite/project/`, `/login/`:** noindex pages that name their own URL. That is allowed by the rule ("no noindex page names *another* URL") and left as it is.

## Design

**API, data, jobs:** none.

**Metadata.** Next merges `alternates` as a whole from the nearest segment that sets it. With the root's removed, a page without `alternates` renders no `<link rel="canonical">`. A page that sets `alternates` keeps exactly what it sets, so the home page, `/ar/` and every `pageMetadata` page are unchanged. `src/app/account/layout.tsx` is a server layout (the page is a client component and cannot export metadata). Its `robots` replaces the root's whole `robots` object, googlebot included, so `/account/` renders one tag, `<meta name="robots" content="noindex, follow"/>`. `follow` stays, because the page's only content is a link to the dashboard.

**Security and privacy:** none.

## Deliverables

- [x] `src/app/layout.tsx` without `alternates`; `src/app/account/layout.tsx`
- [x] `src/app/market/basket/page.tsx`: comment updated only (`canonical: null` kept)
- [x] `server/tests/test_site_pf13b.py` (9 checks)
- [x] `.claude/skills/truebex-seo/SKILL.md` checklist item 9
- [x] this doc; the tracker row; a README section

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_site_pf13b_root_layout_names_no_canonical` | pytest (source) | `src/app/layout.tsx` sets no `alternates` and no `canonical` |
| `test_site_pf13b_account_layout_noindex_source` | pytest (source) | `src/app/account/layout.tsx` has `robots: { index: false, follow: true }`; the page still calls `router.replace("/dashboard/")` |
| `test_site_pf13b_canonical_is_own_url` | build check | every `out/**/*.html` outside `_next`: no canonical, or exactly one naming its own URL (`index.html` → its folder with the trailing slash; the home page → `https://truebex.com/`; `404.html` → `https://truebex.com/404.html`) |
| `test_site_pf13b_noindex_names_no_other_url` | build check | every page with a `noindex` robots tag (at least 40) names no other URL: no foreign canonical, no hreflang alternate |
| `test_site_pf13b_sitemap_urls_self_canonical` | build check | every `<loc>` in `out/sitemap.xml` (at least 20) is served from a file whose only canonical is that URL, and the page is not noindex |
| `test_site_pf13b_account_noindex` | build check | `out/account/index.html`: every robots and googlebot tag says `noindex`, no canonical, the link to `/dashboard/` |
| `test_site_pf13b_only_home_names_root` | build check | the raw `<link rel="canonical" href="https://truebex.com/"` (the human test's grep) and the parsed canonical are found in `out/index.html` only |
| `test_site_pf13b_home_and_arabic_unchanged` | build check | home: canonical `https://truebex.com/`, hreflang en / ar / x-default, indexable; `/ar/`: canonical `/ar/`, the same alternates |
| `test_site_pf13b_private_pages_have_no_canonical` | build check | the 41 files that inherited the root's canonical (`/dashboard/**`, `/supplier/**`, `/market/checkout/`, `/checkout/`, `/login/sso/`, `/invite/`, `/account/`, `/404/`, `/_not-found/`, `404.html`) are noindex and name no canonical |

PF7b's `test_site_pf7b_basket_noindex` and `test_site_pf7b_copy_and_sources` still cover the basket's `canonical: null`. PF13's `test_site_pf13_arabic_page` covers the hreflang pair.

## Human test

Set-up, in the worktree: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1`. It prints `serving … on http://127.0.0.1:3177/` (3100 + the task number). If it prints another port, use that port below. No API is needed.

1. In Edge or Chrome, open `view-source:http://127.0.0.1:3177/dashboard/` and press Ctrl+F `canonical` → no match. Its `<meta name="robots" content="noindex, nofollow"/>` is there.
2. The same for `view-source:http://127.0.0.1:3177/supplier/` and `view-source:http://127.0.0.1:3177/market/checkout/` → no `canonical`, robots `noindex, nofollow`.
3. `view-source:http://127.0.0.1:3177/` → `<link rel="canonical" href="https://truebex.com/"/>` and three `<link rel="alternate" hrefLang=…>` tags: `en` → `https://truebex.com/`, `ar` → `https://truebex.com/ar/`, `x-default` → `https://truebex.com/`.
4. `view-source:http://127.0.0.1:3177/pricing/` → `<link rel="canonical" href="https://truebex.com/pricing/"/>`.
5. `view-source:http://127.0.0.1:3177/account/` → `<meta name="robots" content="noindex, follow"/>`, no `googlebot` tag, no `canonical`.
6. Open `http://127.0.0.1:3177/account/` normally → the address bar moves to `/dashboard/`. Signed out, the dashboard then sends you to `/login/?next=%2Fdashboard%2F` ("Log in"). Signed in, you stay on the dashboard.
7. Optional, in PowerShell in the worktree: `Get-ChildItem out -Recurse -Filter *.html | Select-String -SimpleMatch 'rel="canonical" href="https://truebex.com/"' -List | Select-Object -ExpandProperty Path` → one line, `…\out\index.html`.

## Risks / traps

* **A new private page.** It no longer needs `canonical: null` to avoid pointing at the home page; it only needs `robots` noindex. A private page under a layout that names a canonical must still set `canonical: null` (`truebex-seo` checklist item 9). The gate fails any canonical that is not the page's own URL.
* **A new public page that forgets its canonical** now ships none instead of the home page's. That is better than a wrong one, but it still breaks checklist item 1. If the page is in the sitemap, `test_site_pf13b_sitemap_urls_self_canonical` fails.
* **Soft navigation leaves stale head tags.** After a client-side redirect (`/account/` → `/dashboard/` → `/login/`), the live DOM can hold the previous page's robots tag beside the new one (seen in headless Edge). Crawlers read each URL's served HTML, which is what the gate checks.

## As-built

* **Date, branch, commits:** 2026-10-14, `ap/t77-pf13b-no-page-but-the-home-page` from `master` 988334f (Claude Autopilot T77): `7a59d8a` the build gate (written first; 7 failed, 2 passed on 988334f's build); `c405cb8` the root layout, `/account/`'s layout, the basket comment, the `truebex-seo` checklist line; then this documentation (the doc, the tracker row, the README section).
* **The gate on 988334f's build:** `root_layout_names_no_canonical` ("src/app/layout.tsx sets alternates"), `account_layout_noindex_source` (no layout), `canonical_is_own_url` and `noindex_names_no_other_url` (the 41 files above), `account_noindex` (`['index, follow', 'index, follow, max-image-preview:large']`), `only_home_names_root` (41 more files than `index.html`), and `private_pages_have_no_canonical` failed. `sitemap_urls_self_canonical` and `home_and_arabic_unchanged` passed; they guard what must not move.
* **Counts:** `out/` has 69 HTML files outside `_next` (68 `index.html` + `404.html`). Pages with a canonical went from 68 to 27: the 23 sitemap URLs, each naming itself, and the four noindex pages that name themselves (`/app/`, `/app/project/`, `/invite/project/`, `/login/`). Pages naming `https://truebex.com/` went from 42 to 1. Noindex pages went from 45 to 46 (`/account/`). Pytest collected 718 → 727 (9 new).
* **Byte checks against 988334f's build:** every meta, title, canonical and hreflang tag in the head of `out/index.html` (35 tags) and `out/ar/index.html` (35) is identical. Across all 69 files, the only metadata changes are the 41 dropped canonicals and `/account/`'s robots (`index, follow` + googlebot → `noindex, follow`). `out/sitemap.xml` is identical apart from `lastmod` (the build time); `out/robots.txt` is identical.
* **Self-tests:** `npm run lint`; `npm run build`; `test_site_pf13b.py` with `test_site_pf1.py`, `test_site_pf12.py`, `test_site_pf13.py`, `test_site_pf13a.py`, `test_pf7b_basket.py`: 62 passed. A grep of `out/` for `rel="canonical" href="https://truebex.com/"` finds only `out/index.html`. Headless Edge over CDP on the served `out/` (port 3177): the live DOM of `/`, `/ar/` and `/pricing/` after hydration has the same canonical and hreflang tags. `/market/checkout/` and `/market/basket/` have none. `/account/` navigates to `/dashboard/` and then, signed out, to `/login/?next=%2Fdashboard%2F`. No page errors. `scripts/autopilot-verify.ps1` green in 8 min: lint, build, pytest 710 passed + 17 skipped (727 collected), `out/index.html` carries the API URL.
* **Deviations from the task text:** the task counted 37 inheriting `index.html` pages. The base build had 40 (admin/render, cloud and webhooks under `/dashboard/` were not in its list); all 40 and `404.html` are covered. Beyond the five checks the task named, the gate has two source checks (no `alternates` in the root layout; `/account/`'s layout), a home / Arabic guard and the explicit list of the 41 formerly inheriting files, so a regression names the page.
* **Contract:** none; nothing to record in the Unreal repo's `contracts/`.
* **Owner at deploy:** nothing beyond the usual deploy. No IndexNow ping or sitemap resubmission: no public page changed. Live check after the deploy: `curl -s https://truebex.com/dashboard/ | findstr canonical` prints nothing, and `https://truebex.com/` still has its canonical and three hreflang links.
* **Carry-over → which feature:** PF13's owner: a `not-found.tsx` with its own metadata, so the 404 page drops the layout's `index, follow` and googlebot tags beside Next's `noindex`; and whether the root's `og:url` should stay on private pages (Out, above).
