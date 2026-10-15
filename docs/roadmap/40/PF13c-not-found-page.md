# PF13c — A Truebex not-found page: one title, noindex only, a way back (launch priority 2)

**Needs merged:** PF13 (the root layout, the site build checks), PF13b (no inherited canonical; `test_site_pf13b.py`), PF5a (`scripts/serve-out.py`'s `Server` and `make_server`); all on `master` cc905d3. **Unblocks:** nothing waits on it. It closes PF13b's As-built carry-over ("a `not-found.tsx` with its own metadata, so the 404 page drops the layout's `index, follow` and googlebot tags beside Next's `noindex`"). **Contract:** none. No endpoint or app code changes. It touches site metadata, one page, the Navbar and the local static server.

## Status

**Built (2026-10-15, branch `ap/t85-pf13c-a-truebex-not-found-page-o`, Autopilot T85); see As-built.** Checked on `master` cc905d3, in the source and in its built `out/`, before the work began:

| Area | Where (master cc905d3) | Before |
|---|---|---|
| Not-found page | no `src/app/not-found.tsx` | Next's default not-found page, exported three times: `out/404.html`, `out/404/index.html`, `out/_not-found/index.html` |
| Titles | Next's default component + `src/app/layout.tsx:22` `title.default` | two `<title>`s: `404: This page could not be found.` and `Truebex — See It Before You Build It` |
| Robots | Next's own tag + `src/app/layout.tsx:67` `robots` | three tags: `noindex` (Next), then the layout's `index, follow` and googlebot `index, follow, max-image-preview:large` |
| Body | Next's default | `404 \| This page could not be found.` (black on white, or white on black), under the Navbar, with no link anywhere but the Navbar |
| Local server | `scripts/serve-out.py` (`SimpleHTTPRequestHandler`) | a missing path answers Python's plain "Error response … 404" page, so no human test ever showed the site's 404 page |
| Navbar | `src/components/layout/Navbar.tsx:26` `usePathname()` | picks Arabic labels for any `/ar/…` path and hides itself for any `/app/…` path (found in this task's self-test, below) |

GitHub Pages answers any missing path with `404.html` and status 404. `/404/` and `/_not-found/` are real folders in `out/`, so they answer 200.

## Goal

A dead link on truebex.com lands on a page in the site's own look and words. That can be a link from the app, an old e-mail or a typo. The page offers a way back to the home page, the download and pricing. Search engines read one clear signal on it: one title and robots tags that only say `noindex`. The local static server answers a missing path with this page, the way GitHub Pages does, so a human test sees what visitors will see.

## Read first

* `docs/roadmap/40/00-contract.md` P.3, P.4.
* `PF13b-private-pages-canonical.md` (Out: "The 404 page's second robots tag"; As-built: "Carry-over").
* `.claude/skills/truebex-seo/SKILL.md` (how the site is wired, checklist item 9) and `.claude/skills/truebex-brand-voice/SKILL.md` (voice, tokens).
* `src/app/layout.tsx` (`metadata.robots`, the Navbar), `src/components/layout/Navbar.tsx`, `src/components/ui/Button.tsx`, `scripts/serve-out.py`, `server/tests/test_site_pf13b.py` (`canonicals`, `robots`).

## Scope

**In:**

1. `src/app/not-found.tsx`: the site's own not-found page. It has an eyebrow (`404 · Page not found`), one `h1`, one line, a link home and two of the site's own destinations (Download, Pricing). It is built from the site's tokens, `Button` and the `blueprint-grid` motif, with no new dependency. It is English only and reads well at 390 px and 1280 px. The copy is `NOT_FOUND` at the end of `src/lib/constants.ts`.
2. Its own metadata. The title is `Page not found`, giving `Page not found · Truebex` through the root template. Robots is `{ index: false }`, which replaces the root's whole `robots` object, googlebot included. The built head is checked, not the source.
3. `scripts/serve-out.py`: a 404 answers the served folder's `404.html` with status 404 and `Access-Control-Allow-Origin: *`. A folder without one answers the standard error page. The backlog of 128, the web types, a folder's `index.html` and the slash-less 301 are unchanged.
4. The Navbar takes its language and its `/app/` switch from the route segment, not the address bar. A dead `/ar/…` or `/app/…` link then hydrates as served: no Arabic labels on the English page, no missing Navbar, no React hydration error. Every real page renders exactly as before. This item was not in the task text; the self-test found the fault (As-built).
5. The build checks first, watched failing on master's build: `server/tests/test_site_pf13c.py`.
6. One line in `truebex-seo` ("How the site is wired") about the not-found page and the Navbar.

**Out (and where it goes):**

* **The root layout's robots for public pages, the root `openGraph.url`, the sitemap, `robots.txt`, any public page's head:** unchanged. The 404 page keeps the root's `og:title` and `og:url` (`https://truebex.com/`). Private pages' `og:url` is the owner's call (PF13b, Out).
* **Next's own `noindex`:** Next 16.1.6 still writes `<meta name="robots" content="noindex"/>` on its not-found route, ahead of the metadata. The page's own tag says the same thing, so the head has two identical `noindex` tags and nothing that says `index`. Dropping the page's tag would leave the page relying on Next alone, and `/404/` and `/_not-found/` answer 200 on GitHub Pages.
* **An Arabic not-found page:** none. The Arabic site is one page. GitHub Pages serves the one `404.html` for `/ar/…` paths too, and that page is English (Scope 4).
* **`/404/` and `/_not-found/` answering 200:** they are folders Next exports. Both are `noindex` with no canonical, and neither is in the sitemap. GitHub Pages answers them the same way.
* **Folder listings in `serve-out.py`:** a folder in `out/` without an `index.html` (`/_next/…`, `/images/`) is still listed, where GitHub Pages answers 404. This is unchanged; no page links to a folder.

## Design

**API, data, jobs:** none.

**Metadata.** Next 16.1.6 honours `export const metadata` in `src/app/not-found.tsx`. It merges top-level keys shallowly from the root layout down, so:

* `title: "Page not found"` goes through the root's `template` (`%s · Truebex`). The default component's own `<title>404: …</title>` is gone with the default component. One `<title>` remains.
* `robots: { index: false }` replaces the root's whole `robots` object, `googleBot` included. It renders `<meta name="robots" content="noindex"/>`. `follow` is left out: search engines follow links by default, and the tag then says only `noindex`.
* No `alternates`: the root names no canonical (PF13b), so the page has none.

**UI.** One `<main>`, full viewport height, the content centred over the drafting grid (masked to the centre, as on the home hero). There is an accent eyebrow, an `h1` (`text-balance`), a line (`text-pretty`), and three buttons: `Go to the home page` (primary, `/`), `Download for Windows` (`/download/`) and `Pricing` (`/pricing/`). They sit in a row at 640 px and up, and stack at full width below. The buttons are plain `<a>` links (`Button href`), a full page load, because the page can be served at any address. There is no footer, so no analytics beacon either: the page is not a public page in the analytics sense.

**Navbar.** `useSelectedLayoutSegment()` in the root layout's Navbar returns the first route segment: `null` on `/`, `ar` on `/ar/`, `app` under `/app/`, and `/_not-found` (the route tree in `404.html`) on the not-found page wherever it is served. `usePathname()` returns the address bar, which differs from the server's render only on the not-found page.

**serve-out.py.** `Handler.send_error` serves `<directory>/404.html` for a 404 with `Content-Type: text/html; charset=utf-8`, its `Content-Length`, `Connection: close` and, through `end_headers`, `Access-Control-Allow-Origin: *`. A `HEAD` request gets the headers without the body. Any other code, or a folder without `404.html`, goes to the standard `send_error`.

**Security and privacy:** none. No cookies, beacon or user data.

## Deliverables

- [x] `src/app/not-found.tsx`; `NOT_FOUND` at the end of `src/lib/constants.ts`
- [x] `src/components/layout/Navbar.tsx`: the route segment instead of the address bar
- [x] `scripts/serve-out.py`: `send_error`, `not_found_page`
- [x] `server/tests/test_site_pf13c.py` (10 checks)
- [x] `.claude/skills/truebex-seo/SKILL.md`: one line under "How the site is wired"
- [x] this doc with two screenshots (`img/PF13c-not-found-1280.png`, `img/PF13c-not-found-390.png`); the tracker row; a README section

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_site_pf13c_not_found_source` | pytest (source) | `src/app/not-found.tsx` is a server component exporting `metadata` with `robots: { index: false }` and using `NOT_FOUND`; the copy names the page as not found and has an eyebrow, heading, line, home label and links to site folders |
| `test_site_pf13c_navbar_follows_route_segment` | pytest (source) | the Navbar uses `useSelectedLayoutSegment()` (`ar`, `app`) and not `usePathname` |
| `test_site_pf13c_one_title` | build check | each of the three files has exactly one `<title>`, `Page not found · Truebex`, which says "not found" |
| `test_site_pf13c_robots_noindex_only` | build check | each file has robots tags; every robots and googlebot tag contains `noindex`; none says `index` without `no` |
| `test_site_pf13c_no_canonical` | build check | no `<link rel="canonical">` in any of the three |
| `test_site_pf13c_heading_and_way_back` | build check | one `h1` with `NOT_FOUND.heading`; one `<main>` with the line; an `<a href="/">` reading `Go to the home page`; the Download and Pricing links |
| `test_site_pf13c_next_default_gone` | build check | `This page could not be found` appears nowhere in the HTML (body, title or RSC payload); no `h1.next-error-h1` |
| `test_site_pf13c_not_in_sitemap` | build check | no sitemap URL holds `404` or `_not-found`; none of the three files' URLs is listed |
| `test_site_pf13c_serve_out_answers_404_page` | pytest (server) | `make_server` on a free port over a temporary folder: `/` → 200 with `index.html`; `/pricing/` and the slash-less `/pricing` → the folder's `index.html`; `.js` → `text/javascript`; `/no-such-page/`, `/no-such-page`, `/ar/old-link/`, `/pricing/gone.html`, `/x.js?v=1` → 404 with the `404.html` bytes, `text/html`, its length and `Access-Control-Allow-Origin: *`; `HEAD` → 404 with no body; a folder without `404.html` → 404 with the standard "Error response" page and the CORS header |
| `test_site_pf13c_serve_out_keeps_backlog` | pytest (server) | `Server.request_queue_size` ≥ 128 |

PF13b's gate (`test_site_pf13b.py`, unchanged) still checks every page's canonical. Its `private_pages_have_no_canonical` covers the three not-found files and `canonical_is_own_url` covers all 69.

## Human test

About 3 minutes. Set-up, in the worktree: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1`. It prints `serving … on http://127.0.0.1:3185/` (3100 + the task number). If it prints another port, use that port below. No API is needed.

1. In Edge or Chrome, open `http://127.0.0.1:3185/no-such-page/` → the Truebex page: the Navbar, `404 · PAGE NOT FOUND`, **Nothing stands at this address**, one line, and three buttons: `Go to the home page`, `Download for Windows`, `Pricing`. The tab reads `Page not found · Truebex`. Press F12 → Network, then Ctrl+R → the first row, `no-such-page/`, has status **404**.
2. Click `Go to the home page` → the home page (`http://127.0.0.1:3185/`, "See it before you build it.").
3. Open `view-source:http://127.0.0.1:3185/no-such-page/`. Ctrl+F `<title` → one match, `<title>Page not found · Truebex</title>`. Ctrl+F `name="robots"` → two matches, both `<meta name="robots" content="noindex"/>`. Ctrl+F `googlebot` → no match. Ctrl+F `canonical` → no match.
4. Back on the page, F12 → the device toolbar (Ctrl+Shift+M), width 390 → the heading on two lines, the line under it, the three buttons stacked full width, and no sideways scroll.
5. Open `view-source:http://127.0.0.1:3185/` → `<link rel="canonical" href="https://truebex.com/"/>` and three `<link rel="alternate" hrefLang=…>` tags, as before: `en` → `https://truebex.com/`, `ar` → `https://truebex.com/ar/`, `x-default` → `https://truebex.com/`.
6. Optional: open `http://127.0.0.1:3185/ar/old-link/` and `http://127.0.0.1:3185/app/old-link/` → the same English page, with the English Navbar (`Product`, `How It Works`, … and `العربية`). `http://127.0.0.1:3185/ar/` is still the Arabic page, right to left.

## Risks / traps

* **Root-layout components and the address bar.** The one `404.html` is served at every missing address. A component in the root layout that renders from `usePathname()` renders one thing on the server (`/_not-found`) and another in the browser, which is a hydration mismatch. Read the route segment (`useSelectedLayoutSegment`) instead, or keep address-dependent output inside an effect.
* **Next's own `noindex`** comes first in the head, outside the metadata. It is harmless beside the page's own tag. A gate that counts robots tags would see two.
* **The order of `next-size-adjust`** among the head's meta tags varies between builds of the same source. Two builds of cc905d3 put it in different places on the 404 pages, and two of this branch's builds put it elsewhere on `/login/`. Compare tag sets, not head bytes, across builds.
* **A missing page under `/ar/`** is answered in English. That is intended while the Arabic site is one page; an Arabic 404 would need GitHub Pages to serve per-folder 404 pages, which it does not.

## As-built

* **Date, branch, commits:** 2026-10-15, `ap/t85-pf13c-a-truebex-not-found-page-o` from `master` cc905d3 (Claude Autopilot T85): `06135d0` the build and server checks, written first; `089ea47` `not-found.tsx`, `NOT_FOUND`, `serve-out.py`; `1d8490e` the Navbar follows the route segment, with its source check and `text-balance` / `text-pretty`; then this documentation (this doc and its two screenshots, the tracker row, the README section, the `truebex-seo` line).
* **Metadata mechanism:** `export const metadata` in `src/app/not-found.tsx`. Next 16.1.6 applies it to all three exported files, so no fallback was needed. Its `robots` replaces the root's whole object (googlebot gone). Next's own `noindex` stays beside it.
* **The tags, before (cc905d3) → after,** the same in `out/404.html`, `out/404/index.html` and `out/_not-found/index.html`:

  | Tag | Before | After |
  |---|---|---|
  | `<title>` | `404: This page could not be found.` and `Truebex — See It Before You Build It` | `Page not found · Truebex` |
  | robots | `noindex` (Next), `index, follow` (layout) | `noindex` (Next), `noindex` (the page) |
  | googlebot | `index, follow, max-image-preview:large` | none |
  | canonical | none (since PF13b) | none |
  | `og:title`, `og:url` | the root's | the root's, unchanged (Out) |
  | body | `404 \| This page could not be found.` | `Nothing stands at this address`, the line, three links |

* **The gate on cc905d3's build:** `not_found_source` (no `not-found.tsx`), `one_title` (the two titles above), `robots_noindex_only` (`['noindex', 'index, follow', 'index, follow, max-image-preview:large']`), `heading_and_way_back` (`h1` `404`), `next_default_gone` and `serve_out_answers_404_page` (Python's "Error response" page) failed. `no_canonical`, `not_in_sitemap` and `serve_out_keeps_backlog` passed; they guard what must not move. `navbar_follows_route_segment` was added with the Navbar fix and fails on cc905d3's source (`usePathname`, no `useSelectedLayoutSegment`).
* **Counts:** pytest collected 824 → 834 (10 new). `out/` still has 69 HTML files outside `_next`. Pages whose head tags changed: 3 (the three not-found files). Noindex pages: unchanged at 46. Sitemap: 23 URLs, unchanged.
* **Byte checks against cc905d3's build:** the home page's and `/ar/`'s 39 head tags each (every meta, the title, canonical, hreflang alternates, manifest and icon links) are identical. Across all 69 files, only the three not-found files' tags changed. The Navbar's server-rendered HTML is identical on all 68 pages that have one. `out/sitemap.xml` is identical apart from `lastmod` (the build time), and `out/robots.txt` is identical. Two of the branch's earlier builds flagged `/login/`, where only `next-size-adjust`'s position had moved. A second build of cc905d3 itself moved the same tag on the 404 pages, and the gate's build matched master's `/login/` again (Risks).
* **Self-tests:** `npm run lint`. `npm run build` (three times). `test_site_pf13c.py` with `test_site_pf1.py`, `test_site_pf12.py`, `test_site_pf13.py`, `test_site_pf13a.py`, `test_site_pf13b.py`, `test_pf7b_basket.py` and `test_shares_pf5a.py`: 81 passed. `scripts\autopilot-serve.ps1` on port 3185, checked with curl: `/no-such-page/`, `/no-such-page` and `/ar/old-link/` → `404 Not Found`, the body byte-equal to `out/404.html`, `Access-Control-Allow-Origin: *`. `/404/` and `/_not-found/` → 200. `/pricing` → 301 to `/pricing/`. Headless Edge over CDP (scratchpad `cdp_pf13c.mjs`) on the gate's build, at 1280 × 900 and 390 × 844, on `/no-such-page/`:
  * the document answered 404, with one `<title>` (`Page not found · Truebex`) in the live DOM;
  * robots `noindex` twice, no googlebot tag, no canonical;
  * the `h1` and no "could not be found" text;
  * no horizontal scroll (`scrollWidth − clientWidth` = 0 at both widths);
  * the home button is 183 × 40 px at 1280 and 358 × 40 px at 390, and clicking it lands on `/` with status 200 and the home canonical.

  `/ar/old-link/` and `/app/old-link/` show the same English page with the English Navbar. `/`, `/ar/` (Arabic, `rtl`), `/app/` (no Navbar) and `/pricing/` hydrate with no exception. The only console lines are the expected "Failed to load resource … 404" for the 404 documents and `/pricing/`'s refused call to the production API from a local origin (unrelated). Screenshots: `img/PF13c-not-found-1280.png`, `img/PF13c-not-found-390.png`. `scripts\autopilot-verify.ps1` was green in 871 s: lint, build, pytest 817 passed + 17 skipped (834 collected), and `out/index.html` carries the API URL.
* **Deviations from the task text:**
  * **The Navbar (Scope 4) was not in the BUILD list.** The first headless run showed the fault: on `/ar/old-link/` the Navbar switched to Arabic labels over the English page, and on `/app/old-link/` the Navbar vanished. React logged minified error #418 (hydration mismatch) both times. The cause is `usePathname()`, which reads the address bar that GitHub Pages leaves on the dead link. `useSelectedLayoutSegment()` fixes both, and every real page's Navbar HTML is unchanged.
  * **Beyond the checks the task named,** there are two source checks (the page's metadata and copy, the Navbar) and a backlog guard. The server check also covers the slash-less path, a query string, `HEAD` and the content headers.
* **Contract:** none; nothing to record in the Unreal repo's `contracts/`.
* **Owner at deploy:** nothing beyond the usual deploy. No IndexNow ping and no sitemap change, because the page is noindex. Live check after the deploy: `curl -sI https://truebex.com/no-such-page/` → `HTTP/2 404`, and the page in a browser shows "Nothing stands at this address" with the tab `Page not found · Truebex`.
* **Carry-over → which feature:** PF13's owner decides whether the root's `og:title` / `og:url` should stay on the 404 page and the other private pages (PF13b, Out). Nothing else.
