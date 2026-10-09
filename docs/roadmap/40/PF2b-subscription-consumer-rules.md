# PF2b — Subscription consumer rules: DMCC reminders, cooling-off, easy exit, EU withdrawal (launch priority 1)

**Needs merged:** PF2 (billing), PF14 (mail plumbing), PF1 (trials). **Unblocks:** a production checkout once GD5's QS-17 and QS-18 are answered (GD5 decision register, row PF2). **Contract:** none. PF2b adds no app-facing endpoint, and `contracts/licence-api.md` is unchanged.

## Status

**Built (2026-10-10, branch `ap/t19-pf2b-subscription-consumer-rules`) and switched off.** Every rule sits behind a setting that defaults to off, except the easy exit. Nothing GD5 §7.4 drafts reaches a page or a mail until the owner's solicitor approves the wording. The API is in `server/app/billing/consumer.py` (rules, windows, notices, exits, the confirmation) and `server/app/billing/notices.py` (the wording). The site mirrors the wording in `BILLING.rules`, `BILLING.exit` and `BILLING.mails` (`src/lib/constants.ts`); the 7.4 drafts are compiled in only with `NEXT_PUBLIC_LEGAL_WORDING_APPROVED=true`.

Mail goes through PF14's `send_mail` by one guarded import in `notices.py`. PF14 is on master but not yet merged into this branch, so on the branch no mail is sent: each one is logged as "not sent", and the 6 tests that read mail skip. They pass on the merged tree. See As-built.

Before PF2b, verified at `d0129c5` on 2026-10-10:

| Area | Where | Then |
|---|---|---|
| Consent | `server/app/billing/consent.py:12` (`CONSENT_VERSION`), `:15` (`STRIPE_MESSAGE`); `src/lib/constants.ts:298` (`BILLING.consent`); checked at `server/app/routers/billing.py:286` | one placeholder text, versioned, stored on the payment (`server/app/models.py:193`) |
| Key information | — | none: the billing page showed "Total before tax" |
| Cancelling | `server/app/routers/billing.py:480` (`portal`); `src/lib/constants.ts:314` | only through the provider's portal |
| Reminders, trial notice | `server/app/billing/jobs.py:20`, `:46` (the only jobs) | none |
| Confirmation | PF2 Design, Security (`docs/roadmap/40/PF2-billing-through-the-uk-company.md:150`) | the provider's receipt only |
| EU withdrawal | — | none |
| Mail | — | no mail module on this branch's base; PF14's `send_mail` lived on its own branch |
| Carry-over | PF2 Out (`PF2-…md:67`) and As-built (`:268`) | "DMCC Act 2024 subscription rules … a PF2 follow-up with PF14's mail plumbing" |

GD5 (`T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\guides\GD5-legal-and-company-guide.md`, read-only) is now written. §7.1–7.4 give the rules: the DMCC subscription regime starts in "January 2027" (confirm at writing time), and the EU Art. 11a withdrawal function applies from 19 June 2026. §7.4 is the DRAFT wording ("not to be shown to customers until approved"). Its decision register sets the default for PF2: "Paddle in sandbox only; consent text a placeholder; no production checkout".

## Goal

People who subscribe get what UK and EU consumer law asks for. Before paying they see the key facts: price, renewal, how to cancel, who sells. They get reminders before renewals and before a trial ends, and they can cancel inside Billing in one flow. After an annual renewal they can get a refund within 14 days, and an EU consumer can withdraw within the withdrawal period with two clicks. Every order is confirmed by e-mail. The owner has all of it built and tested, and switches each part on once the solicitor signs off the wording and the open questions (GD5 QS-17, QS-18).

## Read first

* `docs/roadmap/40/00-contract.md` P.2–P.4 (P.3 item 3: a plan changes only from an event the server verified itself).
* `docs/roadmap/40/PF2-billing-through-the-uk-company.md`: Design and As-built (`BillingProvider`, `consent.py`, the founding and reconcile jobs, the billing page, `tests/mock_paddle.py`).
* `docs/roadmap/40/PF14-operations-off-the-home-pc-telemetry-and-crash-ingestion.md`: Plumbing (`server/app/mail` `send_mail` with the console backend and `OUTBOX`, `templates/`, `tasks.py` `@periodic` and the worker).
* `docs/roadmap/40/PF1-licence-api-releases-and-downloads.md`: trials are `subscriptions` rows with `provider='trial'`.
* GD5 §7.1–7.4 and §11.2 QS-17, QS-18; the decision register row for PF2.
* Paddle's buyer terms and refund policy (both dated 31 March 2026), for QS-18.
* Skills: `truebex-brand-voice` (payments copy).

## Scope

**In:**
1. Settings in `server/app/config.py`, all off by default: `subscription_notices_enabled` (the UK notices); `subscription_rules_from` (an ISO date, default 2027-01-01, before which nothing is sent); `eu_withdrawal_enabled`; `legal_wording_approved` (while it is false no GD5 7.4 draft sentence renders on any page or mail, and today's placeholder consent stays); `consent_variant` (QS-17).
2. One source for the wording, each text versioned like the consent: the 7.4 texts (the summary beside the pay button, the consent box in both QS-17 variants, the business box, the trial-end notice, the EU withdrawal steps) and the reminder texts, in `BILLING` (`src/lib/constants.ts`) and `server/app/billing/notices.py`.
3. Key pre-contract information at the last step: the summary block beside the pay button on `/dashboard/billing/` and `/checkout/` (price incl. VAT per interval and currency from the catalogue and the chosen price, automatic renewal, how to cancel, the seller). The buyer acknowledges it, and it is stored with the consent version on the payment (additive columns). Behind `legal_wording_approved`.
4. Reminder notices: the `@periodic` job `billing.subscription_notices` mails, through PF14's `send_mail` and new templates, a renewal reminder before each renewal of a live paid subscription (lead time: 14 days before an annual renewal, 3 before a monthly one, as settings; GD5 names none) and a trial-end notice 3 days before a trial ends. Each goes out once per period (`subscription_notices`, unique on subscription, kind and period end). A no-op while the switch is off or before `subscription_rules_from`.
5. Renewal cooling-off: the annual reminder says the customer may cancel within 14 days of the renewal. In that window Billing offers "Cancel and get a refund", which asks the provider (Paddle: cancel plus a refund adjustment; Stripe: cancel plus a refund of the renewal invoice). The plan changes only from the provider's verified webhook. Behind the switch.
6. Easy exit: cancel inside Billing in one flow, without the provider's portal (`POST /billing/cancel` with a confirm step; cancel at the period end; a confirmation mail). The portal link stays.
7. The EU withdrawal function (Directive 2011/83/EU Art. 11a; GD5 7.2 and 7.4 "For EU consumers"): for an EU consumer inside the withdrawal period, "Withdraw from contract" in Billing, then "Confirm withdrawal", then a mailed acknowledgement with the date and time. Never shown when the business box was ticked. Behind `eu_withdrawal_enabled`. Paddle's own provision is recorded for QS-18 (As-built).
8. Confirmation on a durable medium after a paid checkout (7.4 "The confirmation email"): the order, price and renewal terms, the seller, the exact consent and acknowledgement texts with versions and times, how to cancel, links to the terms and EULA in force. Behind `legal_wording_approved`.
9. `/terms/` and `/privacy/` unchanged (GD5 register: no new legal text is published until approved).

**Out (and where it goes):**
* The legal decisions and the final wording (QS-17, QS-18, GD5 §11.2) go to the owner and the solicitor.
* US state automatic-renewal laws get a note in As-built.
* Prices and whether they are shown incl. VAT go to PF2a / GD7 (GD5 §7.6, QS-19).
* The EULA page goes to PF13 / GD5 §4.3; it is linked by `EULA_URL` once published.

## Design

### API

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| GET | `/billing/plans` | none | — | PF2's catalogue plus `rules: {wording_approved, consent_variant, consent_version, key_info_version, eu_withdrawal, renewal_notices}` |
| POST | `/billing/checkout` | session | PF2's body plus `key_info?: {version, acknowledged: true}`, `business?: bool` | PF2's `{url, reference, founding}` plus `key_info` (the stored text, or null). 422 when `consent.version` is not the one in force (the placeholder, or the 7.4 box in the QS-17 variant once approved); 422 without the key information acknowledged while approved |
| GET | `/billing/payments/{reference}` | session | — | the payment with `consent_version`, `key_info`, `key_info_at`, `business` (for `/checkout/`); 404 when it is not the caller's |
| GET | `/billing/subscription` | session | — | PF2's fields plus `can_cancel`, `cooling_off_until`, `withdrawal_until` (null when not offered) |
| POST | `/billing/cancel` | session | `{confirm: true, refund?: false}` | `{kind: cancel\|cooling_off, requested_at, effective_at, refund_minor, currency, status: done\|processing}`. 422 without `confirm: true`; 404 no live Paddle or Stripe subscription; 409 already ending or on its way, or (`refund`) outside the cooling-off or with the switch off; 503 provider off |
| POST | `/billing/withdraw` | session | `{confirm: true}` | the same shape with `kind: withdrawal`. 404 while `EU_WITHDRAWAL_ENABLED` is false or with no live subscription; 409 not an EU consumer, a business purchase, waived, out of time, or already on its way; 422 without `confirm` |

`BillingProvider` gains `cancel_subscription(db, sub, *, immediately)` and `refund(db, sub, *, charge_id, share_ppm, reason) -> Refund`. Paddle uses `POST /subscriptions/{id}/cancel` (`next_billing_period` or `immediately`) and `POST /adjustments` (`action: refund`, `type: full`, or `partial` split over the transaction's line items). Stripe uses `Subscription.modify(cancel_at_period_end)` or `Subscription.cancel`, then `Refund.create` on the invoice's payment intent. Neither applies the provider's answer to our state: the signed `subscription.*` / `customer.subscription.*` webhook does (P.3.3).

### Data

| Table / column | Fields | Notes |
|---|---|---|
| `subscription_notices` (new) | `subscription_id`, `kind` (`renewal_reminder` \| `trial_end`), `period_end`, `sent_at` | unique (`subscription_id`, `kind`, `period_end`): one notice per period |
| `subscription_exits` (new) | `user_id`, `subscription_id`, `kind` (`cancel` \| `cooling_off` \| `withdrawal`), `requested_at`, `effective_at`, `refund_charge_id`, `refund_ppm`, `refund_minor`, `currency`, `refund_id`, `canceled_at`, `refunded_at`, `mail_sent_at`, `error` | the customer's statement with its date and time; the provider steps are retried until they succeed |
| `subscriptions` (+) | `renewed_at`, `renewal_charge_id` | the latest renewal charge, from Paddle's `transaction.completed` with `origin: subscription_recurring` or Stripe's `invoice.paid` with `billing_reason: subscription_cycle` |
| `payments` (+) | `key_info`, `key_info_version`, `key_info_at`, `business`, `country`, `provider_subscription_id`, `confirmation_sent_at` | country and business from the provider's billing address and tax id; `_ADDED_COLUMNS` with `TIMESTAMP WITH TIME ZONE` (valid on SQLite and PF14's Postgres) |

### Rules

* **The DMCC switch** is on when `SUBSCRIPTION_NOTICES_ENABLED` is true and today is on or after `SUBSCRIPTION_RULES_FROM`. It gates the reminders, the trial notice and the cooling-off refund.
* **Renewal cooling-off:** an annual Paddle or Stripe subscription whose latest renewal was billed while the rules were in force, until the end of the 14th day after it. The refund is the unused share of the renewed year, rounded up for the customer.
* **EU withdrawal:**
  * Who: an EU-27 billing country (from the provider), not a business purchase, and the right not waived.
  * The right is waived only by a digital-content consent together with the confirmation e-mail on a durable medium (GD5 7.1: express consent, acknowledgement and confirmation; without all three the right stays).
  * When: until the end of the 14th day after payment.
  * Refund: the whole first payment for a digital-content consent; for the service variant, the unused share (Art. 14(3)).
* **Easy exit:** a live Paddle or Stripe subscription that is not already ending, with no cancellation on its way. It cancels at the period end.
* **On its way:** an exit whose provider steps are unfinished (retried for 7 days), or one requested after the subscription last changed. Until the provider's webhook changes the subscription, the action is not offered again.

### UI

| Page | Change |
|---|---|
| `/dashboard/billing/` "Choose a plan" | Not approved: unchanged (placeholder consent, "Total before tax"). Approved build and API: a **Key information** block with the 7.4 summary for the selected tier, interval, currency and seats; "I've read the key information above."; the 7.4 consent box in the API's QS-17 variant; the optional business box. Checkout stays disabled until both required boxes are ticked. If the API's consent version differs from the build's, the page says payment is being set up. |
| `/dashboard/billing/` "Current plan" | Under "Manage card and cancellation": **Cancel subscription** (easy exit), **Cancel and get a refund** (cooling-off, when offered) and **Withdraw from contract** (EU, approved builds only), each with a confirm step ("Confirm cancellation", "Cancel now and refund", "Confirm withdrawal" or "Keep my plan"). Afterwards it shows a notice and re-reads the plan as the webhook lands. |
| `/checkout/` | When the checkout's stored key information exists, it is shown in "What you're buying" beside Paddle's checkout (Paddle.js inline mode). Otherwise the overlay, as in PF2. |
| `src/lib/constants.ts` | `LEGAL_WORDING_APPROVED`; `BILLING.rules` (the 7.4 drafts; `null` unless approved at build time); `BILLING.exit` (cancel and refund copy); `BILLING.mails` (the notice texts, mirrored); `CHECKOUT.summary` |
| `next.config.ts` | always defines `NEXT_PUBLIC_LEGAL_WORDING_APPROVED` (`"false"` by default), so the minifier drops the drafts from `out/` |

### Jobs / workers

* `billing.subscription_notices`, every 3600 s: renewal reminders (14 / 3 days ahead) and trial-end notices (3 days ahead, approved wording only). Each is reserved in `subscription_notices` before it is sent and released if the mail fails.
* `billing.exits.retry`, every 900 s: finishes exits whose provider call failed, and mails any confirmation that could not be sent, for 7 days.
* Paddle's daily `billing.reconcile` also fetches each live annual subscription's latest renewal charge, covering a renewal webhook missed while the API was down.

### Mail

* **Sending.** PF2b sends through PF14's plumbing, `send_mail(to, template, data, *, reply_to=None)`, and has no mail code of its own. Its only import is in `server/app/billing/notices.py`: `try: from app.mail import send_mail` / `except ImportError: send_mail = None`.
* **Without PF14's mail** (this branch until the merge):
  * `billing.subscription_notices` logs and does nothing.
  * The order confirmation is logged as not sent.
  * Cancellations, refunds and withdrawals are still recorded and sent to the provider. Their confirmations stay unsent (`mail_sent_at` null), and `billing.exits.retry` sends them once mail exists, for 7 days.
* **Templates** are under `server/app/mail/templates/`, named as PF14 names them: `renewal_reminder`, `trial_end`, `cancel_confirmation`, `withdrawal_acknowledgement` and `order_confirmation`. Each has `.subject.txt`, `.txt` and `.html` and holds layout only: every sentence comes from `notices.py` as data.
* **Reading mails locally:** with PF14's `MAIL_BACKEND=console`, `consumer._send` also logs the whole text. Run uvicorn with `--log-config scripts/log-info.json` to see it.

### Security and privacy

* The browser never changes a plan. Cancel, refund and withdraw only ask the provider; the plan changes when the signed webhook arrives (tests post a forged one to prove it). Only the caller's own subscription is touched. Eligibility (window, country, business, waiver, switches) is decided on the server.
* The key information text stored per payment is rendered by the server from the price it picked, not taken from the browser.
* Personal data added: the billing country (two letters) and a business flag per payment, both from the provider. They are already collected by Paddle for tax (PF2 privacy wording). The privacy page is not changed (GD5 register).

## Deliverables

- [x] Settings (`server/app/config.py`, `server/.env.example`), all off by default
- [x] `server/app/billing/notices.py` (wording), `server/app/billing/consumer.py` (rules, notices, exits, confirmation), `base.py` (`Refund`, `cancel_subscription`, `refund`), Paddle and Stripe adapters, `service.record_renewal`
- [x] Five mail templates in `server/app/mail/templates/` (PF14's naming); PF14's `send_mail` through one guarded import in `notices.py` (no mail plumbing of PF2b's own)
- [x] Endpoints `POST /billing/cancel`, `POST /billing/withdraw`, `GET /billing/payments/{reference}`; extra fields on `/billing/plans`, `/billing/subscription`, `/billing/checkout`, `/billing/payments`
- [x] Jobs `billing.subscription_notices`, `billing.exits.retry`
- [x] Tables `subscription_notices`, `subscription_exits`; additive columns on `subscriptions` and `payments`
- [x] `tests/mock_paddle.py`: cancel, adjustments, renewals (`renew()`, `POST /mock/renew/{id|latest}`), the buyer's country and business, `STATE["sent"]`
- [x] Site: billing page (key information, both boxes, exits), `/checkout/` summary, copy in `constants.ts`, `next.config.ts`
- [x] `server/scripts/log-info.json`; README (env table, endpoints, Billing)
- [x] Tests below; this doc; tracker row

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_pf2b_settings_off_by_default` | pytest | every switch off, rules from 2027-01-01, lead times 14 / 3 / 3; `/billing/plans` `rules` says so |
| `test_pf2b_wording_matches_site` | pytest | every 7.4 draft and notice text and version in `notices.py` equals `constants.ts` |
| `test_notices_off_by_default` | pytest | switch off, or on but before `subscription_rules_from`: the job sends nothing and stores no notice row; the job is registered |
| `test_pf2b_without_mail_logs_and_does_nothing` | pytest | with `send_mail` missing: the job logs "not merged" and does nothing; a cancellation is still recorded and sent to the provider, its mail left for the retry |
| `test_renewal_reminder_sent_once_per_period` ✉ | pytest | 3-day lead for monthly (not at 4 days), sent once; the next period gets its own after a mock renewal; annual: 14-day lead and the cooling-off line; nothing for a plan set to end |
| `test_trial_end_notice` ✉ | pytest | the 7.4 trial text 3 days before the end, once; nothing while the wording is unapproved, nothing for an ended trial |
| `test_cancel_easy_exit` | pytest | 401 anonymous; 404 without a subscription; 422 without `confirm: true` or with a bad `refund`; happy path asks Paddle for `next_billing_period` and changes nothing until the webhook, 409 while on its way and after; the portal still works |
| `test_exit_retry_job` | pytest | provider down: `processing`, 409 on repeat; `billing.exits.retry` finishes it once |
| `test_renewal_cooling_off_refund_via_provider_mock` | pytest | renewal recorded from the webhook; refused and not offered while off; on: cancel `immediately` plus a refund adjustment on the renewal transaction; the plan stays until the verified webhook (a forged one is refused); outside 14 days and monthly: not offered |
| `test_renewal_cooling_off_refund_stripe` | pytest | `invoice.paid` records the renewal; `Subscription.cancel` and `Refund.create` on the payment intent; Free only after `customer.subscription.deleted` |
| `test_eu_withdrawal_flow` ✉ | pytest | 401; 404 with the switch off; DE consumer: window 14 days, 422 without confirm, cancel `immediately` plus a full refund of the checkout transaction, acknowledgement with date and time, 409 on repeat, Free after the webhook; GB consumer, FR business purchase and an expired window: 409 |
| `test_eu_withdrawal_rules_without_mail` | pytest | the same rules without reading mail: 404 off, 422, DE consumer cancelled now and refunded with the plan changing only on the webhook, GB, business and late: 409 |
| `test_eu_withdrawal_after_complete_waiver_is_not_offered` ✉ | pytest | digital-content consent plus the confirmation mail: not offered; the service variant keeps the right with a proportionate refund |
| `test_key_information_acknowledged_with_payment` | pytest | off: placeholder consent, nothing stored; on: placeholder refused, key info required (missing, wrong version, not acknowledged: 422); the stored text matches the summary for Team × 3, annual; `GET /billing/payments/{ref}` 200 / 401 / 404; the QS-17 variant picks the consent version |
| `test_confirmation_mail_contents` ✉ | pytest | none while unapproved; once approved, one mail even with replayed events: order, price, "every year", renewal terms, seller and licensor, exact consent text, version and time, key information, version and time, how to cancel, terms and EULA links, HTML part; nothing for an old order |
| `test_exit_confirmation_mails` ✉ | pytest | the cancellation confirmation ("stays active until …"), sent once even after a provider retry; the cooling-off refund mail with the amount |
| `test_site_pf2b_no_draft_wording_in_out` | build check | no fixed run of any 7.4 draft (≥ 16 characters) in `out/**/*.html`, `*.txt` or `_next/**/*.js` while the wording is unapproved |
| `npm run lint`, `npm run build`, `scripts/autopilot-verify.ps1` | build check | green |

✉ reads mail: it starts with `pytest.importorskip("app.mail")` and skips until PF14 is merged into the branch. Until then only PF2b's templates are in `app/mail/`, which imports as an empty namespace package, so the helper also skips when `send_mail` is absent.

## Human test

Setup, about 4 minutes, PowerShell in the worktree. Three terminals: A for the site, B for mock Paddle, C for the API.

**Mail differs with the branch's state.** While PF14 is not merged into this branch (`server\app\mail\__init__.py` absent), terminal C prints a warning for each mail instead of sending it:

`WARNING truebex.billing.consumer: PF14's app.mail is not merged: <template> to <address> not sent`

Once Autopilot has merged master here, the same step prints the mail itself:

`INFO truebex.billing.consumer: console mail <template> to <address>: <subject>`, followed by its text.

The steps below give the template name to look for.

1. **A:** build the site against a local API with the approved wording compiled in, then serve it.
   ```
   $env:NEXT_PUBLIC_AUTH_URL="http://127.0.0.1:8000"; $env:NEXT_PUBLIC_LEGAL_WORDING_APPROVED="true"; npm run build
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1
   ```
   It prints the URL: `http://127.0.0.1:3119/` under Autopilot. If it prints another port, use that port below.
2. **B** (in `server\`): `.venv\Scripts\python.exe -m uvicorn tests.mock_paddle:app --port 8098`
3. **C** (in `server\`):
   ```
   $env:BILLING_PROVIDER="paddle"; $env:PADDLE_API_KEY="pdl_sdbx_local"; $env:PADDLE_WEBHOOK_SECRET="pdl_ntfset_mock_secret"; $env:PADDLE_CLIENT_TOKEN="test_local"; $env:PADDLE_API_BASE="http://127.0.0.1:8098"; $env:SITE_URL="http://127.0.0.1:3119"; $env:CORS_ORIGINS="http://127.0.0.1:3119"; $env:DATABASE_URL="sqlite:///./pf2b-test.db"; $env:BACKGROUND_TASKS="off"
   .venv\Scripts\python.exe scripts\sync_prices.py --provider paddle --env sandbox
   .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --log-config scripts\log-info.json
   ```

**A. Switched off (today's state).**

1. Open `http://127.0.0.1:3119/signup/`, sign up, then open Billing.
   * You see "Choose a plan", the old consent box ("I want my plan to start now…") and "Total before tax".
   * You do not see "Key information" or the business box.
2. Tick the box and press **Continue to payment**. The mock pay page opens. Leave the country on United Kingdom and press **Pay with a test card**.
   * Back on Billing: "Payment received", plan Pro, "Renews on …".
   * The buttons are **Manage card and cancellation** and **Cancel subscription**. There is no "Cancel and get a refund" and no "Withdraw from contract".
3. Press **Cancel subscription**. It reads "Your plan stays active until … and won't renew…". Press **Confirm cancellation**.
   * The notice reads "Cancellation sent…", and within a few seconds the card reads "Ends on …".
   * Terminal C logs `cancel_confirmation` (subject "Your Truebex Pro plan is cancelled"), as described above.
   * Terminal C logs no `order_confirmation` line.

**B. Switched on (as after the solicitor's sign-off).**

4. In C, stop the API (Ctrl+C) and start it again with the switches on:
   ```
   $env:LEGAL_WORDING_APPROVED="true"; $env:EU_WITHDRAWAL_ENABLED="true"; $env:CONSENT_VARIANT="service"; $env:SUBSCRIPTION_NOTICES_ENABLED="true"; $env:SUBSCRIPTION_RULES_FROM="2020-01-01"
   .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --log-config scripts\log-info.json
   ```
5. Sign out, sign up a second account and open Billing.
   * You see **KEY INFORMATION**: "Truebex Pro — <price> incl. VAT a month (<currency>). Renews automatically every month until you cancel. Cancel any time in Billing; … Sold by Paddle.com, our reseller and Merchant of Record."
   * Below it: "I've read the key information above.", the consent ending "…I pay for the days I used." and the business box.
   * **Continue to payment** stays disabled ("Tick both boxes above to continue.") until both of the first two boxes are ticked.
6. Tick both and press **Continue to payment**. On the mock page choose **Germany** and pay.
   * Billing shows Pro with **Cancel subscription** and **Withdraw from contract**.
   * C logs `order_confirmation` (subject "Your Truebex order: Pro"). Once mail is merged, its text holds the order, "Renews automatically every month…", the seller, the consent text with "Version gd5-2026-10-09-service, accepted <date, time> UTC", the key information with its version and time, how to cancel, and the Terms / EULA links.
7. Press **Withdraw from contract**. It reads "Open until <date>…". Press **Confirm withdrawal**.
   * The notice reads "Withdrawal received…", and the card returns to Free within seconds.
   * C logs `withdrawal_acknowledgement`. Once mail is merged, its text reads "We received your withdrawal … on <date> at <hh:mm> UTC" and gives the refund amount.
8. Optional, the renewal cooling-off:
   1. A third account picks **Annual**, pays from United Kingdom, and gets "Payment received".
   2. In a fourth terminal run `Invoke-RestMethod -Method Post http://127.0.0.1:8098/mock/renew/latest`, then reload Billing.
   3. **Cancel and get a refund** appears. Press it, then **Cancel now and refund**.
   * The plan returns to Free, and C logs `cancel_confirmation` (subject "Your Truebex Pro plan is cancelled and refunded", with the amount once mail is merged).
9. Clean up: stop A, B and C and delete `server\pf2b-test.db`.

The default build (no `NEXT_PUBLIC_LEGAL_WORDING_APPROVED`) carries none of the 7.4 drafts. The verify gate proves it on every run (`test_site_pf2b_no_draft_wording_in_out`).

## Risks / traps

* **Two switches for the 7.4 wording.** The API's `LEGAL_WORDING_APPROVED` and the site's build-time `NEXT_PUBLIC_LEGAL_WORDING_APPROVED` must be flipped together. If only the API is flipped, checkout says "being set up", because the build has no approved consent and the versions differ. This is deliberate: it fails closed.
* **"incl. VAT".** The key information states the catalogue price incl. VAT. Flip the wording only once the catalogue prices are tax-inclusive (Paddle `tax_mode` internal; GD5 §7.6, QS-19, PF2a / GD7). Coupon discounts show only in Paddle's checkout.
* **Paddle.js inline mode** on `/checkout/` (used only when key information exists) needs a sandbox check before production. The overlay stays the path while unapproved.
* **Stripe renewals** need `invoice.paid` added to the Stripe webhook endpoint. Paddle needs no new events.
* **No mail until PF14 is merged into this branch.**
  * `notices.send_mail` is None until then: confirmations are only logged, and 6 tests skip.
  * After the merge, `billing.exits.retry` sends the confirmations of exits from the last 7 days.
  * Order confirmations go out only for checkouts paid in the last 2 days.
* **Dates in mails are UTC.** The billing page shows local dates, so the two can differ by a day around midnight.
* **SQLite naive datetimes:** compared through `service._aware` everywhere.
* **The monthly reminder cadence** follows the task (before every renewal). The DMCC's own cadence for short periods is for QS-18.
* **Hot spots shared with other features:** `routers/billing.py`, `schemas.py`, `constants.ts`, `config.py`, `database.py`. The PF2b blocks are kept apart from PF14's.

## As-built

* **Date, branch, commits:** 2026-10-10, `ap/t19-pf2b-subscription-consumer-rules` (base `master` d0129c5).
  * `f16d040`: API, mock, site, tests.
  * `7c83612`: shaped to merge cleanly with PF14, plus polish of the confirmation and mails.
  * `25810de`: `/mock/renew/latest`, this doc, the README and the tracker row.
  * `a701236`: the manager's branch note. PF2b codes against PF14's `send_mail` through one guarded import, has no mail plumbing of its own, and its mail tests skip until PF14 is merged (below).
  * The docs commit that records it.
* **Counts:**
  * pytest with `out/` built (verify gate), on this branch: 140 → 151 passed, 6 skipped.
    * 16 tests in `server/tests/test_billing_pf2b.py`: 10 run, 6 skip (mail).
    * 1 build check in `server/tests/test_site_pf2.py`.
  * Verify gate green.
* **Tests skipped on this branch, and why.** They read mail. They start with `pytest.importorskip("app.mail")` and skip because PF14's `app.mail` (`send_mail`, `OUTBOX`) is not merged into this branch. The skip reason reads "PF14's app.mail (send_mail, OUTBOX) is not merged into this branch yet". They run for real once Autopilot merges master (PF14 is on it as 4758ae1):
  * `test_renewal_reminder_sent_once_per_period`
  * `test_trial_end_notice`
  * `test_eu_withdrawal_flow`
  * `test_eu_withdrawal_after_complete_waiver_is_not_offered`
  * `test_confirmation_mail_contents`
  * `test_exit_confirmation_mails`

  The mail-free parts of those flows also run on the branch: `test_notices_off_by_default`, `test_pf2b_without_mail_logs_and_does_nothing`, `test_cancel_easy_exit`, `test_exit_retry_job`, the two cooling-off tests and `test_eu_withdrawal_rules_without_mail`.
* **The merged result, checked read-only.** `git merge-tree` of this branch with today's `master` reports no conflicts. That tree was exported to a scratch folder and tested in a fresh venv with PF14's requirements:
  * All 16 PF2b tests pass against the real `send_mail`.
  * The full suite gives 167 passed, 30 skipped (site checks without `out/`, Postgres-only tests).
  * One full run had a single failure in PF14's own `test_ops.py::test_sqlite_to_postgres_lists_every_feature_table`, which starts a fresh Python process. It passed alone, with its file, and in a second full run.
* **Self-tests:** an end-to-end run over real HTTP in headless Edge, using the API, `tests/mock_paddle.py` sending signed webhooks, and the built site with the approved wording. It ran twice:
  * **With this branch's API:** every flow works. That is key information and both ticks; a German purchase and withdrawal (plan back to Free from the webhook); a UK purchase and the easy exit ("Ends on …" after the webhook); an annual purchase, renewal and "Cancel and get a refund". Each mail is logged "PF14's app.mail is not merged: <template> to <address> not sent".
  * **With the merged tree's API:** the same flows, with all six mails sent through PF14's `send_mail`: three order confirmations, the withdrawal acknowledgement, and the two cancellation confirmations.
  * The default build has no 7.4 text in `out/`; the approved build has it.

**The switches: what the owner flips, and when**

| Setting (`server/.env`) | Default | Turns on | Flip when | Waits on |
|---|---|---|---|---|
| `SUBSCRIPTION_NOTICES_ENABLED` | `false` | renewal reminders, the trial-end notice (with the wording), "Cancel and get a refund" after an annual renewal | the solicitor approves the reminder, cancellation and cooling-off texts (`notices.py` NOTICE_VERSION) | QS-18 (DMCC rules, reminder notices) |
| `SUBSCRIPTION_RULES_FROM` | `2027-01-01` | the day the UK rules start; nothing is sent or offered before it | set to the commencement date GD5 confirms | QS-18; GD5 §7.3 "confirm at writing time" |
| `RENEWAL_REMINDER_DAYS_YEAR` / `_MONTH`, `TRIAL_END_NOTICE_DAYS` | `14` / `3` / `3` | reminder lead times (GD5 names none) | if the regulations or the CMA guidance set others | QS-18 |
| `EU_WITHDRAWAL_ENABLED` | `false` | "Withdraw from contract" for EU consumers in the period. The button also needs the approved build: its labels are 7.4 wording | QS-18 says Truebex must offer its own function next to Paddle's | QS-18 |
| `LEGAL_WORDING_APPROVED`, plus a site build with `NEXT_PUBLIC_LEGAL_WORDING_APPROVED=true` | `false` | key information at checkout, the 7.4 consent box, the business box, the trial-end notice, the order confirmation e-mail, the EU labels | the solicitor approves GD5 7.4 and these texts (if the wording changes, bump `DRAFT_VERSION` in `notices.py` and `BILLING.rules` together); prices are VAT-inclusive | QS-17 (and QS-19 for VAT-inclusive prices) |
| `CONSENT_VARIANT` | `digital_content` | which 7.4 consent box checkout asks for, and how a withdrawal is refunded | the solicitor classifies the subscription | QS-17 |
| `COMPANY_ADDRESS`, `EULA_URL` | empty | the registered office and the EULA link in the confirmation (empty EULA = the terms page) | the company is incorporated; the EULA page is published | QS-2, QS-3 (GD5 §1.3, §4.3) |

The easy exit has no switch. The task listed none, it is not GD5 7.4 wording, and it only asks the provider to cancel at the period end, as the portal already does.

* **QS-18: who provides the EU withdrawal function under a merchant of record** (read 2026-10-10):
  * Paddle's Refund Policy (paddle.com/legal/refund-policy, dated 31 March 2026), §3.1.1: "An online withdrawal button is available in the Paddle Customer Portal for eligible transactions during the 14-day withdrawal period". It is reached from the "Manage subscription" link in Paddle's e-mails or at paddle.net ("Request withdrawal").
  * §2.2.2: the right covers "one-off purchases and … the first payment under a Subscription contract", not later payments.
  * §2.2.3: "If you completed a Transaction in the UK and have an annual Subscription, you will have a new period of 14 calendar days to exercise your right to withdraw starting the day the Subscription auto-renews for another year."
  * Paddle's buyer terms (same date) keep the digital-content exception when the buyer agreed to early access and started using the product.
  * So, as merchant of record, **Paddle provides a withdrawal function itself**, reachable from Billing's "Manage card and cancellation". Whether Truebex must also offer its own (it licenses the software; Paddle sells it) is QS-18. `EU_WITHDRAWAL_ENABLED` stays off either way.
  * Paddle refunds a UK annual renewal in full under its own policy. PF2b's cooling-off refunds the unused share; the solicitor decides which to use.
* **US automatic-renewal laws:**
  * Not built separately. GD5 §7.3 notes state laws (for example California's, amended from 1 July 2025) with their own consent, reminder and online-cancellation rules (QS-18).
  * PF2b's pieces cover the usual elements: key terms before payment, express consent, a confirmation with cancellation steps, online cancellation in Billing, and renewal reminders.
  * Whether their timing and content fit each state, and whether US buyers need a different reminder (annual plans, trials), is for the solicitor. No US-specific switch exists yet.
* **Deviations from the task text, and why:**
  1. **The trial-end notice needs `LEGAL_WORDING_APPROVED` as well as the DMCC switch.** Its text is GD5 7.4's, which must not reach a mail until approved.
  2. **"Withdraw from contract" shows only in an approved build** (its two labels are 7.4 wording). The API's own check is `EU_WITHDRAWAL_ENABLED`.
  3. **Exits are recorded before the provider is called.**
     * A cancellation or withdrawal is a customer's statement: it is stored with its time and confirmed by e-mail at once.
     * The provider steps (cancel, then refund) are retried by `billing.exits.retry` for 7 days; the API answers `status: processing` meanwhile.
     * A provider error is never shown as a failure of the customer's request.
  4. **Refund amounts:**
     * Cooling-off: the unused share of the renewed year.
     * Withdrawal: the whole first payment with a digital-content consent (the right was not waived, so nothing is owed: reg. 37, Art. 14(4)(b)); the unused share with the service consent.
     * Rounding goes the customer's way.
     * The withdrawal button is withheld when the waiver is complete (digital-content consent plus the confirmation mail), per GD5 7.1.
  5. **Renewals are recorded from the renewal charge.** Paddle: `transaction.completed` with `origin: subscription_recurring`, plus the daily reconcile. Stripe: `invoice.paid` with `billing_reason: subscription_cycle`. The charge is stored as `renewal_charge_id`, and that is what gets refunded.
  6. **The country and the business flag come from the provider** (Paddle's transaction address, fetched because webhooks carry only its id; Stripe's `customer_details`). The checkout's business box also sets the flag, and a provider tax id sets it too.
  7. **Extra endpoint `GET /billing/payments/{reference}`**, so `/checkout/` can show the stored key information beside the pay button. `/checkout/` then uses Paddle's inline checkout instead of the overlay.
  8. **The order confirmation goes out only for checkouts paid in the last 2 days.** Approving the wording later does not mail old orders when a late event arrives. Its seller block reads "Paddle.com, our reseller and Merchant of Record" and "The software is licensed to you by Truebex Ltd[, COMPANY_ADDRESS]". Paddle's own address is on Paddle's receipt.
  9. **Stripe's consent box text** now mirrors the consent the buyer accepted (the 7.4 text once approved).
  10. **Mail, per the manager's branch note.** The note said to merge master into the branch when PF14's mail is on master, and otherwise to keep no mail plumbing and code against PF14's interface.
      * PF14's mail is on master (4758ae1), but the merge was refused in the task run: "Autopilot guard: `git merge` is not allowed in a task run -- the human merges after testing". So the note's second path applies.
      * The copy of PF14's `server/app/mail/__init__.py` and `smtp.py` that this branch had carried is removed, and `config.py`'s plumbing block is back to the base (PF14's arrives with the merge).
      * `notices.py` holds the one guarded import of `send_mail`. Without it, the notices job logs and does nothing.
      * The templates stay in `server/app/mail/templates/` with PF14's naming, and the mail tests importorskip.
      * Console mails print their whole text with `uvicorn … --log-config scripts/log-info.json` once mail is merged.
  11. **The reminder goes before every renewal, monthly included,** as the task says. The DMCC sets its own cadence for short renewal periods, so the cadence may change after QS-18; only the lead-time settings and the job's query would change.
* **GD5 wording adopted:** the 7.4 drafts, verbatim, as `DRAFT_VERSION gd5-2026-10-09`. The consent versions are `gd5-2026-10-09-digital` and `gd5-2026-10-09-service`. The renewal reminder, cooling-off, cancellation, refund and acknowledgement texts are Truebex's own, as `NOTICE_VERSION pf2b-2026-10-09`, for the solicitor to read too. Today's placeholder consent (`2026-10-09`) stays in force until the wording is approved.
* **Carry-over → which feature:**
  * **Owner and solicitor:** QS-17 (classification, consent variant, the confirmation e-mail, whether the provider's receipt suffices) and QS-18 (DMCC date and reminders, the EU function under Paddle, US laws). Then flip the switches above. Also set `COMPANY_ADDRESS` and `EULA_URL`, and add `invoice.paid` to Stripe's webhook endpoint.
  * **PF2a / GD7:** VAT-inclusive catalogue prices before `LEGAL_WORDING_APPROVED`.
  * **PF13:** the EULA page (then `EULA_URL`); `/terms/` and `/privacy/` unchanged here.
  * **PF3:** organisation-owned checkouts are business purchases; set `business` on them.
  * **PF14 (merged):** after Autopilot merges master here, optionally list the PF2b settings in `infra/secrets/server.env.example` (all default off, so the VM needs nothing until a switch is flipped).
  * **Contract `licence-api.md` §11:** no row changes.
