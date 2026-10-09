# PF13 — Website: pricing, features, roadmap, Arabic, changelog, analytics (launch priority 1)

**Needs merged:** nothing. **Unblocks:** none by Needs; PF2's provider approval (a live pricing page) and GD6's launch plan lean on it. **Contract:** none (public website; it reads PF1's catalogue and release feed and PF2's prices when they exist).

## Status

**Built 2026-10-09 on `ap/t2-pf13-website-pricing-features-ro`** (verify gate green; see As-built). The table below is the state the task started from.

The site is one landing page with a three-plan pricing section and a hand-written roadmap list. Verified with Grep on 2026-10-09:

| Area | Where | Today |
|---|---|---|
| Pricing | `src/components/sections/Pricing.tsx:112-131` from `PRICING_PLANS` (`src/lib/constants.ts:236-289`) | Starter, Professional ($99), Enterprise; no annual, no founding offer |
| Home JSON-LD offers | `src/app/page.tsx:15-55`, offers `:30-44` | Starter $0, Professional $99 |
| Features | `FEATURES` (`src/lib/constants.ts:56-120`), `src/components/sections/CoreFeatures.tsx:20` ("Nine capabilities … all shipping today") | one section, no feature pages |
| Roadmap | `ROADMAP` (`src/lib/constants.ts:123-164`), rendered at `CoreFeatures.tsx:42-58` ("On the roadmap", `:45`) | hand-written, no status |
| Captures | `PRODUCT_SHOT` (`src/lib/constants.ts:167-174`): one clean capture | brand rule: clean captures only (`.claude/skills/truebex-brand-voice/SKILL.md:26`) |
| Navigation | `NAV_LINKS` (`src/lib/constants.ts:46-54`; Pricing → `/#pricing` at `:50`), footer `RESOURCES` (`src/components/layout/Footer.tsx:5-12`) | no language switch, no social links |
| Language | `src/app/layout.tsx:99` (`<html lang="en">`), `:43` (`locale: "en_US"`), `:40` (canonical) | English only |
| Organisation JSON-LD | `src/app/layout.tsx:71-91` | no `sameAs` |
| Sitemap | `src/app/sitemap.ts:7-15` | five URLs, no alternates |
| SEO plan | `.claude/skills/truebex-seo/SKILL.md:33-46` (keyword map), `:43` (Arabic `/ar/`), `:48-55` (content engine: feature pages, changelog, Arabic), `:57-61` (Search Console, Bing, IndexNow), `:74-79` (privacy-friendly analytics) | written, not built |
| Analytics, verification | none in the code | |

What the owner meant: app-side `00-understanding.md` §1 (tiers), §15 ("the website is updated … to show what shipped … and the roadmap in Truebex's own words").

## Goal

The website sells the product the owner is launching: a pricing page on the final tiers (Free, Pro, Studio, Team, Enterprise and the founding seats) with a monthly / annual switch; one page per search cluster that answers the query with clean captures; a roadmap that follows the real plan; an Arabic landing page that search engines pair with the English one; a changelog fed by the release feed; analytics that respect visitors; and the site verified with search engines and linked to its social accounts.

## Read first

* `docs/roadmap/40/00-contract.md` (P.3 items 1–2: copy in `constants.ts`, the per-page SEO checklist); app-side `00-understanding.md` §1, §15.
* `.claude/skills/truebex-brand-voice/SKILL.md` (positioning `:13-29`, only shipped claims `:31-71`, payments `:73-74`) and `.claude/skills/truebex-seo/SKILL.md` (the per-page checklist `:22-31`) — every page goes through both.
* `guides/GD7-*.md` (tiers, prices, founding seats, the matrix) and `guides/GD6-*.md` (launch plan, social handles, the Arabic copy review) are not written yet: every price and handle is a placeholder `from GD7` / `from GD6`, and no placeholder text may reach `out/`.
* PF1 (`server/app/catalogue.json`, `src/content/releases.json`, `/changelog/`, `/download/`), PF2 (prices in the catalogue, `/billing/plans`, checkout links).
* Google Search Central: "Tell Google about localized versions of your page" (hreflang); Cloudflare Web Analytics documentation; the IndexNow protocol (indexnow.org).

## Scope

**In:**
1. The pricing page `/pricing/` on the GD7 tiers — Free, Pro, Studio, Team, Enterprise — with a monthly / annual toggle, a currency choice (GBP, USD, EUR), the per-seat note on per-seat tiers, the founding offer (seats left, the lasting discount), a comparison table from the entitlement matrix, a pricing FAQ, and calls to action (Start free → sign-up, a tier → `/dashboard/billing/?tier=…&interval=…`, Enterprise → contact); every number read from `server/app/catalogue.json` at build time (placeholders `from GD7` until then), the founding count refreshed from `/billing/plans` after load.
2. Matrix rows for features that are not shipped carry "On the roadmap" (brand rule `SKILL.md:65`); the Free tier's facts follow `00-understanding.md` §1 (the full modeller, watermark on exports, one storey, the 14-day Pro trial).
3. The home pricing section becomes a three-tier teaser from the same catalogue with "See all plans"; the home JSON-LD offers come from the catalogue too.
4. Feature pages per search cluster: `/features/daylight/`, `/features/surfaces/`, `/features/assets/`, `/features/sheets/`, `/features/marketplace/`; each with one h1 holding the cluster's phrase, a short how-it-works, clean captures with alt text naming the feature, a page FAQ, links to download and sign-up; the marketplace page written as roadmap ("On the roadmap", never present tense) with a supplier interest link.
5. Clean captures: `scripts/make_web_assets.py` gains crops for the new pages from clean source frames in the Unreal project; a page whose clean frame does not exist yet ships with text and the existing capture, never with a HUD frame.
6. The roadmap fed from the plan: `src/content/roadmap.json` (public items in Truebex's words, each mapped to tracker ids) with statuses (planned, in progress, shipped) written by `scripts/sync-roadmap.mjs` from both trackers; the home roadmap block and a `/roadmap/` page read it; nothing moves into `FEATURES` automatically.
7. The Arabic landing page `/ar/`: the home content in Arabic, right to left, an Arabic web font, `hreflang` alternates on `/` and `/ar/` (with `x-default`), the sitemap's alternates, a language switch in the navbar and footer.
8. The changelog page from PF1's release feed: PF1's release entries plus the product's history (the shipped roadmap 39 plans in Truebex's words), anchors per version, JSON-LD, an Atom feed `/changelog/feed.xml`, links from the nav and footer.
9. Privacy-friendly analytics: Cloudflare Web Analytics on public pages only (no cookies, no cross-site tracking; Cloudflare is already a named processor), and conversions counted from the platform's own records (sign-ups, downloads, trials, checkouts per day) on an admin Growth panel; the privacy page says so.
10. Search Console and Bing verification: `metadata.verification` tags in the root layout (tokens are public), the owner's DNS TXT record for the domain property, the sitemap submitted; an IndexNow key file and `scripts/indexnow.mjs` the owner runs after a deploy.
11. Social links: `SOCIAL` in `constants.ts` (handles `from GD6`), a Follow column in the footer showing the set ones, `sameAs` in the Organization JSON-LD.
12. Every page through the brand-voice and SEO skills: metadata, one h1, canonical with trailing slash, server-rendered text, sitemap entry, JSON-LD kept in step; the SEO skill's keyword map updated to the pages that now exist.
13. Build checks for all of it.

**Out (and where it goes):**
* Prices, founding seats and the matrix values → GD7; social handles, launch posts and clips → GD6; Arabic copy review by a native speaker → the owner (GD6).
* The release feed, `/download/` and the release entries → PF1; checkout and the billing page → PF2.
* Arabic inside the app → LO1 (app); Arabic for the dashboard and portal → not in roadmap 40.
* A blog → not planned (the changelog and feature pages carry the fresh content, SEO skill `:48-55`).

## Design

### API

The site is static; it calls only `GET /billing/plans` (PF2, for the live founding count; the page renders without it) and adds one admin read for conversions:

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/admin/growth?from=&to=` | admin (PF1's `require_admin`) | `{days: [{day, signups, downloads, trials, checkouts, paid}]}` counted from `users.created_at`, PF1's download log, trial subscriptions and payments; no personal data |

### Data

| File | Holds | Written by |
|---|---|---|
| `server/app/catalogue.json` (PF1's schema) | tiers, prices (PF2), founding, the matrix | PF1 / PF2; if this task lands first it adds the file with `licence-api.md` §6.3's placeholder matrix and null prices, exactly as PF1 specifies, and the merge keeps one copy |
| `src/content/roadmap.json` | `[{id, title, description, icon, plan_ids: ["IO1", "IO2", "IO4"], status}]` | titles and descriptions by hand (brand voice); `status` by `scripts/sync-roadmap.mjs` |
| `src/content/history.json` | `[{date, title, summary}]` for the shipped roadmap 39 plans, in Truebex's words | by hand from the app's As-built notes |
| `src/content/releases.json` | the release feed (PF1) | `npm run sync:releases` |
| `src/lib/constants.ts` | `PRICING` (tier copy keyed by tier id, FAQ, comparison labels per feature key), `FEATURE_PAGES` (five pages' copy), `AR_HOME` (Arabic copy), `SOCIAL`, `ANALYTICS` (the Cloudflare beacon token, public), `VERIFICATION` (Google, Bing tokens, public) | by hand |

`scripts/sync-roadmap.mjs <app tracker path> <platform tracker path>` reads the two README tables (`[x]` = merged, a branch in "Code today" = in progress) and writes statuses; it runs on the owner's machine before a deploy, never in the build. **Decision:** public words by hand, statuses from the trackers. Rejected: printing tracker rows on the site (engineering names, brand rule 1).

### UI

| Route | Content | SEO |
|---|---|---|
| `/pricing/` | `src/components/pricing/` (`TierCards` with the toggle and currency, `FoundingBanner`, `ComparisonTable`, `PricingFaq`); tiers without a price show "Price at launch" and the founding block stays hidden until the catalogue has numbers | title "Pricing" (≤ 60 chars with " · Truebex"), FAQPage + SoftwareApplication `offers` (one Offer per priced tier and interval), canonical `/pricing/` |
| `/features/{daylight,surfaces,assets,sheets,marketplace}/` | `src/components/features/FeaturePage.tsx` filled from `FEATURE_PAGES`; marketplace in roadmap voice | WebPage + BreadcrumbList + FAQPage; each in the sitemap |
| `/roadmap/` | items grouped by theme with status chips (planned, in progress, shipped); the home block shows the same data | WebPage + BreadcrumbList |
| `/ar/` | `src/app/ar/page.tsx`: the home sections from `AR_HOME`, `lang="ar" dir="rtl"` on its wrapper, an Arabic web font (an OFL-licensed Arabic sans through `next/font/google`, loaded on this route only), logical CSS properties (`ms-`, `me-`) so the layout mirrors | `alternates.languages {en: "/", ar: "/ar/", "x-default": "/"}` on both pages; WebPage `inLanguage: "ar"` |
| `/changelog/` (PF1's page) | release entries (PF1) and history entries (this task), one anchor per entry, `/changelog/feed.xml` (Atom, `force-static` like `src/app/sitemap.ts`) | BreadcrumbList; the feed linked with `rel="alternate"` |
| Navbar, footer | Pricing → `/pricing/`; a language switch (English · العربية); footer Follow column from `SOCIAL`, Changelog and Roadmap in Resources | |
| Root layout | `verification` tags; the analytics beacon through `next/script` (`afterInteractive`) on public routes only (not `/dashboard/`, `/app/`, `/supplier/`); `suppressHydrationWarning` on `<html>` | |

**Decision: the Arabic page's `<html lang="ar" dir="rtl">` is written by a post-build step** (`scripts/postbuild-lang.mjs` rewrites `out/ar/index.html`; `npm run build` runs it after `next build` and PF5's viewer step), with `lang` and `dir` also on the page wrapper for the client. Rejected: two root layouts in route groups (every existing route would move into a group, colliding with the routes parallel PF branches add); a client-side script setting `lang` (crawlers read the HTML as served).

**Decision: Cloudflare Web Analytics.** Cookieless, no cross-site profile, free, and Cloudflare is already the site's named processor (`src/app/privacy/page.tsx:75`); goals come from the platform's own counts. Rejected: a paid hosted analytics service (another processor and fee, though it records custom goals); self-hosting an analytics server (needs PF14's server and is one more service to run).

### Jobs / workers

None on the server. Owner-run scripts: `npm run sync:releases` (PF1), `node scripts/sync-roadmap.mjs …`, `node scripts/indexnow.mjs <changed URLs>` after a deploy; `py -3.12 scripts/make_web_assets.py` for new clean crops.

### Security and privacy

* Verification and analytics tokens are public by design; no secret enters `constants.ts` or `out/`.
* The beacon never loads on signed-in areas (dashboard, app, supplier portal) or share pages.
* The privacy page gains "Website analytics" (what Cloudflare Web Analytics measures, no cookies) and keeps its processor list in step with PF2 and PF14.

## Deliverables

- [x] `src/app/pricing/`, `src/components/pricing/`, the home teaser in `src/components/sections/Pricing.tsx`, home JSON-LD offers from the catalogue (`src/lib/catalogue.ts` reads `server/app/catalogue.json`)
- [x] `src/app/features/*/`, `src/components/features/FeaturePage.tsx`, new crops in `scripts/make_web_assets.py` (clean frames only)
- [x] `src/content/roadmap.json`, `scripts/sync-roadmap.mjs`, `src/app/roadmap/`, the home roadmap block reading it
- [x] `src/app/ar/`, `scripts/postbuild-lang.mjs`, `package.json` build script, the language switch
- [x] `src/content/history.json`, the changelog's history entries and `/changelog/feed.xml`
- [x] analytics beacon, `verification` tags, `public/<indexnow key>.txt`, `scripts/indexnow.mjs`, `SOCIAL` and the footer column, `sameAs`
- [x] `/admin/growth` and its panel in the admin dashboard
- [x] `sitemap.ts` with every new URL and the `/` + `/ar/` alternates; privacy page section; `.claude/skills/truebex-seo/SKILL.md` keyword map pointing at the built pages (the Arabic row no longer cites Wayl, which PF2 retires)

## Tests

Build checks are pytest functions in `server/tests/test_site_pf13.py` reading `out/` after the verify gate's build.

| Name | Kind | Asserts |
|---|---|---|
| `test_site_pf13_pricing_page` | build check | `out/pricing/index.html`: one h1, canonical `/pricing/`, five tier names, the monthly / annual toggle's both labels, FAQPage and SoftwareApplication JSON-LD |
| `test_site_pf13_pricing_matches_catalogue` | build check | every price shown equals the catalogue's (minor units formatted per currency); unpriced tiers say "Price at launch" |
| `test_site_pf13_no_placeholder_text` | build check | no "GD7", "GD6", "TODO" or "placeholder" anywhere in `out/**/*.html` |
| `test_site_pf13_roadmap_rows_labelled` | build check | every matrix row whose feature is not shipped carries "On the roadmap" on `/pricing/` |
| `test_site_pf13_feature_pages` | build check | the five pages: one h1 each, unique titles ≤ 60 chars, descriptions 140–160 chars, canonical with trailing slash, JSON-LD, images with `alt`, `width`, `height` |
| `test_site_pf13_marketplace_page_future_tense` | build check | the marketplace page carries "On the roadmap" and none of the shipped-feature claims |
| `test_site_pf13_arabic_page` | build check | `out/ar/index.html` has `<html lang="ar" dir="rtl">`, Arabic text, `hreflang` links to `/` and `/ar/` and `x-default`; `out/index.html` has the reverse links |
| `test_site_pf13_sitemap_complete` | build check | the sitemap lists `/pricing/`, the five feature pages, `/roadmap/`, `/ar/`, `/changelog/` with `/` ↔ `/ar/` alternates |
| `test_site_pf13_changelog_feed` | build check | `out/changelog/feed.xml` is valid Atom with one entry per release and history item |
| `test_site_pf13_analytics_public_only` | build check | the beacon is in `out/index.html` and `out/pricing/index.html`, not in `out/dashboard/**`, `out/app/**`, `out/supplier/**` |
| `test_site_pf13_verification_and_social` | build check | the verification meta tags are present; the footer shows only set social links; `sameAs` lists the same |
| `test_site_pf13_no_competitor_names` | build check | none of a deny list of design-software and engine names in public pages (brand rule 1) |
| `test_site_pf13_json_ld_in_step` | build check | the home `offers` equal the catalogue's priced tiers; the FAQPage questions equal the visible ones |
| `test_admin_growth_counts` | pytest | daily counts of sign-ups, downloads, trials and checkouts; 401 anonymous, 403 non-admin; no e-mail in the answer |
| `npm run lint`, `npm run build` | build check | green |

## Human test

1. Build and serve with `scripts/autopilot-serve.ps1`; open `/pricing/` → five tiers; switch to Annual → the per-month and per-year prices change; switch currency to EUR; the founding banner shows when the catalogue has a founding offer; a roadmap feature row says "On the roadmap".
2. View source of `/pricing/` → title, description, canonical `https://truebex.com/pricing/`, one h1, JSON-LD with the offers.
3. Open each feature page → one h1 with the cluster phrase, clean pictures only, the FAQ, links to download and sign-up; the marketplace page speaks of the future.
4. Open `/roadmap/` → items grouped with statuses; run `node scripts/sync-roadmap.mjs <app README> <platform README>` after ticking a test row in a copy → the status changes after a rebuild.
5. Open `/ar/` on a phone → Arabic text, right-to-left layout, the Arabic font; the language switch returns to `/`; view source → `<html lang="ar" dir="rtl">` and the `hreflang` links.
6. Open `/changelog/` → release and history entries with anchors; `/changelog/feed.xml` opens in a feed reader.
7. Open `/sitemap.xml` → every new URL with the language alternates; `/robots.txt` unchanged.
8. With the analytics token set, open the home page → one request to the beacon in the browser's network panel; open `/dashboard/` → none.
9. Owner (after deploy): verify the domain in Search Console by DNS TXT and the meta tag, submit the sitemap, import into Bing Webmaster Tools, run `scripts/indexnow.mjs` with the new URLs; check link previews of `/pricing/` and `/features/daylight/` in a post inspector.

## Risks / traps

* Static export (`next.config.ts:4`, `:9`): every page is HTML at build time, which is what the SEO checklist needs; the founding count is the only runtime number and the page must read well without it.
* The root layout writes `<html lang="en">` for every route (`src/app/layout.tsx:99`): the post-build rewrite is the only place `/ar/` gets its own; the build check guards it.
* Open Sans has no Arabic glyphs (`src/app/layout.tsx:8-12` loads the Latin subset): the Arabic font loads on `/ar/` only, so other pages stay light.
* Brand rules: only shipped features as facts; roadmap items in future tense; no other software or engine named; numbers with units (`SKILL.md:13-29`, `:65-71`); the deny-list test catches names, a reviewer catches tense.
* Placeholder prices must never ship: unpriced tiers say "Price at launch" and the founding block hides; `test_site_pf13_no_placeholder_text` fails the gate otherwise.
* Hot spots: `constants.ts`, `layout.tsx`, `sitemap.ts`, `Footer.tsx`, `Navbar.tsx`, `package.json` (build script also changed by PF5) are touched by PF1, PF2, PF5 and PF9; edit in own blocks.
* GitHub Pages serves `out/` as is: `feed.xml` and the IndexNow key file must be in `out/` at the paths the scripts expect.

## As-built

* **Date, branch, commits:** 2026-10-09, `ap/t2-pf13-website-pricing-features-ro` (Claude Autopilot T2), on `master` at 744a9f3; commits `git log master..ap/t2-pf13-website-pricing-features-ro`.
* **Counts:** pytest 24 → 51 (`test_site_pf13.py` 20 build checks, `test_admin_growth.py` 7). `out/`: 23 `index.html` pages (was 13: + `/pricing/`, five `/features/<slug>/`, `/roadmap/`, `/changelog/`, `/ar/`, `/dashboard/admin/growth/`), plus `/changelog/feed.xml` (12 Atom entries) and the IndexNow key file; sitemap 5 → 14 URLs, `/` and `/ar/` with `en` / `ar` / `x-default` alternates. Lint, build and the verify gate green.
* **Tests as named in the doc:** every row of the Tests table exists under its name in `server/tests/test_site_pf13.py` (build checks) and `server/tests/test_admin_growth.py::test_admin_growth_counts`; extra: `…_catalogue_placeholder_shape`, `…_catalogue_api_quotas_match_plans`, `…_content_files_valid`, `…_roadmap_page`, `…_sync_roadmap_script`, `…_indexnow_dry_run`, `…_home_teaser_and_nav`, `test_admin_growth_requires_admin` / `_validation` / `_default_range_zero_filled`, `test_me_reports_admin_flag`, `test_download_events_hold_no_personal_data`, `test_admin_cli_sets_flag`. The checks are conditional where the doc's state is: prices, founding, beacon, verification tags and social links are asserted *present and correct* when set and *absent* when not. Self-tested both ways: the default build (all unset) and a sample build (`TRUEBEX_CATALOGUE_FILE=scripts/fixtures/catalogue-sample.json`, `TRUEBEX_ANALYTICS_TOKEN`, `TRUEBEX_GOOGLE_SITE_VERIFICATION`, `TRUEBEX_BING_SITE_VERIFICATION`, one LinkedIn URL) → 20/20 each; pages looked at in headless Edge (pricing desktop and 500 px, Arabic RTL, daylight, marketplace, roadmap, changelog, the Growth panel against a local API with seeded rows).
* **Deviations from Design and why:**
  * The five feature pages are one route, `src/app/features/[slug]/page.tsx` with `generateStaticParams` and `dynamicParams = false` (five static HTML pages, as specified), not five folders: one template, copy in `FEATURE_PAGES`.
  * PF1 is not merged, so this branch adds what PF13 reads from it, in PF1's shapes: `server/app/catalogue.json` (PF1's schema, §6.3 placeholder matrix, plus PF2's `prices: []`, `per_seat`, `min_seats`, top-level `founding: null`; API quotas equal `plans.py`, guarded by a test), `src/content/releases.json` (an empty 5.13 feed), the `/changelog/` page (release entries rendered from the feed with the contract's notes subset, then the history; a history entry whose id equals a release version gives way to it), `users.is_admin` + `require_admin` (PF1's names) and `UserOut.is_admin`. The admin route lives in `server/app/routers/growth.py` (prefix `/admin`) so it does not collide with PF1's `routers/admin.py`. `python -m app.admin_cli <email> [--off]` sets the flag.
  * PF1 has no download log, so `download_events` (when, version, platform, channel; no person, no IP) and `app.growth.service.record_download()` are added here; PF1's 5.14 calls it (carry-over). Trials are `subscriptions` with `provider="trial"`, checkouts `payments.created_at`, paid `payments.paid_at`.
  * The beacon is rendered by the public `Footer` (every public page renders it, no signed-in page does) instead of the root layout with a pathname gate: with a gate the token would still sit in the dashboard's RSC payload. `next/script` `afterInteractive`, `data-cf-beacon` with `spa: false`, so a client-side hop into the dashboard is not counted.
  * The download button points at `/download/` only when `src/app/download/page.tsx` is in the build (`src/lib/site-routes.ts`); until PF1 merges it reads "Request a demo" → `/#contact`, so no link 404s.
  * A paid tier without a price shows "Price at launch" and its button is "Start free" → `/signup/` (a checkout link for a tier that cannot be bought leads nowhere); with a price it is "Choose <tier>" → `/dashboard/billing/?tier=…&interval=…&currency=…`. Free says "Free" and Enterprise "Custom" / "Talk to us" → `/#contact`.
  * Currency: the static HTML shows GBP; the client picks USD / EUR / GBP from the browser's region (`useSyncExternalStore`, no hydration mismatch) and remembers an explicit choice in `localStorage`. Annual shows the per-month equivalent plus the yearly total; monthly shows the month plus its 12× year; both change when the toggle flips.
  * Build-time overrides for local testing (never needed for a release): `TRUEBEX_CATALOGUE_FILE`, `TRUEBEX_ANALYTICS_TOKEN`, `TRUEBEX_GOOGLE_SITE_VERIFICATION`, `TRUEBEX_BING_SITE_VERIFICATION` (`src/lib/catalogue-data.ts`, `src/lib/site-config.ts`); the committed values stay in `constants.ts`.
  * Roadmap items carry `theme` (themes listed in the file) and an optional `home` flag (the eight shown on the home page); `sync-roadmap.mjs` finds columns by header name, fails on a plan id missing from both trackers, and has `--check`. 23 items map to the app's and platform's plan ids; all are "planned" today.
  * The navbar is locale-aware (Arabic labels on `/ar/`), the logo lockup is forced left to right so it never mirrors, and the Arabic font (Noto Sans Arabic through `next/font`, `src/app/ar/layout.tsx`) also styles the navbar through an `html[lang="ar"]` rule; the build check confirms the font's CSS is linked from `/ar/` and not from `/`.
  * `/developers/` reads its plan allowances from the catalogue (Free, Pro, Studio, Team, Enterprise). The dashboard and API error texts still say Starter / Professional until PF1 renames plans in `plans.py`.
  * `UsageChart` gained `label` / `unit` props for the Growth panel (stat tiles for the totals, one metric at a time as daily bars with a table view).
  * The placeholder check reads visible text, meta descriptions, alt / title / aria-label, JSON-LD and the feed, not HTML attribute names (the demo form's `placeholder=` attributes are legitimate).
* **GD6 / GD7 inputs adopted:** none; neither guide is written. Prices are empty (every paid tier says "Price at launch", the JSON-LD offers are Free only), the founding block is hidden, `SOCIAL`, `ANALYTICS` and `VERIFICATION` are empty (no Follow column, no `sameAs`, no beacon, no tags), Studio and Team carry the same placeholder matrix as Pro (their cards differ only in roadmap lines and seats), and the Arabic copy (`AR_HOME`) awaits a native speaker's review.
* **Owner steps done:** none yet; all are after a deploy. (1) Cloudflare dashboard → Web Analytics → add truebex.com → copy the token into `ANALYTICS.cloudflareToken`. (2) Search Console: domain property by DNS TXT at Cloudflare, plus the HTML tag token in `VERIFICATION.google`; submit `https://truebex.com/sitemap.xml`. (3) Bing Webmaster Tools: import from Search Console or put the tag in `VERIFICATION.bing`. (4) After each deploy: `npm run indexnow -- --sitemap` (key file `public/9453d000061b1c7726749ca61a17a0db.txt`). (5) Social URLs into `SOCIAL`. (6) Before a deploy: `npm run sync:roadmap -- <app README> <platform README>`.
* **Contract:** none (no contract endpoint implemented); nothing to record in the Unreal repo's `contracts/`.
* **Carry-over → which feature:** PF1: call `record_download()` from `GET /releases/{version}/download`; at merge keep one `catalogue.json`, one `/changelog/` page (PF1's release rendering + this history, ItemList JSON-LD, feed and anchors) and one `require_admin` / `is_admin`; make `plans.py` read the catalogue and rename Starter / Professional. PF2: fill `prices` and `founding` in the catalogue; `GET /billing/plans` returns `founding.{enabled,total,remaining}` (the banner already reads them) and the billing page honours `?tier=&interval=&currency=`. GD7: the matrix, prices and founding numbers, and what sets Studio apart from Pro (`PRICING.tiers` copy). GD6: social handles, the Arabic review, the clean captures (drop `<page>.png` into `Brand/Truebex/captures/` and run `py -3.12 scripts/make_web_assets.py --features`, then update that page's alt and caption).
