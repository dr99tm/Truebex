# PF13a — Sell on Truebex page leading to the supplier sign-up (launch priority 2)

**Needs merged:** PF8, PF13 (both on `master` at 842768e). **Unblocks:** GD1's onboarding has a public page to send suppliers to. **Contract:** none (no endpoint; the page links to PF8's `/supplier/signup/`).

## Status

**Built 2026-10-11** (Autopilot T38, `ap/t38-pf13a-sell-on-truebex-page-leadi`): `/suppliers/`, a public, indexable page that leads to the supplier portal's sign-up; see As-built. Before this task (master 842768e, verified with Grep on 2026-10-11):

| Area | Where (master 842768e) | Before |
|---|---|---|
| Supplier button on the marketplace page | `src/lib/constants.ts:1038-1041` (`FEATURE_PAGES` marketplace `supplierCta`), rendered by `src/components/features/FeaturePage.tsx:31-35` | "Register supplier interest" → `mailto:${SITE.email}?subject=Supplier%20interest`, a personal webmail address (GD5) |
| The portal's sign-up | `src/app/supplier/signup/page.tsx`, `src/components/supplier/SignupForm.tsx` | built by PF8; noindex like every portal page (`src/app/supplier/layout.tsx:6-9`), out of the sitemap, `Disallow: /supplier/` in `src/app/robots.ts:8` |
| A public page for suppliers | none | PF8's As-built carry-over to PF13: "a public Sell on Truebex page linking `/supplier/signup/`"; PF13 landed before PF8, so no such page existed |

## Goal

A company that sells furniture, lighting, kitchens, bathrooms or finishes finds a public page on truebex.com that says, in plain words, what the supplier portal gives it today, how the first suppliers are onboarded, and what is still on the roadmap, and that has one button: apply as a supplier. The page can be found in search and shared; the portal behind it stays private.

## Read first

* `docs/roadmap/40/00-contract.md` P.2, P.3 (the per-page SEO checklist), P.4.
* As-built of `PF8-supplier-portal-and-app.md` (the portal as it ships; the carry-over to PF13) and `PF13-website-pricing-features-roadmap-arabic-changelog-analytics.md` (the feature pages, `seo.ts`, the build checks).
* `.claude/skills/truebex-seo/SKILL.md`, `.claude/skills/truebex-brand-voice/SKILL.md`.
* `src/app/supplier/signup/`, `src/components/supplier/SignupForm.tsx`.
* `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\guides\GD1-supplier-onboarding-guide.md` (read-only): the first ten suppliers are signed by hand (§5), every product is reviewed (PF8 carry-over), card payments stay off until GD5 signs off the marketplace terms (the table "What is true today"; PF7 `MARKET_PAYMENTS_ENABLED`), every fee waits for GD7 (§7 slide 10).

## Scope

**In:**

1. A public, indexable page at `/suppliers/` (trailing slash) in the site's style, saying:
   * what suppliers get, in the present tense: the catalogue (variants, dimensions, materials, pictures, 3D files checked on upload), prices and stock by region, spreadsheet and feed import with a dry run, the leads, quotes and orders inbox, the numbers per product and region, team roles and supplier API keys (PF8's portal as it ships);
   * how onboarding works today (GD1): apply with the company details and one document; the first suppliers are reviewed by hand; prepare the catalogue meanwhile; every product is reviewed before it is listed;
   * what is still on the roadmap, labelled "On the roadmap", in the future tense, with no dates and no fees: the catalogue inside the app, the live cost, and card payments for orders (off until the marketplace terms are signed off; until then every supplier is quote-only).
   One call to action, "Apply as a supplier" → `/supplier/signup/`, shown in the header and again at the end of the page.
2. All copy in `src/lib/constants.ts` (`SELL_PAGE`, a new export at the end of the file), written with `truebex-brand-voice`.
3. The per-page SEO checklist: metadata (title ≤ 60, description 140–160 with the main phrase), one h1, the canonical `https://truebex.com/suppliers/`, server-rendered text, a sitemap entry, and JSON-LD (WebPage, BreadcrumbList, FAQPage) built from the same copy.
4. The marketplace feature page's supplier button links to `/suppliers/` (no `mailto:` left in a supplier call to action); a footer link "Sell on Truebex" in the Resources column. The portal stays noindex and disallowed.
5. Build checks first: `server/tests/test_site_pf13a.py`.

**Out (and where it goes):**

* Arabic: out of scope. `AR_HOME` covers only the Arabic home page and the site has no Arabic feature pages; `/suppliers/` is English only, has no `hreflang` pair, and the Arabic footer (`AR_HOME.footer.links`) gets no link. An Arabic supplier page waits for the Arabic pages after LO1 (`truebex-seo` content engine, item 4) and a native speaker's review (GD6).
* A per-page OG image: the SEO skill asks for none on new pages; the page uses the shared card (`OG_IMAGE`, `public/images/og-image.jpg`). No `scripts/make_web_assets.py` run.
* Fees, listing plans and commission on the page → GD7 (not ticked). Card payments switched on → GD5 sign-off, then PF7's `MARKET_PAYMENTS_ENABLED`.
* Naming suppliers on the page → only with a supplier's written consent (GD1 §8.3), after go-live.
* The IndexNow ping and Search Console's "Request indexing" → the owner, after the deploy.

## Design

**API:** none. **Data:** none. **Jobs / workers:** none.

**UI:**

* Route `src/app/suppliers/page.tsx` (server component): `pageMetadata({ title, description, path: "/suppliers/", absoluteTitle: true })`, and one `<script type="application/ld+json">` with `webPageLd` (name = the h1, description = the meta description), `breadcrumbLd` (Truebex → Sell on Truebex) and `faqLd(SELL_PAGE.faq)`.
* Component `src/components/suppliers/SellPage.tsx` (`suppliers`, so it is not mistaken for the portal's `src/components/supplier/`): breadcrumb, header (eyebrow, h1, intro, the button, a note that the application is linked to a Truebex account), then `<section data-sell="offer|onboarding|roadmap|faq|apply">`. Roadmap cards carry `data-roadmap="true"` and the amber "On the roadmap" label (`text-warn`), like `/roadmap/`. The FAQ renders through `FaqList` so the visible questions and the FAQPage match. No image: the brand's one clean capture belongs to daylight, and the portal has no clean capture yet.
* The call to action is `<a data-cta="supplier-signup" href="/supplier/signup/">Apply as a supplier</a>`, a plain link (the portal is another layout). The marketplace page's supplier button gains `data-cta="supplier"`.
* Copy keys (`SELL_PAGE`): `path`, `nav`, `title`, `description`, `eyebrow`, `h1`, `intro`, `cta`, `ctaNote`, `offerTitle`, `offer[] {id, title, body}`, `stepsTitle`, `steps[]`, `roadmapTitle`, `roadmapLabel`, `roadmapIntro`, `roadmap[]`, `roadmapLink`, `faqTitle`, `faq[]`, `closingTitle`, `closingBody`. Changed: `FEATURE_PAGES` marketplace `supplierCta` ("Sell on Truebex" → `/suppliers/`), its "For suppliers" section and its FAQ "Can my company list products?" (the portal ships, so they say so); `FOOTER.links` + "Sell on Truebex".
* Sitemap: `/suppliers/`, monthly, priority 0.6 (like the roadmap feature page).
* Robots: unchanged. `Disallow: /supplier/` is a prefix rule, and `/suppliers/` does not start with `/supplier/`, so the new page is crawlable while the portal is not (a build check asserts both).

**Security and privacy:** the page collects nothing and calls no API. Removing the `mailto:` takes the owner's personal address out of the supplier call to action (it remains in the footer's contact column, a site-wide choice outside this task).

## Deliverables

- [x] `src/app/suppliers/page.tsx`, `src/components/suppliers/SellPage.tsx`
- [x] `SELL_PAGE` in `src/lib/constants.ts`; the marketplace `supplierCta`, section and FAQ; the footer link
- [x] `src/app/sitemap.ts` entry; `src/components/features/FeaturePage.tsx` `data-cta="supplier"`
- [x] `server/tests/test_site_pf13a.py` (6 checks)
- [x] the `truebex-seo` keyword map row and content-engine note; a README section; this doc; the tracker row

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_site_pf13a_page_built` | build check | `out/suppliers/index.html`: one h1 ("Sell … on Truebex"); a unique title ≤ 60 with "Sell on Truebex"; description 140–160 with the main phrase; canonical, `og:url` = `https://truebex.com/suppliers/`; OG and Twitter cards; each section's h2, h3s and text in the HTML; H2s ≤ 6 words; WebPage (url, name = h1, description = meta), BreadcrumbList (`/` → `/suppliers/`, matching the visible trail), FAQPage = the visible questions |
| `test_site_pf13a_sitemap_and_robots` | build check | `/suppliers/` once in `sitemap.xml`, no `/supplier/` URL there; the page is not noindex; no `Disallow` rule is a prefix of `/suppliers/` while `/supplier/` stays disallowed; the portal's sign-up stays noindex |
| `test_site_pf13a_links_to_supplier_signup` | build check | every `data-cta` in `<main>` is `supplier-signup` → `/supplier/signup/` with one label; no `mailto:`, `/signup/`, `/download/` or demo link in `<main>`; the sign-up page is in the build |
| `test_site_pf13a_marketplace_button_and_footer` | build check | the marketplace page's two supplier buttons read "Sell on Truebex" and link to `/suppliers/` (no `mailto:`); the footer of `/`, `/pricing/`, `/features/marketplace/`, `/roadmap/` and `/suppliers/` links to `/suppliers/` |
| `test_site_pf13a_supplier_cta_has_no_mailto` | pytest (no build) | every `supplierCta` in `constants.ts` names `"/suppliers/"` and no `mailto:` |
| `test_site_pf13a_brand_words` | build check | the page's copy (main, meta description, JSON-LD) names no other product or engine (PF13's list), has no placeholder, internal plan or guide id, hype word or "!", date, price, percentage, fee, commission or listing plan; every roadmap card says "On the roadmap" in the future tense and one is card payments ("quote-only"); the offer is in the present tense and covers catalogue, region, spreadsheet, feed, request for quote and order; onboarding says "by hand" and "every product" |

PF13's site-wide checks also cover the page: `test_site_pf13_no_competitor_names`, `test_site_pf13_no_placeholder_text`, `test_site_pf13_sitemap_complete` (trailing slashes) and `test_site_pf13_marketplace_page_future_tense` (its supplier link).

## Human test

Set-up, in the worktree (two terminals):

* A: `server\run.bat` (the API on `http://127.0.0.1:8000`; the first run copies `server\.env` from `.env.example`). In `server\.env` add `,http://127.0.0.1:3138` to the end of `CORS_ORIGINS`, then stop (Ctrl+C) and start `server\run.bat` again.
* B: `$env:NEXT_PUBLIC_AUTH_URL='http://127.0.0.1:8000'; npm run build`, then `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1`. It prints `serving … on http://127.0.0.1:3138/`. If it prints another port, use that port below and in `CORS_ORIGINS`.

1. Open `http://127.0.0.1:3138/suppliers/` → tab "Sell on Truebex · Supplier portal for building products"; heading "Sell your products on Truebex"; one blue "Apply as a supplier" button; then "What you get" (6 cards), "How onboarding works" (4 numbered steps, including "We review it by hand" and "Every product is reviewed"), "On the roadmap" (3 cards with an amber "On the roadmap" label; the last one, "Orders paid on Truebex", says every supplier is quote-only until card payments open), "Questions" (5, each opens and closes), and a closing panel with the same button. Nowhere a price, fee, percentage or date.
2. Make the window narrow (or DevTools → 375 px wide) → one column, no sideways scrolling.
3. Footer → Resources → "Sell on Truebex" is listed. Open `http://127.0.0.1:3138/` → its footer has the same link.
4. Open `http://127.0.0.1:3138/features/marketplace/` → the third button under the heading reads "Sell on Truebex" (and again in the panel near the end). Click it → you land on `/suppliers/`; no mail app opens.
5. On `/suppliers/`, signed out, click "Apply as a supplier" → `/supplier/signup/` ("Sell your products in Truebex") with "Create a Truebex account or sign in first…" and the buttons "Create an account" and "Sign in".
6. Click "Create an account", sign up with any e-mail and an 8+ character password → you come back to the supplier sign-up, now showing the three steps "1. Company · 2. Regions and contact · 3. Document".
7. Optional (PF8's flow): fill the three steps with any small PDF → "Under review"; terminal A prints the confirmation e-mail.
8. Optional: View source (Ctrl+U) on `/suppliers/` → `<link rel="canonical" href="https://truebex.com/suppliers/"/>`, no `noindex`, one JSON-LD script with WebPage, BreadcrumbList and FAQPage; `http://127.0.0.1:3138/sitemap.xml` lists `https://truebex.com/suppliers/`.

## Risks / traps

* `robots.txt` rules are prefixes: a future `Disallow: /supplier` (without the slash) would also hide `/suppliers/`. The build check fails if any rule covers the page.
* `out/` from the verify gate is built against `.env.local`'s production API: steps 5–7 need the rebuild with `NEXT_PUBLIC_AUTH_URL` above, and the served origin in `CORS_ORIGINS`.
* A screenshot at 375 px with `msedge --headless --window-size=375,…` clips the right edge, because headless Edge keeps a wider minimum window. Use DevTools device mode, or CDP `Emulation.setDeviceMetricsOverride`, to judge phone layout.
* When the in-app catalogue (MK1) or card payments ship, move that roadmap card into "What you get" in the present tense, and update the marketplace page with it (`truebex-brand-voice`: a row is shipped when ticked and merged to `main`).
* `SITE.email` is no longer used by any call to action in `FEATURE_PAGES`; the footer still shows it.

## As-built

* **Date, branch, commits:** 2026-10-11, `ap/t38-pf13a-sell-on-truebex-page-leadi` from `master` 842768e (Claude Autopilot T38): `fd1e5e3` the page, copy, sitemap, footer, marketplace button and the build checks; `abb2d1d` this documentation (the doc, the tracker row, the README section and the `truebex-seo` keyword row); `24a9671` a test fix outside the feature (below).
* **Counts:** pytest in the verify gate 544 → 550 passed (6 new in `test_site_pf13a.py`), 5 skipped (unchanged). `out/`: 66 → 67 `index.html` pages; sitemap 22 → 23 URLs. Lint, build and `scripts/autopilot-verify.ps1` green.
* **Tests as named:** every row of the Tests table exists under its name; the build checks were written before the page and ran (not skipped) on the built `out/`.
* **Self-tests:** headless Edge over CDP on the served `out/`: at 375 px, `scrollWidth` = `clientWidth` = 375 on `/suppliers/` (no element wider than the screen), full-page screenshots at 1280 px and 375 px; the marketplace page's "Sell on Truebex" button → `/suppliers/`; "Apply as a supplier" → `/supplier/signup/`, signed out (the "Create an account / Sign in" panel) and signed in (the three-step form) against a throwaway local API (port 8038, scratch SQLite DB, `CORS_ORIGINS` = the served origin); no page errors.
* **Deviations from the task text and why:**
  * The one call to action appears twice, in the header and in the closing panel: the same button, label and link, as the feature pages do. The page has no other action (no download, account or demo button), and a build check enforces that.
  * The marketplace page's "For suppliers" section and its FAQ "Can my company list products?" now say that suppliers can apply and prepare their catalogue in the portal (present tense), because the portal ships; the rest of that page stays in the future tense. The button's label changed from "Register supplier interest" to "Sell on Truebex", the page it now opens.
  * The FAQ has no "What does it cost?" or "How long does review take?": they would need a fee or a date, which the task rules out.
  * The page says the first suppliers are "onboarded one by one" and reviewed "by hand" (GD1 §5: scoring, intro call, sample check, signed agreement), without promising the intro call or the sample check to a supplier who applies through the page.
* **A flaky gate test fixed on the way (not PF13a's code):** `test_pf12_webhooks.py::test_webhooks_market_order_and_feed_events` asserted that an order's two `market.order.updated` deliveries arrive as `submitted` then `cancelled`. Since 6c7ecb6 deliveries go out in parallel (`delivery.PARALLEL`) and the event timestamps tie at whole seconds, so under the full suite they arrived reversed once (the test passed 8/8 alone). It now asserts both states, once each, for that order; delivery order was never promised to receivers.
* **Arabic:** out of scope, as above; recorded for the Arabic pages after LO1.
* **OG image:** none added; the shared card serves the page (`truebex-seo` asks for no per-page image).
* **Contract:** none; nothing to record in the Unreal repo's `contracts/`.
* **Owner at deploy:** after the deploy, `npm run indexnow -- --sitemap` (the sitemap now lists `/suppliers/`), and in Search Console, URL Inspection → Request indexing for `https://truebex.com/suppliers/`. Live check: `https://truebex.com/suppliers/` returns 200 and the marketplace page's "Sell on Truebex" button opens it.
* **Carry-over → which feature:** MK1 (catalogue in the app), MK3 (live cost), PF7 / GD5 (card payments): when each ships, move its card from "On the roadmap" to "What you get" and drop "quote-only". GD7: when fees are set and ticked, decide whether the page names them. GD1: when auto-approval for trusted suppliers lands, update "We review it by hand". GD6 / LO1: an Arabic supplier page with its `hreflang` pair.
