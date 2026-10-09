# PF8 — Supplier portal and app (launch priority 1)

**Needs merged:** PF7. **Unblocks:** none by Needs; GD1's onboarding of the first ten suppliers runs on it. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\marketplace-api.md` (v1.0.0; this feature implements the feeds 5.11–5.13, §11).

## Status

No supplier-facing pages, feeds or e-mail exist (`00-contract.md` P.1). What this builds on, verified with Grep on 2026-10-09:

| Area | Where | Today |
|---|---|---|
| API keys | `server/app/models.py:46-70` (`ApiKey`, no scope or owner organisation), `server/app/routers/keys.py:33-58` (create, shown once) | feeds authenticate with a key (contract §4); this feature binds keys to a supplier |
| Dashboard building blocks | `src/components/dashboard/DashboardShell.tsx:131-176` (`PageHeader`, `Panel`, `ErrorNote`), `:104-123` (mobile tabs), `src/components/dashboard/useApiData.ts:7` | the portal shell reuses them |
| Charts | `src/components/dashboard/UsageChart.tsx:37` | supplier analytics per day |
| From PF7 (Needs) | suppliers, members and roles, products, variants, `supplier_regions`, `variant_prices`, `variant_availability`, the importer, `feed_runs`, orders and leads, commissions, listing plans | the backend this portal drives |
| E-mail | none in the code | `server/app/mail` per PF14 Plumbing; created here if no earlier task did |

What the owner meant: app-side `00-understanding.md` §9 ("a web app for the companies that sell products to manage catalogue, stock, regional prices, leads and orders, with spreadsheet and feed import").

## Goal

A company that sells furniture, finishes or fittings signs up, gets verified, and runs its Truebex catalogue itself from a desk or a phone: products with variants, pictures and placeable geometry; stock and prices per region; a spreadsheet or a feed that keeps all of it current; a single inbox for quote requests and orders; numbers on what designers look at and buy; and its listing plan and invoices. Human test seed: "as a supplier, upload a spreadsheet of products with two regional price lists and see them in the app's catalogue".

## Read first

* **`contracts/marketplace-api.md` v1.0.0** — §4 (supplier systems use a member's API key), §5.11–5.13 (the feeds this feature implements), §6.1–6.3 (the product, categories and price shapes the portal edits), §6.4 (the feed columns the spreadsheet template mirrors), §7 errors, §9 fixtures (`feed-two-regions.csv`, `feed-two-regions.json`, `feed-report.json`), §10 the feed tests.
* PF7 (schemas, importer, admin approval, orders); PF2 (the billing interface for listing plans); PF14 Plumbing (`mail`, `tasks`, `storage`, `uploads`).
* `guides/GD1-*.md` (supplier onboarding, the spreadsheet template's help text) and `guides/GD7-*.md` (listing plans) are not written yet: placeholders.
* Skills: `truebex-brand-voice` (e-mails and portal copy).

## Scope

**In:**
1. Sign-up and verification: a supplier application (legal name, country, company number, VAT id, website, address, regions sold in, a contact) from a new or existing account, a company document upload (PDF ≤ 10 MB), state `applied` until an admin verifies it (PF7's admin), e-mail on the decision; unverified suppliers can prepare products but not publish.
2. Catalogue management: products (name, kind, category from the taxonomy tree, description, images), variants (options, `dims_mm`, materials), BIM uploads (`tbxa`, `glb`, `gltf`, `obj`, `fbx` ≤ 100 MB, checked on upload), submit for review, hide, withdraw, mark discontinued.
3. Stock and prices by region: a grid per region (price, tax included, tax rate, delivery fee and days, stock, state, lead time), bulk edits, the regions the supplier serves with their currency.
4. Bulk import from spreadsheets and feeds: the spreadsheet template (XLSX) and the contract's CSV and JSON; upload with a dry run (what would be created, updated, unchanged, rejected) then apply; a registered feed URL pulled daily at 02:00 UTC; the feed endpoints 5.11–5.13 for supplier systems; every run's report.
5. Leads and orders inbox: requests for quote answered with quoted prices and a message; orders accepted or rejected, then shipped (carrier and reference) and delivered; buyer contact shown only for the supplier's own leads and orders.
6. Analytics: per product and region, per day — search impressions, product views, geometry downloads (placements), quote requests, orders and order value; counts only, no buyer identities.
7. Listing plan and billing: choose a listing plan (`from GD7`), pay it through PF2's interface (Stripe, business customer with VAT id), see commission statements and invoices, and connect payouts for orders (Stripe Connect onboarding link, PF7).
8. Team: members with roles (`owner`, `catalogue`, `orders`, `viewer`) by invitation, and supplier-scoped API keys for feeds.
9. A mobile-friendly layout: every page usable at 375 px wide; the inbox, the price grid and stock edits designed for the phone first.
10. E-mail notifications: application received and decided, product approved or rejected, new quote request, new order, order cancelled by the buyer, a feed run with rejected rows, a failed feed pull.
11. Tests: the contract's feed tests, a pytest per endpoint (happy path, auth failure, validation failure), the template round trip.

**Out (and where it goes):**
* Catalogue reads, search, orders' checkout, commissions' computation, admin approval → PF7.
* A native supplier app for the stores → not planned (the responsive web app is the app; installable later with PF9's PWA work if suppliers ask).
* Supplier contracts and onboarding calls → GD1, GD5; listing-plan prices → GD7.
* A public "Sell on Truebex" page → PF13 (the marketplace feature page).

## Design

### API

Feed endpoints follow the contract; portal endpoints (session, supplier role checks) live under `/supplier` (`server/app/routers/supplier.py`, service `server/app/supplier/`).

| Endpoint | Auth (role) | Behaviour |
|---|---|---|
| `POST /market/feeds` (5.11) | supplier key (`owner`, `catalogue`) | multipart `file` CSV or JSON ≤ 50 MB and 100 000 rows, `format`, `mode` → 202 `{feed_id, state: "queued"}`; header or JSON shape wrong → 422 `feed_invalid` |
| `PUT /market/feeds/source` (5.12) | supplier key | `{url, format, mode}`, https only → 200 the source |
| `GET /market/feeds/{feed_id}` (5.13) | supplier key | the report: counts and up to 200 row errors |
| `POST /supplier/applications` | session | the application; 409 when the account already applied; 422 field rules |
| `POST /supplier/documents` | session (`owner`) | one multipart PDF ≤ 10 MB (well inside Cloudflare's body limit, so no resumable upload and no new upload purpose), stored at `market/suppliers/{supplier_id}/docs/{sha256}.pdf`, readable by admins only |
| `GET/POST/PATCH /supplier/products`, `…/{id}/variants`, `…/{id}/submit` | session (`catalogue`) | edits only `draft`, `rejected` or the supplier's own approved products (a change to an approved product goes back to review when name, category, images or geometry change) |
| `POST /supplier/geometry` | session (`catalogue`) | a geometry upload: format by magic bytes, size ≤ 100 MB, for `glb` the triangle count ≤ 500 000 and the bounding box within 5 % of `dims_mm` (else a warning) |
| `GET/PUT /supplier/prices?region=` | session (`catalogue`) | the grid; a PUT writes rows through the same validation as the importer |
| `POST /supplier/imports` · `POST /supplier/imports/{id}/apply` | session (`catalogue`) | upload XLSX, CSV or JSON → dry-run report → apply runs PF7's importer and records a `feed_runs` row |
| `GET /supplier/imports/template.xlsx` | session | the template with the supplier's categories and regions filled into the lists |
| `GET /supplier/inbox` · `POST /supplier/inbox/{order_id}/quote` · `/accept` · `/reject` · `/ship` · `/deliver` | session (`orders`) | the supplier's part of each lead and order; state changes per contract §5.7–5.10 |
| `GET /supplier/analytics?from=&to=&region=` | session (any role) | daily counts per product |
| `GET/POST /supplier/listing` · `GET /supplier/statements` · `POST /supplier/payouts/connect` | session (`owner`) | listing plan checkout through PF2, statements with invoice PDFs, a Stripe Connect onboarding link |
| `GET/POST/DELETE /supplier/members`, `POST /supplier/keys` | session (`owner`) | invitations by e-mail with a role; keys created here carry `supplier_id` |

### Spreadsheet and feed import format

The template is the contract's §6.4 columns in one sheet named `catalogue`, one row per variant and region, plus `help` (every column with its rule and an example), `categories` and `regions` (the lists the drop-downs use). CSV and JSON feeds carry the same fields (§6.4); XLSX is converted to those rows before the importer runs.

| Column | Required | Example | Rule (contract §6.4, plus the portal's checks) |
|---|---|---|---|
| `sku`, `variant_id`, `name` | yes | `SOFA-OSLO-3`, `oat-linen`, `Oslo 3-seater sofa` | ≤ 64, ≤ 64, ≤ 120; stable across uploads; `default` for a single variant |
| `category`, `kind` | yes, no | `furniture/seating/sofas`, `object` | a path of the `categories` sheet; `object` when empty |
| `option_size`, `option_colour`, `option_finish`, `materials` | no | `3-seater`, `Oat`, `Linen`, `linen;oak` | ≤ 40 each; `;` separates materials |
| `width_mm`, `height_mm`, `depth_mm` | for objects | `2100`, `950`, `850` | whole millimetres, 1–100 000 (X width, Y height, Z depth, §6.1) |
| `geometry_url`, `image_urls` | for objects; yes | `https://…/oslo.glb`, `https://…/oslo-1.jpg;https://…/oslo-2.jpg` | https; a §6.1 format; images JPEG or PNG ≥ 512 px, the first is the thumbnail |
| `region`, `currency` | yes | `GB`, `GBP` | a row of the `regions` sheet; the region's currency |
| `price`, `price_includes_tax`, `tax_rate_percent` | yes, yes, no | `1299.00`, `true`, `20` | text in major units with at most the currency's exponent of decimals; spreadsheet numbers are read through `Decimal(str(cell))` and refused when they carry more |
| `delivery_fee`, `delivery_days_min`, `delivery_days_max` | no | `49.00`, `7`, `14` | defaults from the supplier's region settings |
| `stock`, `lead_time_days`, `status` | no | `12`, ``, `active` | integers; `active`, `discontinued`, `hidden` |

Row error codes in the report (`errors[].code`): `missing_required`, `too_long`, `unknown_category`, `unknown_kind`, `unknown_region`, `currency_mismatch`, `bad_price`, `bad_bool`, `bad_integer`, `bad_dims`, `bad_url`, `bad_geometry_format`, `geometry_fetch_failed`, `image_fetch_failed`, `image_too_small`, `duplicate_row`, `bad_status`. **Decision:** one row per variant and region, as the contract's CSV. Rejected: a wide sheet with a column per region's price (tax and delivery per region would need a column each, and every new region would change the template).

### Data

| Table / column | Fields | Notes |
|---|---|---|
| `api_keys.supplier_id` | `VARCHAR(32)` via `_ADDED_COLUMNS` | nullable; a key without it is accepted on 5.11–5.13 only when its owner belongs to exactly one supplier with `owner` or `catalogue` |
| `supplier_applications` | `supplier_id`, `submitted_by`, `fields` JSON, `document_keys`, `state`, `decided_by`, `decided_at`, `reason` | the verification trail |
| `feed_sources` | `supplier_id`, `url`, `format`, `mode`, `last_pull_at`, `last_status`, `etag` | pulled daily |
| `supplier_imports` | `import_id`, `supplier_id`, `source_key`, `format`, `mode`, `dry_run` JSON, `feed_id`, `created_by`, `created_at` | a dry run kept 24 h |
| `market_events_daily` | `product_id`, `region`, `day`, `impressions`, `views`, `geometry_downloads`, `quotes`, `orders`, `order_value` | counts written by PF7's endpoints through one `count_event()` call |
| `supplier_member_invites` | `supplier_id`, `email`, `role`, `token_hash`, `expires_at`, `accepted_at` | 7 days |
| `listing_subscriptions` | `supplier_id`, `plan`, `provider`, `provider_subscription_id`, `status`, `current_period_end` | PF2's interface keeps it in step |

### UI

| Page (all noindex, under `src/app/supplier/`) | What it shows |
|---|---|
| `signup/` | the application in three steps (company, regions and contact, document), then "Under review" |
| `page.tsx` (overview) | verification state, open requests and orders, last import, this week's views and quotes |
| `catalogue/`, `catalogue/product/?id=` | products with state badges; the editor with images, variants, geometry upload and a size check against `dims_mm`; Submit for review |
| `prices/?region=` | the per-region grid; on phones each variant is a card with price, stock and state |
| `imports/` | upload, the dry-run table (created, updated, unchanged, rejected with row and column), Apply; the feed URL; past runs with their reports; Download template |
| `inbox/` | requests and orders as a list with filters; a request opens a quote form; an order shows Accept, Reject, Shipped (carrier, reference), Delivered |
| `analytics/` | per-day chart (`UsageChart`) and a product table for a date range and region |
| `billing/`, `team/` | listing plan, statements, payouts connection; members, invitations, supplier keys (shown once) |

`src/components/supplier/SupplierShell.tsx` mirrors `DashboardShell` (auth guard, side nav on desktop, tabs on phones) with the supplier switcher for people in more than one supplier. Copy that is public (the sign-up page's headings and help) lives in `src/lib/constants.ts`.

### Jobs / workers

| Job | Every | Does |
|---|---|---|
| `market.feeds.run` | 30 s | takes queued feed runs (5.11, portal applies) and runs PF7's importer; one run per supplier at a time |
| `market.feeds.pull` | daily, 02:00 UTC | fetches each registered URL (ETag, 50 MB cap, 60 s timeout) and queues a run |
| `supplier.imports.purge` | 24 h | drops dry runs older than 24 h |
| `supplier.notify` | on events | the e-mails of Scope item 10 through `server/app/mail` (PF14 Plumbing; the `console` adapter on the home PC) |

### Security and privacy

* Role checks on every portal route; a member of one supplier never reads another's data; supplier keys are bound to their supplier.
* Remote fetches (feed URLs, image and geometry URLs in rows): https only, private and loopback addresses refused, size and time capped — the server-side request forgery guard.
* Uploaded files are data: geometry stored by hash and served as attachments; images re-encoded; PDFs never rendered on the server.
* Buyer details appear only on that supplier's leads and orders; analytics are counts without people.

## Deliverables

- [ ] `server/app/supplier/` (`applications.py`, `catalogue.py`, `geometry_check.py`, `prices.py`, `imports.py` with the XLSX reader, `template.py`, `inbox.py`, `analytics.py`, `listing.py`, `members.py`), `server/app/routers/supplier.py`, the feed routes 5.11–5.13
- [ ] `server/app/mail/` (`console`, templates) if no earlier task created it (PF14 Plumbing); templates for Scope item 10
- [ ] `_ADDED_COLUMNS` (`api_keys.supplier_id`), models, settings; `openpyxl` pinned
- [ ] `src/app/supplier/` pages, `src/components/supplier/SupplierShell.tsx`, `src/lib/supplier.ts`, copy in `constants.ts`
- [ ] contract §11 rows for 5.11–5.13 recorded in As-built

## Tests

The first four names are the contract's §10 feed tests.

| Name | Kind | Asserts |
|---|---|---|
| `test_feed_csv_two_regions` | pytest | `feed-two-regions.csv` imports as `feed-report.json` says: GB and AE prices on each variant |
| `test_feed_rejects_unknown_category` | pytest | the bad rows land in `errors` with `unknown_category`; good rows import |
| `test_feed_requires_supplier_key` | pytest | 401 without a key; 403 `not_supplier` for a key of a non-member or a `viewer` |
| `test_contract_header_and_error_envelope` | pytest | header echoed on 5.11–5.13; MAJOR 2 → 400; envelope with `code` and `request_id` |
| `test_feed_json_matches_csv` | pytest | `feed-two-regions.json` gives the same rows as the CSV |
| `test_feed_limits_and_shape` | pytest | 413 over 50 MB or 100 000 rows; 422 `feed_invalid` for a wrong header |
| `test_feed_source_daily_pull` | pytest | a registered URL (mocked HTTP) queues a run at 02:00 UTC; `http://` and private addresses refused |
| `test_supplier_application_flow` | pytest | apply → `applied`; admin verify → `verified` and an e-mail in `mail.OUTBOX`; 409 second application; 401 anonymous |
| `test_supplier_products_crud_and_review` | pytest | create, add variants, submit → `pending_review`; a `viewer` gets 403; another supplier's product → 404 |
| `test_supplier_geometry_checks` | pytest | a GLB over 500 000 triangles → 422; bounding box 10 % off `dims_mm` → warning; a renamed ZIP → 422 |
| `test_supplier_price_grid_validation` | pytest | `bad_price` for three decimals in GBP; `currency_mismatch` for USD in GB |
| `test_supplier_xlsx_dry_run_and_apply` | pytest | the template filled with two regions: dry run counts, apply creates a `feed_runs` row with the same counts |
| `test_supplier_template_round_trip` | pytest | the downloaded template, filled with the fixture's rows, imports without errors |
| `test_supplier_inbox_quote_and_order_states` | pytest | quote → buyer sees `quoted`; accept, ship, deliver; an `orders` role needed (403 for `catalogue`) |
| `test_supplier_analytics_counts_only` | pytest | counts per day and region; no buyer id in the response |
| `test_supplier_listing_checkout_via_billing` | pytest | listing plan checkout calls PF2's interface (mocked) and records `listing_subscriptions` |
| `test_supplier_members_and_scoped_keys` | pytest | invitation flow; a key made in the portal carries `supplier_id` and works on 5.11 |
| `test_site_pf8_supplier_pages_noindex` | build check | every `out/supplier/**/index.html` carries `noindex` |
| `npm run lint`, `npm run build` | build check | green |

## Human test

1. Local API with PF7 merged and `MAIL_BACKEND=console`; the build served against it.
2. Open `/supplier/signup/` as a new account → fill the company, regions GB and AE, upload a PDF → "Under review"; the API console prints the "application received" e-mail.
3. As an admin: Dashboard → Admin → Market → Suppliers → Verify → the supplier gets the "verified" e-mail; the portal unlocks.
4. Imports → Download template → open it in a spreadsheet program: `catalogue`, `help`, `categories`, `regions` sheets; fill three variants with a GB and an AE row each (or use the contract's `feed-two-regions.csv`).
5. Upload → the dry run shows "6 rows · 3 created · 0 rejected"; change one price to `1299.999` and upload again → that row rejected with `bad_price`; fix it → Apply → the report matches.
6. Catalogue → the products show "In review" → as admin approve them.
7. In an MK1 build (or `curl /market/search?q=…&region=AE`) → the products with AED prices; switch to GB → GBP prices.
8. On a phone at 375 px: open Prices → change stock on a variant; open Inbox → answer a test request for quote (sent by PF7's human test step 7) with a quoted price → the buyer's order page shows `quoted`.

## Risks / traps

* Spreadsheets turn prices into floats: the reader takes `Decimal(str(cell))` and refuses more decimals than the currency allows; never `float`.
* Spreadsheet programs reformat SKUs (`00123` → `123`, long digit strings → exponent form): the template formats `sku`, `variant_id` and `price` columns as text, and the importer warns when a SKU looks numeric-reformatted.
* Feed URLs and row URLs are fetched by the server: the private-address guard must run after DNS resolution, not on the hostname alone.
* A member of several suppliers with an unbound key is ambiguous: such keys get 403 `not_supplier` with a pointer to the portal's supplier keys.
* The first suppliers are onboarded by hand (GD1): the admin queue must stay small enough to read daily; auto-approval for trusted suppliers is a carry-over, not a default.
* Hot spots: `routers/admin.py` and `models.py` with PF7; `constants.ts` with PF13.

## As-built

* Date, branch, commits:
* Counts (pytest before → after):
* Deviations from Design and why:
* GD1 template text and GD7 listing plans adopted:
* Contract §11 rows for the owner to set to "PF8: done" (5.11–5.13) in `contracts/marketplace-api.md`:
* Carry-over → which feature:
