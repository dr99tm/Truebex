# PF3a — Organisation billing: organisations buy and change seats through PF2 (launch priority 2)

**Needs merged:** PF2, PF3 (both on `master` after T15 and T22). **Unblocks:** organisation seats bought online (no more hand grants with `grant_org_seats.py` for Team); PF4 (organisation-owned projects) reads the same `organisation_id`. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\licence-api.md` (5.5 entitlement `seat_kind` and `account.org_id`, 5.7 Account panel `seats {total, assigned}`; no new app-facing endpoint).

## Status

**Built on branch `ap/t21-pf3a-organisation-billing-organi` (2026-10-10, Autopilot T21); see As-built.** Before this task, on `master` 57a7309 (PF2 and PF3 merged; verified with Grep on 2026-10-10):

| Area | Where (master 57a7309) | Before |
|---|---|---|
| Seats given to people | `server/app/billing/service.py:134-137` (`seats_assigned`) | always `1`, so `POST /billing/seats` never refused a drop below the seats an organisation had given |
| Paddle checkout | `server/app/billing/paddle_provider.py:202` | only the comment `# PF3 adds "org_id"`; no organisation anywhere in `custom_data` |
| Stripe checkout | `server/app/billing/stripe_provider.py:108-114` | metadata names the user only |
| Attaching | `server/app/billing/paddle_provider.py:252-294`, `stripe_provider.py:192-241` | `user_id` from `custom_data` or metadata; `subscriptions.organisation_id` (PF3, `server/app/models.py:164-167`) never set by billing |
| Management | `server/app/routers/billing.py:119-160` (`_subscription_out`, `_live_managed`), `:311-318` (409), `:415-444` (invoices), `:479-492` (portal) | personal only; `service.managed_subscription` (`service.py:97-113`) also picked up an organisation's rows |
| Licence path | `server/app/orgs/seats.py:306` | `seats.assigned` = named seats + floating seats in use |
| UI | `src/app/dashboard/organisation/page.tsx:201` | the console's Billing link opened `/dashboard/billing/?org=…`, which ignored `org` and showed the personal page |
| Organisation seats | `server/scripts/grant_org_seats.py` | by hand only (PF3 As-built, merge note) |

What the owner meant: PF2's As-built carry-over to PF3 ("`org_id` in the checkout's `custom_data`; `service.seats_assigned` (409 below assigned seats) becomes real") and PF3 Scope item 4 ("the `billing` role buys and changes seats through PF2").

## Goal

A practice's owner (or the person they give the billing role) opens Billing from the organisation console, buys Team seats for the organisation on the same checkout people use, and later adds seats, changes the plan or interval, opens the card and cancellation portal and downloads the organisation's invoices. The seats reach the members PF3 assigns, named or floating, in their app's entitlement; the buyer's own plan never changes. Nobody can attach a subscription to an organisation by writing its id into Paddle's `custom_data`. Human test seed: "create an organisation, buy Team ×3 for it on the mock Paddle from `/dashboard/billing/?org=…`, assign two named seats, try to drop to 1 seat (refused), and see a member's entitlement say team".

## Read first

* `docs/roadmap/40/00-contract.md` P.2 to P.4 (P.3 item 3: a plan changes only from an event the server verified).
* `PF2-billing-through-the-uk-company.md`: API table, Data, As-built deviations 1 (founding per subscription), 3 (`custom_data` only names the account; a price we never synced grants nothing) and 5 (409 while a live subscription exists).
* `PF3-organisations-seats-and-sso.md`: Scope 4 to 8, roles `owner`, `admin`, `billing`, `member`, `seat_assignments`, `organisations.floating_seats`, As-built deviation 9 (`live_subscription` skips organisation rows) and the T22 merge note.
* `PF1-licence-api-releases-and-downloads.md` As-built: `seat_source`, the Account panel's `seats {total, assigned}`.
* PF2b (`POST /billing/cancel`): not written or merged on 2026-10-10, so cancellation stays in the provider's portal.
* Code: `server/app/billing/` (`base.py`, `service.py`, `paddle_provider.py`, `stripe_provider.py`), `server/app/routers/billing.py`, `server/app/orgs/` (`service.py`, `seats.py`), `server/app/licence/seats.py`, `src/app/dashboard/billing/page.tsx`, `src/app/checkout/CheckoutClient.tsx`, `src/lib/developer.ts`.
* Skills: `truebex-brand-voice` (dashboard copy).

## Scope

**In:**
1. Checkout for an organisation: `POST /billing/checkout` takes an optional `org_id` (32 hex). Only the organisation's owner or billing role may buy: 403 for admin and member, 404 for a non-member, 401 anonymous. The catalogue's `min_seats` and `per_seat` rules apply as for people. 409 while the organisation already has a live subscription; a buyer's personal subscription does not block an organisation checkout, and the reverse holds too. The payment row records `organisation_id` (additive column via `_ADDED_COLUMNS`). Paddle `custom_data` and Stripe metadata carry `org_id`.
2. Attach on the verified webhook from our own payment row (the subscription's originating transaction or checkout session), never from `custom_data` alone. A subscription whose `custom_data` names an organisation without a matching payment of ours is not attached to it. An organisation's tier is never written into the buyer's `users.plan` cache.
3. Management by owner and billing roles: `GET /billing/subscription`, `POST /billing/seats`, `POST /billing/change`, `POST /billing/portal` and `GET /billing/invoices` accept `org_id` with the same role check (PF2b's cancel is not in the tree).
4. `service.seats_assigned(db, sub)` made real: for an organisation subscription the named seats assigned plus the floating pool size (`organisations.floating_seats`); for a personal one 1. `POST /billing/seats` below that answers 409 with `data {assigned}`. PF3's seat settings and seat assignment keep refusing anything above the bought total.
5. The licence path: a subscription bought this way gives assigned members the organisation's tier through PF3's `seat_source` (named and floating), and `/licence/account` `seats {total, assigned}` read the subscription's seats and `seats_assigned`.
6. UI: `/dashboard/billing/?org=<id>` (read inside `Suspense`) shows the organisation's plan, seats and invoices, and offers checkout to owner and billing roles (others see the plan read-only). The PF3 console's Billing link opens it. Copy follows `truebex-brand-voice`.
7. Founding offer: one founding place per organisation subscription, the same per-subscription rule PF2 uses.

**Out (and where it goes):**
* SCIM provisioning → not planned in roadmap 40 (PF3's carry-over).
* Enterprise invoices by hand → the owner, through `create_invoice` on the Stripe adapter (PF2) and `grant_org_seats.py` (PF3).
* Prices → PF2a / GD7.
* `POST /billing/cancel` for organisations → PF2b, when it lands (it takes `org_id` with the same `require_billing` check).

## Design

### API

Every route below keeps PF2's behaviour without `org_id`. With `org_id` it acts for that organisation; `billing.org_billing.require_billing` answers 404 `not_found` (shared envelope) to someone outside it and 403 `forbidden` to an admin or member.

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| POST | `/billing/checkout` | session, owner/billing | PF2's body + `org_id?` | `{url, reference, founding}`; the Paddle URL ends `&ref=…&org=<id>`; 409 `live_subscription` (`data.plan`) while the organisation has a live, past-due or paused subscription (a hand grant included); 422 bad `org_id` |
| GET | `/billing/subscription?org_id=` | session, owner/billing | — | PF2's shape + `org_id`, `seats_assigned`; without a subscription `tier "free"`, `seats 0`, `status "none"` |
| POST | `/billing/seats` | session, owner/billing | `{seats, org_id?}` | the subscription; 409 `seats_assigned` with `data {assigned, named, floating}` below `service.seats_assigned`; 422 below `min_seats` |
| POST | `/billing/change` | session, owner/billing | `{tier?, interval?, org_id?}` | the subscription; 409 `seats_assigned` when the new plan would keep fewer seats than are assigned |
| POST | `/billing/portal` | session, owner/billing | `{org_id?}` (optional body) | `{url}`; 404 without a subscription |
| GET | `/billing/invoices?org_id=` | session, owner/billing | — | the organisation's invoices; `pdf_url` signed for the user and the organisation (`&o=<id>`) |
| GET | `/billing/payments?org_id=` | session, owner/billing | — | the organisation's checkouts, whoever paid; rows carry `organisation_id` |
| GET | `/billing/invoices/{id}/pdf?u&p&o&exp&sig` | signed link | — | 302; with `o` the user must still be owner or billing, and the invoice one of the organisation's subscriptions |

Attaching, in `billing/org_billing.py` and the adapters:

| Event | Paddle | Stripe |
|---|---|---|
| The link we trust | `subscription.created` names `transaction_id`; our payment's `provider_ref` is that transaction (we created it through the API) | `checkout.session.completed`: `client_reference_id` is our reference and the session id is the one we stored |
| Also | `transaction.completed` of our organisation checkout names `subscription_id`: the subscription is fetched from Paddle and applied with the organisation (a lost `subscription.created`) | the return-page refresh and the reconcile retrieve the session |
| Return page / reconcile | `verify_payment` fetches our transaction, then its subscription, with the payment as origin | `verify_payment` retrieves our session |
| A subscription event naming one of our organisation checkouts (`org_id` + `reference`) without the link | held back (not applied, event recorded `skipped`) until the link arrives, so it is never the buyer's personal plan in between | same (a `customer.subscription.*` event ahead of its session) |
| A subscription naming an organisation with no checkout of ours (Paddle.js with the public token) | not attached; applied as PF2 applies it, for the person `custom_data` names | same |

`upsert_subscription(…, organisation_id=)` sets the organisation once, on a row without one, and never changes or clears it; buying for an organisation does not end the buyer's own trial.

### Data

| Table / column | Fields | Notes |
|---|---|---|
| `payments.organisation_id` | `VARCHAR(32)`, nullable | `_ADDED_COLUMNS` (PF3a block in `server/app/database.py`); the organisation a checkout buys for |
| `subscriptions.organisation_id` | PF3's column | now written by billing, from the payment row only |

No new settings, jobs or tables.

### UI

| Page / component | Change |
|---|---|
| `src/app/dashboard/billing/page.tsx` | `?org=<id>` read inside `Suspense`; the organisation is loaded with `GET /orgs/{id}`; owners and billing members get PF2's page for the organisation (plan card with "3 seats · 2 assigned", Team preselected, checkout with `org_id`, change and seat stepper with the assigned-seats hint and a link to the Seats tab, portal, invoices, payments, a link back to the console); admins and members get the plan read-only; a malformed `org` says so. The personal page lists "Organisations you buy for" with their Billing links |
| `src/app/checkout/CheckoutClient.tsx` | returns an organisation checkout to `/dashboard/billing/?org=<id>&checkout=…` |
| `src/lib/developer.ts` | `getSubscription`, `listInvoices`, `listPayments`, `changeSeats`, `changePlan`, `openBillingPortal` take an optional `orgId`; types gain `org_id`, `seats_assigned`, `organisation_id` |
| `src/lib/constants.ts` | `ORG_BILLING` (new, at the end) |

### Security and privacy

* The browser can name an organisation but never attach one: attaching reads our payment row, matched by the provider's own link, and the role check runs before any provider call.
* An organisation's tier never reaches `users.plan` (PF3's `live_subscription` rule); its members get it through `seat_source`.
* Invoice PDF links for an organisation are HMAC-signed with the organisation id and re-check the role when opened.
* Personal invoices and payment history leave out what a person bought for organisations; the organisation's lists show every buyer's checkouts.

## Deliverables

- [x] `server/app/billing/org_billing.py` (roles, the organisation's subscriptions, `seats_assigned`, invoice scopes, attaching rules)
- [x] `service.seats_assigned` real; `service.managed_subscription` personal only; `upsert_subscription(organisation_id=)`
- [x] Paddle and Stripe adapters: `org_id` in `custom_data` / metadata, attaching from the payment row, `InvoiceScope` for invoices and PDFs
- [x] `server/app/routers/billing.py`: `org_id` on checkout, subscription, seats, change, portal, invoices, payments, PDF links
- [x] `payments.organisation_id` (model + `_ADDED_COLUMNS`); schemas
- [x] `seat_source` and the Account panel read `seats_assigned`
- [x] `server/tests/test_billing_orgs.py`; `server/tests/mock_paddle.py` sends `transaction_id` on `subscription.created` and returns to `?org=`
- [x] `/dashboard/billing/?org=`, `/checkout/` return, `developer.ts`, `ORG_BILLING`
- [x] This doc, the tracker row, a README section

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_org_checkout_roles` | pytest | owner and billing 200 (custom_data `org_id`, payment `organisation_id`, URL `&org=`); admin and member 403; non-member and unknown organisation 404; anonymous 401; malformed `org_id` 422; `min_seats` 422; Enterprise 400; a personal checkout names no organisation |
| `test_org_checkout_attaches_subscription_from_payment` | pytest | `subscriptions.organisation_id` set from the payment; the buyer's `users.plan` (a running trial) unchanged and the trial not ended; `/orgs/{id}` and `/billing/subscription?org_id=` show Team ×3; replays and updates keep it attached |
| `test_org_checkout_attaches_when_webhooks_are_late_or_lost` | pytest | a `subscription.updated` ahead of `subscription.created` is held back (no personal plan); the return-page refresh attaches it; `transaction.completed` alone attaches it |
| `test_org_forged_custom_data_not_attached` | pytest | Paddle.js-style `custom_data` naming the organisation → not attached (the named person's own); a claim with a real organisation checkout's reference but no transaction → never applied; the real checkout still attaches |
| `test_org_second_live_subscription_conflict` | pytest | 409 `live_subscription` for owner and billing; the organisation's subscription does not block the buyer's own, nor theirs another organisation's; past due still 409 |
| `test_org_seats_below_assigned_conflict` | pytest | 3 seats, 2 named + 1 floating: seats 2 → 409 `seats_assigned` `data.assigned` 3; seats 4 → 200 through the mock (prorated); PF3's floating setting above the total → 422; roles 401/403/404 |
| `test_org_billing_management_roles` | pytest | subscription, invoices, payments, portal and change: 401 / 403 / 403 / 404 by role; the billing member's invoice PDF link opens; the buyer's personal invoices and payments leave the organisation's out; change interval for the organisation; a plan change below the assigned seats → 409 |
| `test_org_founding_one_place_per_subscription` | pytest | an organisation's Team ×5 takes one founding place, still one after 9 seats; the buyer's own founding subscription is a second place |
| `test_org_subscription_reaches_member_entitlement` | pytest | Team ×3 + a named seat: the member's 5.5 says `team`, `seat_kind` `named`, `account.org_id`; 5.7 `seats {total 3, assigned 1}`, then 5 after buying more; buyer and member keep Free |
| `test_org_stripe_metadata_org_id` | pytest | Checkout metadata and `subscription_data.metadata` carry `org_id`, return URLs `&org=`; a subscription event ahead of its session is held back; the session attaches it; metadata naming the organisation on another subscription is not attached |
| PF1, PF2, PF3 suites | pytest | unchanged and green |
| `npm run lint`, `npm run build` | build check | green |

## Human test

Local stack: mock Paddle, the API on :8000 and the built site. Use `@example.com` addresses and the password `password123`.

1. In `server\.env` (`server\run.bat` copies `.env.example` there on first run): a long `SECRET_KEY`; `BILLING_PROVIDER=paddle`, `PADDLE_API_KEY=pdl_sdbx_local`, `PADDLE_WEBHOOK_SECRET=pdl_ntfset_mock_secret`, `PADDLE_CLIENT_TOKEN=local`, `PADDLE_API_BASE=http://127.0.0.1:8098`; `SITE_URL` = the address `autopilot-serve.ps1` prints (`http://127.0.0.1:3121` for T21) and that address in `CORS_ORIGINS`; `MAIL_BACKEND=console`; `LICENCE_SIGNING_KEY` from `.venv\Scripts\python.exe scripts\make_signing_key.py --kind lic` (only for step 8).
2. Terminal 1, in `server\`: `.venv\Scripts\python.exe -m uvicorn tests.mock_paddle:app --port 8098`. Terminal 2: `server\run.bat`. Terminal 3, in `server\`: `.venv\Scripts\python.exe scripts\sync_prices.py --provider paddle --env sandbox` → "36 prices". In the worktree: `$env:NEXT_PUBLIC_AUTH_URL="http://127.0.0.1:8000"; npm run build`, then `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1`.
3. Sign up `owner@example.com` → Dashboard → Organisation → Create an organisation "Studio North" → in its console's Plan panel, **Billing** → `/dashboard/billing/?org=…`: "Plan, seats, invoices and payments of Studio North.", "No seats yet", Choose a plan with Team selected.
4. Seats 3, tick the consent box, Continue to payment → the mock pay page lists the Team price × 3 → Pay with a test card → back on the organisation's billing page: "Payment received. The organisation's seats are active."; Current plan Team, "Monthly · 3 seats · 0 assigned"; one invoice with Download (opens the PDF). Your own `/dashboard/billing/` still says Free plan and lists Studio North under "Organisations you buy for".
5. Console → Seats: set floating to 1. Invites: `a@example.com` and `b@example.com`, each with a named seat; the links print in Terminal 2; accept each in a private window after signing up.
6. Back on Billing (`?org=`): "3 seats · 3 assigned". Seats stepper to 2 → Update seats → OK: the red note "3 of Studio North's seats are assigned (2 named, 1 floating). …" and the count stays 3. Stepper to 4 → Update seats: "4 seats · 3 assigned".
7. As `a@example.com`, open `/dashboard/billing/?org=…`: the plan (Team, 4 seats) read-only with "Only an owner or a billing member of this organisation can change its plan and see its invoices."; no checkout.
8. In `server\`: `.venv\Scripts\python.exe scripts\try_device.py --email a@example.com --password password123 --name "Test PC 1" --refresh` → `entitlement: plan team · seat named · org <the organisation's id>`.

## Risks / traps

* **Paddle customers are one per e-mail.** The organisation's subscription lives under its buyer's Paddle (or Stripe) customer, so the portal a billing member opens is the buyer's whole customer portal, including any personal subscription there. Buy organisation seats with a work address, or let the billing person buy (owner decision, As-built carry-over).
* Static export: `?org=` and the return parameters are read inside `Suspense`; the page loads the organisation in the browser, so a non-member sees the API's 404 message.
* Held-back events: a subscription event that names one of our organisation checkouts waits for the verified link; if the provider never sends it and the return page is never opened, the daily `billing.reconcile` (pending checkouts of the last 48 h) applies it.
* Deleting an organisation with a pending (unpaid) checkout: a payment completed afterwards attaches to the deleted organisation, which nobody can open; the provider refunds. Rare; not guarded.
* Hot spots shared with other features: `routers/billing.py`, `billing/service.py`, the adapters, `schemas.py`, `constants.ts` (block at the end), `billing/page.tsx`.

## As-built

* **Date, branch, commits:** 2026-10-10, `ap/t21-pf3a-organisation-billing-organi` from `master` 57a7309. `8433980` (API, tests, mock), `87e27cf` (site), then copy polish and this doc.
* **Counts:** pytest in the verify gate 220 → 230 passed (+ 3 Postgres-only skips); new `server/tests/test_billing_orgs.py` (10 tests); PF1, PF2 and PF3 test files unchanged. `out/`: no new route. Verify gate green. Self-test beyond pytest: an end-to-end run over real HTTP (uvicorn API, `tests/mock_paddle.py` under uvicorn sending signed webhooks, `out/` built against that API and served) with headless Edge over CDP: the console's Billing link, `?org=` page empty → Team ×3 checkout on the mock pay page → paid notice, plan card and invoice; floating 1 and two named invites accepted; seats 2 refused with the reason; seats 4 applied; a member's read-only view; the personal page's organisation list; no browser errors; then the member's 5.5 (`team`, `named`, `org_id`), 5.7 `seats {4, 3}`, the buyer still Free, the API's 409 `seats_assigned` and the member's 403 (36 of 36 checks).
* **Deviations from the task and why:**
  1. **Held back, not personal, while the link is pending.** An event that names one of our organisation checkouts (`org_id` and its `reference`) but carries no verified link is not applied at all until the link arrives (Paddle: `subscription.created`'s `transaction_id`, our transaction's `subscription_id`, the refresh; Stripe: our session). Applying it as the buyer's personal plan meanwhile would have ended their trial and put Team in their cache for a moment. A claim with no checkout of ours behind it is applied as PF2 does, for the person named, and never attached.
  2. **`transaction.completed` of an organisation checkout fetches its subscription** from Paddle and applies it with the organisation, so a lost `subscription.created` cannot leave the organisation without seats (PF2's personal flow had the same gap; left as it was).
  3. **Error codes in the shared envelope:** `live_subscription` (409, also for a live hand grant: "set up by hand. Contact us") and `seats_assigned` (409, `data {assigned, named, floating}`). The personal seat 409 now uses the envelope too (same status; the site reads `detail` either way).
  4. **`POST /billing/change` for an organisation** refuses a plan that would keep fewer seats than are assigned (e.g. Team → Pro with 3 assigned), with the same 409.
  5. **Beyond the five routes:** `GET /billing/payments?org_id=` (the organisation's checkouts), `o=` on invoice PDF links (signed with the organisation; the role is re-checked when opened). Personal invoices and payment history leave out organisation purchases.
  6. **`SubscriptionOut` adds `org_id` and `seats_assigned`; `PaymentOut` adds `organisation_id`.** An organisation without a subscription reads `tier "free"`, `seats 0`, `status "none"`.
  7. **The Account panel's `seats.assigned`** is now `seats_assigned` (named seats + the floating pool size) for organisation seats, as Scope 5 asks; PF3 had reported named seats + floating seats *in use*. Personal seats still read 1.
  8. **`InvoiceScope`** (`billing/base.py`): `list_invoices` and `invoice_pdf_url` take an optional scope (customers, and the subscriptions to keep or leave out), because an organisation's invoices can sit under several buyers' provider customers.
  9. **Mock:** `tests/mock_paddle.py` now puts `transaction_id` on `subscription.created` (as Paddle does) and its pay page returns to `?org=`.
  10. **UI extras:** Team preselected for an organisation; "Organisations you buy for" on the personal page; a link back to the console.
  11. **No PF2b:** `POST /billing/cancel` is not in the tree; cancellation stays in the portal.
* **Contract *implemented by* rows for the owner to apply in `contracts/licence-api.md` at merge:** no endpoint changes. Suggested *Changes* line: "2026-10-10 · 1.0.0 · PF3a: 5.7 `seats.assigned` of an organisation seat = named seats assigned + the floating pool size (was named + floating in use); organisation subscriptions are bought through PF2's checkout."
* **Carry-over → which feature:**
  * **Owner:** decide whether organisation portals should open only for the buyer (Paddle and Stripe customers are per e-mail; see Risks). Retire `grant_org_seats.py` for Team once Paddle is live (it stays for Enterprise).
  * **PF2b:** `POST /billing/cancel` takes `org_id` through `org_billing.require_billing`.
  * **PF2:** the personal flow's lost-`subscription.created` gap (deviation 2) could reuse `_attach_from_transaction` for every checkout.
  * **PF4:** organisation-owned projects can read `subscriptions.organisation_id` for the organisation's tier.
