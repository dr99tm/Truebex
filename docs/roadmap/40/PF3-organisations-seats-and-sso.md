# PF3 — Organisations, seats and SSO (launch priority 2)

**Needs merged:** PF1. **Unblocks:** none by Needs; PF4 (projects owned by an organisation) and PF2 (organisation-owned subscriptions) use its tables when present. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\licence-api.md` (seat kinds and the floating-seat lease).

## Status

**Done 2026-10-09** on `ap/t9-pf3-organisations-seats-and-sso` (Autopilot T9): the whole Scope: In, every test of the Tests table, verify gate green. See As-built (deviations, carry-over, and the fix to PF1's missing `server/app/storage/` package that this branch had to make first). The paragraph and table below are the pre-task snapshot.

No organisations, roles, invites, seat assignment, SSO or audit log exist (`00-contract.md` P.1). The code this extends, verified with Grep on 2026-10-09:

| Area | Where | Today |
|---|---|---|
| Accounts | `server/app/models.py:22-43` (`User`), `:34-36` (`plan` is a per-user cache) | one person = one plan |
| Sign-in | `server/app/routers/auth.py:25-37` (register), `:40-54` (password), `:57-68` (Google token check), `:71-112` (Google sign-in, link by e-mail), `:115-120` (`/auth/me`) | no SSO |
| Sessions | `server/app/security.py:32-38` (JWT with `sub` = user id) | stored in `localStorage` by `src/lib/api.ts:30-33` |
| Usage per user | `server/app/models.py:73-90` (`UsageDaily`), `server/app/routers/usage.py:22-62` | per key and endpoint; nothing per organisation |
| Sign-in UI | `src/components/auth/AuthForm.tsx:16`, `:28`, `:70-72` | Google button and e-mail form |
| Dashboard | `src/components/dashboard/DashboardShell.tsx:71-127` | no organisation switcher |
| From PF1 (Needs) | `devices`, `licence_events`, `subscriptions.seats`, `seat_source(user)`, `require_admin`, entitlement `seat_kind` | personal seats only |
| From PF2 (when merged) | `upsert_subscription`, `change_subscription`, `custom_data` | subscriptions owned by users |

What the owner meant: app-side `00-understanding.md` §1 (Studio, Team, Enterprise; seats in the entitlement).

## Goal

A practice buys Team seats once and runs them itself: the owner creates the organisation, invites people, gives each a named seat or lets them share floating seats, sees who uses what, and an Enterprise customer signs everyone in through its own identity provider. Every licence event (activation, seat change, lease, sign-in through SSO) lands in an audit log the admins can read and export. Human test seed: "create an organisation, invite two members, assign seats, see both activate".

## Read first

* `docs/roadmap/40/00-contract.md` (P.3); PF1 (devices, entitlements, `seat_source`, `licence_events`); PF2 (subscriptions, seats at the provider).
* **`contracts/licence-api.md` v1.0.0** (2026-10-09): seat kinds `free`, `personal`, `named`, `floating`, `trial` (§6.1); floating seats are leased by `POST /licence/entitlement` (5.5, `refresh_after` 30 min, `expires_at` 2 h) and handed back by `POST /licence/release` (5.11, this feature's endpoint); 409 `no_seat_available` and 409 `not_floating` (§7); the Account panel's `seat` and `seats` (5.7). `org_id` travels as 32 hex (§6.1 `account`).
* `guides/GD7-*.md` (seat prices, named against floating, minimums) and `guides/GD5-*.md` (enterprise data-processing terms) are not written yet: placeholders.
* Specifications: OpenID Connect Core 1.0; RFC 7636 (PKCE); OASIS SAML 2.0 Core, Bindings and Profiles (Web Browser SSO, SP-initiated); W3C XML Signature; Somorovsky et al., "On Breaking SAML: Be Whoever You Want to Be", USENIX Security 2012 (signature wrapping).
* Mail through `server/app/mail` and periodic jobs through `server/app/tasks.py` (PF14 §Design, Plumbing).

## Scope

**In:**
1. Organisations: create, rename, delete (owner only, no live subscription), a unique slug; a user may belong to several and keeps a personal workspace.
2. Members and roles: `owner`, `admin`, `billing`, `member`; change role, remove, leave; at least one owner at all times.
3. Invites by e-mail with a role and an optional seat, a 7-day token link `/invite/?t=…`, accepted only by a signed-in account with the invited e-mail; resend and revoke.
4. Organisation subscriptions: `subscriptions.organisation_id` (PF2 sets it from `custom_data.org_id`); the `billing` role buys and changes seats through PF2.
5. Named seats: an admin assigns one to a member; the member's devices get the organisation's tier, `limits.devices` applying per member.
6. Floating seats: a pool of concurrent leases (the organisation decides how many of its seats float); a floating member's `POST /licence/entitlement` (5.5) takes or renews a lease and gets a document with `refresh_after` 30 min and `expires_at` 2 h (contract §6.1); `POST /licence/release` (5.11) hands it back at exit; a lease not renewed lapses with its document; a full pool answers 409 `no_seat_available` (names of the holders for admins in the console).
7. Seat choice: PF1's `seat_source(user)` extended to pick the best of personal subscription, named seats and floating pools by tier rank; the entitlement carries `seat_kind` and `account.org_id`, the Account panel `seat {kind, org_id, org_name}` and `seats {total, assigned}`.
8. Admin console `/dashboard/organisation/`: Members (role, seat, last active, devices), Invites, Seats (named assigned / total, floating in use now), Usage per member, SSO, Audit log, a Billing link.
9. Usage per member: active devices, last activity, API requests this month, floating-seat hours this month; columns for cloud storage, panoramas and AI credits filled from `metering` once PF4, PF6 and PF11 record them.
10. SSO for Enterprise through OIDC (authorization code + PKCE, discovery, JWKS) and SAML 2.0 (SP-initiated, HTTP-Redirect request, HTTP-POST response, signed assertions required), one connection per organisation; verified e-mail domains route sign-in to the organisation's provider; just-in-time membership; an "SSO required" policy for domain users with an owner break-glass code; SP metadata endpoint.
11. Audit log of licence events: PF1's `licence_events` plus organisation events (members, roles, invites, seats, leases, SSO sign-ins, policy changes), filterable, exportable as CSV, kept 24 months (`from GD5`).
12. E-mails: invite, seat assigned, removed from organisation.
13. Tests for every endpoint (happy path, auth failure, validation failure), the lease race and both SSO protocols against local mock providers.

**Out (and where it goes):**
* Checkout and the provider-side seat quantity → PF2 (PF3 calls `change_subscription`).
* Project ownership and per-project roles → PF4 (projects may belong to an organisation).
* The app's seat display, lease handling and offline message → LC1 (app).
* SCIM user provisioning → not planned in roadmap 40 (a carry-over row if an Enterprise deal asks for it).
* Encrypted SAML assertions → carry-over (v1 requires TLS and signed, unencrypted assertions).
* Enterprise contract terms → GD5.

## Design

### API

Roles gate routes: *member* = any role, *admin* = `owner` or `admin`, *owner* = `owner`. Device auth is PF1's `tbx_dev_…` token.

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| POST | `/orgs` | session | `{name}` | `201 {id, slug, name, role: "owner"}`; 422 |
| GET | `/orgs` | session | — | `[{id, name, slug, role, seat_kind}]` |
| GET / PATCH / DELETE | `/orgs/{id}` | member / admin / owner | `{name}` | 200 / 200 / 204; 409 live subscription |
| GET | `/orgs/{id}/members` | member | — | `[{user_id, email, name, role, seat_kind, last_active_at, devices}]` |
| PATCH / DELETE | `/orgs/{id}/members/{user_id}` | admin (or self to leave) | `{role}` | 200 / 204; 409 `last_owner` |
| POST / GET | `/orgs/{id}/invites` | admin | `{email, role, seat: named\|floating\|none}` | `201 {id, expires_at}`; 409 already a member |
| DELETE | `/orgs/{id}/invites/{invite_id}` | admin | — | 204 |
| POST | `/invites/accept` | session | `{token}` | `200 {org_id}`; 403 e-mail mismatch; 410 expired |
| GET | `/orgs/{id}/seats` | admin | — | `{tier, total, named: {total, assigned}, floating: {total, in_use, leases: [{user, device, since}]}}` |
| PUT | `/orgs/{id}/seats/settings` | admin | `{floating}` | 200; 422 above total |
| PUT | `/orgs/{id}/seats/{user_id}` | admin | `{kind: named\|floating\|none}` | 200; 409 `no_seat_left` |
| POST | `/licence/entitlement` (contract 5.5, PF1's route) | device | `{fingerprint, app_version}` | for a floating member: takes or renews the lease; 409 `no_seat_available` |
| POST | `/licence/release` (contract 5.11) | device | — | 204; 409 `not_floating` |
| GET | `/orgs/{id}/usage?month=2026-10` | admin | — | `[{user_id, devices, last_active_at, api_requests, floating_hours, storage_bytes, panoramas, ai_credits}]` |
| GET | `/orgs/{id}/audit?cursor=&kind=&format=csv` | admin | — | `{events: [{at, actor, kind, target, details}], next}` or CSV |
| GET / PUT | `/orgs/{id}/sso` | owner | `{kind: oidc\|saml, issuer, client_id, client_secret, idp_metadata_xml, required}` | 200; secrets are write-only |
| POST | `/orgs/{id}/domains` · `/orgs/{id}/domains/{domain}/verify` | owner | `{domain}` | `201 {txt_record}` · 200 when the DNS TXT record matches |
| GET | `/auth/sso/start?email=&next=` | none | — | 302 to the provider; 404 no SSO for the domain |
| GET | `/auth/sso/oidc/callback` | `state` | `code, state` | 302 to `${SITE_URL}/login/sso/#token=…&next=…` |
| GET | `/auth/sso/saml/{org_slug}/metadata` | none | — | SP metadata XML |
| POST | `/auth/sso/saml/{org_slug}/acs` | signed `SAMLResponse` | form post | 302 as the OIDC callback |

The session token returns in the URL fragment, which browsers never send to a server or write to access logs; `/login/sso/` stores it with `setToken` (`src/lib/api.ts:30-33`) and follows `next` through `safeNext` (`src/lib/auth.ts:77-80`).

### Data

| Table / column | Fields | Notes |
|---|---|---|
| `organisations` | `id` (32 hex UUIDv7, PF1's `ids.py`), `name`, `slug` unique, `created_by`, `created_at`, `floating_seats`, `sso_required`, `deleted_at` | |
| `org_members` | `org_id`, `user_id`, `role`, `joined_at` (PK both ids) | |
| `org_invites` | `id`, `org_id`, `email`, `role`, `seat_kind`, `token_hash`, `invited_by`, `expires_at`, `accepted_at`, `revoked_at` | 256-bit token, hash stored |
| `seat_assignments` | `org_id`, `user_id`, `kind` named / floating, `assigned_by`, `assigned_at` | floating = may lease |
| `floating_leases` | `id`, `org_id`, `user_id`, `device_id`, `leased_at`, `expires_at` (= the document's `expires_at`, 2 h), `released_at` | in use = not released and not expired |
| `org_domains` | `org_id`, `domain` unique, `txt_token`, `verified_at` | |
| `sso_connections` | `org_id` PK, `kind`, `issuer`, `client_id`, `client_secret_enc`, `idp_entity_id`, `idp_sso_url`, `idp_cert_pem`, `enabled` | secret sealed with Fernet (`SSO_SECRET_KEY`) |
| `sso_requests` | `id`, `org_id`, `state`, `nonce`, `code_verifier`, `saml_request_id`, `next`, `expires_at` | 10 min, single use |
| `sso_assertions_seen` | `assertion_id`, `expires_at` | SAML replay cache |
| `audit_events` | `id`, `at`, `org_id`, `actor_user_id`, `kind`, `target_kind`, `target_id`, `details` JSON | the audit view unions PF1's `licence_events` of the organisation's members |
| `subscriptions.organisation_id` | `_ADDED_COLUMNS`, nullable | an organisation's paid tier |

`users.plan` (`server/app/models.py:34-36`) stays the personal plan; what a device may do is decided by `seat_source`, never by that cache.

### UI

| Page / component | What it shows |
|---|---|
| `DashboardShell.tsx` | an organisation switcher above the nav (personal + each organisation) and an Organisation group for admins |
| `src/app/dashboard/organisation/page.tsx` (+ `members/`, `invites/`, `seats/`, `usage/`, `sso/`, `audit/`) | the console of Scope item 8; tables with the dashboard's `Panel` and `ErrorNote` (`DashboardShell.tsx:151-176`) |
| `src/app/invite/page.tsx` (noindex) | reads `?t=` inside `Suspense`, asks to sign in or sign up with the invited e-mail, then Accept |
| `src/app/login/sso/page.tsx` (noindex) | reads the fragment, stores the token, continues to `next` |
| `AuthForm.tsx` | "Continue with SSO": a work e-mail field that calls `/auth/sso/start`; password sign-in for an SSO-required domain answers with a pointer to SSO |

Copy stays inline as in the rest of the dashboard; the public login strings live in `src/lib/constants.ts`.

### Jobs / workers

| Job | Every | Does |
|---|---|---|
| `licence.leases.expire` | 60 s | marks leases past `expires_at` free (a closed laptop's lease ends with its 2 h document); writes an audit event |
| `orgs.invites.expire` | 24 h | marks invites past 7 days |
| `sso.requests.purge` | 600 s | deletes used or expired `sso_requests` and `sso_assertions_seen` rows |
| `audit.purge` | 24 h | deletes events older than the retention |

Local stand-ins for the human test and the tests: `server/tests/mock_oidc.py` (discovery, JWKS, authorize, token) and `server/tests/mock_saml_idp.py` (signs a response with a test certificate), in the manner of `server/tests/mock_wayl.py`.

### Security and privacy

* SAML is implemented with `signxml` and `lxml` (both ship Windows wheels for the verify gate): the response or assertion must be signed by the configured certificate, and only the element `signxml` returns as verified is read, which defeats signature wrapping; then Issuer, Audience (our entity id), Recipient (the ACS URL), `NotBefore` / `NotOnOrAfter` (±120 s), `InResponseTo` (a pending request) and one use per assertion id. Rejected: `python3-saml` and `pysaml2` (both need the native `xmlsec1` library, which has no dependable Windows build for the verify gate); a hosted SSO broker (a fee per connection and another processor in the privacy policy); a self-hosted broker (one more service for one person to run).
* OIDC is implemented with `httpx` and `python-jose` (both already pinned, `server/requirements.txt:8`, `:15`): PKCE S256, `state` and `nonce`, the ID token checked against the provider's JWKS (cached 1 h), `iss`, `aud`, `exp`, `email_verified`, and an e-mail in a verified domain of that organisation.
* Account linking: an existing account with the same e-mail is joined only when the domain is verified for the organisation, the gap the Google flow closes with `email_verified` (`server/app/routers/auth.py:94-98`).
* SSO-required organisations: password and Google sign-in refused for their domains; owners keep a one-time break-glass code shown once at setup.
* Floating leases are taken inside one transaction that locks the organisation row (`SELECT … FOR UPDATE` on Postgres, `BEGIN IMMEDIATE` on SQLite), so two devices cannot take the last seat.
* Invite tokens and break-glass codes stored hashed; client secrets sealed; every admin action written to `audit_events`.

## Deliverables

- [x] `server/app/orgs/` (`service.py`, `seats.py`, `audit.py`), `server/app/routers/orgs.py`; PF1's `seat_source` extended; `POST /licence/release` in `server/app/routers/licence.py`
- [x] `server/app/sso/` (`oidc.py`, `saml.py`, `domains.py`), `server/app/routers/sso.py`; `signxml`, `lxml` pinned
- [x] models, `_ADDED_COLUMNS` (`subscriptions.organisation_id`), settings (`SSO_SECRET_KEY`, `SAML_SP_ENTITY_ID`), `.env.example`
- [x] mail templates `org_invite`, `org_seat_assigned`, `org_removed`; `server/scripts/grant_org_seats.py` (hand assignment for Enterprise and tests)
- [x] `server/tests/mock_oidc.py`, `server/tests/mock_saml_idp.py`, test certificates under `server/tests/fixtures/sso/`
- [x] dashboard organisation pages, switcher, `/invite/`, `/login/sso/`, `AuthForm` SSO entry, `src/lib/orgs.ts`
- [x] the tests below; contract *implemented by* rows recorded in As-built

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_orgs_create_and_list` | pytest | 201 with role `owner`; listed; 401 anonymous; 422 empty name |
| `test_orgs_delete_blocked_by_subscription` | pytest | 409 with a live organisation subscription; 204 without; 403 for an admin |
| `test_orgs_member_roles_and_last_owner` | pytest | role change by admin; demoting or removing the last owner → 409; 403 for a member |
| `test_orgs_invite_accept_flow` | pytest | invite → console mail in `mail.OUTBOX` → accept with the same e-mail → member with the invited role |
| `test_orgs_invite_rejects_mismatch_and_expiry` | pytest | 403 other e-mail; 410 after 7 days; 401 without session |
| `test_orgs_named_seat_assignment` | pytest | assigned member's entitlement has the organisation tier and `seat_kind` `named`; 409 when none left |
| `test_orgs_named_seat_device_limit` | pytest | the member's third device → 409 `device_limit` (contract §7) |
| `test_licence_floating_lease_refresh_and_release` | pytest | 5.5 returns `seat_kind` `floating`, `refresh_after` +30 min, `expires_at` +2 h; a second 5.5 renews; 5.11 → 204 frees the seat; 401 without device token |
| `test_licence_release_not_floating` | pytest | 5.11 on a named seat → 409 `not_floating` |
| `test_licence_floating_pool_full` | pytest | with the one floating seat in use, another member's 5.5 → 409 `no_seat_available`; the console names the holder for admins only |
| `test_licence_floating_race_last_seat` | pytest | two concurrent 5.5 calls for the last seat → exactly one 200 |
| `test_licence_lease_expiry_job` | pytest | a lease past `expires_at` is freed by `licence.leases.expire` |
| `test_orgs_seat_source_picks_best` | pytest | personal Pro + named Team → entitlement tier `team` |
| `test_orgs_usage_per_member` | pytest | API requests per member from `usage_daily`; floating hours from leases; 403 for a member |
| `test_orgs_audit_log_and_csv` | pytest | invite, seat change, lease and SSO sign-in each logged; CSV header and rows; 403 for a member |
| `test_sso_domain_verification` | pytest | TXT record mismatch → 409; match (resolver mocked) → verified |
| `test_sso_oidc_login_jit` | pytest | against `mock_oidc`: callback → new user, member of the organisation, token in the redirect fragment |
| `test_sso_oidc_rejects_bad_state_nonce_audience` | pytest | each tampered value → 401 |
| `test_sso_saml_login_signed_assertion` | pytest | against `mock_saml_idp`: valid response → session; SP metadata parses |
| `test_sso_saml_rejects_wrapping_replay_and_audience` | pytest | a wrapped unsigned assertion, a replayed assertion id, a wrong audience and an expired `NotOnOrAfter` → 401 each |
| `test_sso_required_blocks_password_and_google` | pytest | domain user's `/auth/login` and `/auth/google` → 401 pointing to SSO; break-glass code works once |
| `test_site_pf3_new_pages_noindex` | build check | `out/invite/`, `out/login/sso/`, `out/dashboard/organisation/` carry `noindex` |
| `npm run lint`, `npm run build` | build check | green |

## Human test

As built: use `@example.com` addresses (the existing sign-up validator refuses the reserved `.test` names), and verify the test domain by hand in step 10 (no DNS answers for it).

1. Start the local API (`server\run.bat`, `MAIL_BACKEND=console`) and serve the build against it (`scripts/autopilot-serve.ps1`).
2. Sign up as `owner@example.com`; Dashboard → Organisation → Create "Studio North" → the console appears with you as Owner.
3. Give the organisation a Team subscription with 2 seats: through PF2's sandbox checkout, or in `server/` run `.venv\Scripts\python.exe scripts\grant_org_seats.py --org studio-north --tier team --seats 2` (the hand-assignment helper, as `enterprise` is set by hand today).
4. Seats tab: set floating to 1 → "Named 0 / 1 · Floating 0 / 1".
5. Invite `a@example.com` (named) and `b@example.com` (floating) → two invite e-mails print in the API console with links.
6. In two private windows, sign up as a and b and open the links → Accept → Members lists both with their seat kinds.
7. Activate a device as a and as b (an LC1 build, or `server\scripts\try_device.py`, which acts as the app on a pretend computer) → both entitlements show `team`; b's shows `seat_kind` `floating` with `expires_at` two hours ahead.
8. Seats tab → Floating "1 / 1 in use, b · Test PC 2 · since 14:03"; a third member set to floating gets 409 `no_seat_available` from `/licence/entitlement` and the app runs Free with "All 1 floating seats are in use".
9. Audit tab → activation, seat assignment and lease rows; Export CSV downloads them.
10. SSO (optional on the local stack): start `mock_oidc` (`uvicorn tests.mock_oidc:app --port 8098`), verify the test domain with `scripts\verify_org_domain.py --org studio-north --domain example.com`, configure the SSO tab (OpenID Connect, issuer `http://127.0.0.1:8098`, client id `truebex-local`, secret `mock-oidc-secret`), sign out, "Continue with SSO" with `c@example.com` → back on the dashboard as a new member.

## Risks / traps

* `effective_plan` and the `users.plan` cache are per user (`server/app/billing/service.py:55-65`): never write an organisation's tier into the personal cache; the entitlement comes from `seat_source`.
* Floating seats need a network: offline, a floating entitlement ends 2 h after its last refresh (contract §6.1); LC1 says so in the Account panel before people travel.
* SQLite serialises writers, so the lease race test passes there too; on Postgres the row lock carries it (PF14's Postgres job runs the test).
* SSO e-mail takeover: only verified domains route to an IdP, and only that organisation's IdP can assert them.
* The SAML ACS is a cross-site POST without a CSRF token by design; `InResponseTo`, the signature and the replay cache protect it.
* Hot spots: `routers/auth.py`, `AuthForm.tsx`, `DashboardShell.tsx`, `routers/licence.py` (PF1) are shared with PF1 and PF2; edit in own blocks.

## As-built

* **Date, branch, commits:** 2026-10-09, `ap/t9-pf3-organisations-seats-and-sso` from `ap/t1-pf1-licence-api-releases-and-dow` (fa824cf). `9faba33` (PF1's storage package, see deviation 1), `4cf397b` (server services and routers), `c5d5c6c` (server tests, mock providers, hand scripts), `4a6925e` (site), then docs and `scripts/try_device.py` (the app's stand-in for the human test).
* **Counts:** pytest 68 → 99 in the verify gate (64 passed + 4 skipped before, all 99 pass now with `out/` built; new: `test_orgs.py` 9, `test_orgs_seats.py` 10, `test_sso.py` 9, `test_site_pf3.py` 3, PF1's hook test adjusted). Every name in the Tests table exists verbatim. Pages in `out/`: 16 → 25 `index.html` (`/invite/`, `/login/sso/`, `/dashboard/organisation/` and its six tabs). Self-tests beyond pytest: the human test's steps 2–10 run over HTTP against a real uvicorn API and `mock_oidc` under uvicorn (grant script, invite mails in the console, accept, two activations, the third floating member's 409, audit + CSV, 5.11, OIDC sign-in landing on `/login/sso/#token=`), and headless Edge over CDP opening all seven console pages, the Log in page's "Continue with SSO" and `/invite/` against that API with no browser errors.
* **Deviations from Design and why:**
  1. *PF1's `server/app/storage/` was never committed*: `server/.gitignore` ignored every `storage/` folder, so the base branch failed pytest at import. The ignore now names only the data folder (`/storage/`) and the package is rewritten to the PF14 Plumbing interface PF1's tests exercise (`put/open/stat/delete/list/signed_get_url/signed_put_url`, HMAC URLs, `local.clock`). **At merge:** keep PF1's own copy if it reappears on the PF1 branch, else this one.
  2. *Test addresses.* Pydantic's `EmailStr` refuses `.test` addresses at `/auth/register`, so the tests and the human test use `@example.com`; a test domain is verified by hand with `scripts/verify_org_domain.py` (real domains verify by DNS TXT).
  3. *The lease lock* is one portable statement, `UPDATE organisations SET lease_seq = lease_seq + 1` before counting: pysqlite opens its transaction at the first write, which takes SQLite's RESERVED lock; on Postgres the UPDATE holds the row lock as `SELECT … FOR UPDATE` would. `test_licence_floating_race_last_seat` widens the race window with a barrier and fails when the lock is removed (checked).
  4. *Floating seats per device* (one running copy = one seat). When the owner lowers the floating count below the seats in use, the newest leases end at their next refresh (`pool_reduced`) and the oldest keep theirs. A full pool falls back to another seat the person holds (their own paid plan, another organisation's seat) before answering 409 `no_seat_available` (`data: {total, org_id, org_name}`; holders are named only in the admin console). Activation (5.4) with a full pool still returns the device token with the personal seat, so the app can retry with 5.5.
  5. *Domains* are unique among verified rows (a partial unique index), so several organisations may claim a pending domain but only one verifies it (`domain_taken`); TXT record `_truebex-verification.<domain>` = `truebex-domain-verification=<token>`.
  6. *Endpoints beyond the table:* `POST /invites/preview` (what `/invite/` shows before sign-in), `POST /orgs/{id}/invites/{invite_id}/resend`, `GET /orgs/{id}/domains`, `DELETE /orgs/{id}/domains/{domain}`, `DELETE /orgs/{id}/sso`, `POST /orgs/{id}/sso/break-glass`, and `format=json` on `/auth/sso/start` (the site asks for `{url}` and can say "no SSO for this domain" in place).
  7. *Columns beyond the Data table:* `organisations.break_glass_hash`, `.lease_seq`; `org_invites.created_at`, `.accepted_by`, `.expired_at`; `floating_leases.end_reason`; `sso_requests.login_hint`, `.created_at`, `.used_at`; `org_domains.id`, `.created_at`; `subscriptions.organisation_id` is also on the model and indexed. All new tables, so no other migration.
  8. *Error codes* (shared envelope on every PF3 route): `last_owner`, `no_seat_left`, `already_member`, `already_invited`, `email_mismatch` (403), `invite_expired` (410: expired, revoked or used), `live_subscription`, `domain_taken`, `txt_mismatch`, `sso_not_ready`, `sso_not_found`, `sso_failed` (401), `sso_required` (401 on `/auth/login` and `/auth/google`, 403 on `/auth/register`).
  9. *Personal vs organisation plans:* `billing.service.live_subscription` now ignores rows with `organisation_id`, so a seat bought for an organisation is never its buyer's personal plan; hand grants are `provider="manual"` rows (`scripts/grant_org_seats.py`, `--until` makes a fixed term that caps `expires_at`).
  10. *SAML:* AuthnRequests are unsigned (HTTP-Redirect); IdP-initiated sign-in is refused (`InResponseTo` must name a pending request); a response must hold exactly one Assertion and the signed element must be that one, on top of reading only what `signxml` verified. `signxml==5.1.0` and `lxml==6.1.3` are pinned (signxml 4.x breaks with PF1's `cryptography==50`).
  11. *OIDC* requires `email_verified: true`; the provider's token endpoint gets `client_secret_basic` unless its discovery lists only `client_secret_post`.
  12. *Mail:* `server/app/mail/` (PF14's interface) with the `console` adapter only; a send failure is logged, never fails the request.
  13. *Usage per member* answers the spec's list; storage, panoramas and AI credits stay `null` until an `app.metering` module exists (read through it when present).
  14. PF1's `test_licence_floating_durations_hook` now stubs the new `seats.claim` step too (its fake organisation has no row to lease from).
  15. *Site:* the Workspace switcher stores the choice in `localStorage` (`truebex_org`); the Organisation group shows Members to everyone, Invites/Seats/Member usage/Audit log to owners and admins, SSO to owners. The Billing link is `/dashboard/billing/?org=<id>` for PF2 to read. Public strings: `SSO_LOGIN`, `SSO_CALLBACK`, `INVITE_PAGE` in `constants.ts`; the privacy page gains an Organisations item (roles, seats, audit log kept 24 months, identity-provider claims).
* **GD7 seat rules and GD5 retention adopted:** neither guide exists yet. Any tier may be granted to an organisation; the owner decides how many seats float (no minimums, no price difference between named and floating); audit retention 24 months as the placeholder `AUDIT_RETENTION_DAYS=730`.
* **Contract *implemented by* rows for the owner to apply in `contracts/licence-api.md` at merge:** `POST /licence/release` → "PF3: done". 5.5 now leases floating seats (§6.1 durations) and answers 409 `no_seat_available` with `data {total, org_id, org_name}` (additive); 5.7 reports `seat {kind: named|floating, org_id, org_name}` and the organisation's `seats {total, assigned}` (assigned = named seats given + floating seats in use). Suggested *Changes* line: "2026-10-09 · 1.0.0 · PF3: 5.11 implemented; `no_seat_available` carries `data.total`, `data.org_id`, `data.org_name`."
* **Carry-over → which feature:** SCIM provisioning → not planned (a row if an Enterprise deal asks). Encrypted SAML assertions and signed AuthnRequests → carry-over (only if an IdP insists). Providers that omit `email_verified` (some Entra ID set-ups) → carry-over: a per-connection "trust the IdP's e-mail" switch. Setting `subscriptions.organisation_id` from `custom_data.org_id`, the seat stepper and `change_subscription` from the Billing link → PF2. The `smtp` mail adapter and the race test on Postgres → PF14. Storage, panoramas and AI-credit columns → PF4, PF6, PF11 via `metering`. The app's seat display, 409 handling and `POST /licence/release` at exit → LC1.
* **Merged with PF1, PF2, PF13 and PF14 (2026-10-10, Autopilot T22, `ap/t22-merge-t9-pf3-organisations-seats`):**
  one copy of each shared file. `storage/` is master's (PF1's package plus PF14's `s3.py`), as deviation 1 asked; this
  branch's rewrite is gone. `mail/` is PF14's module (`smtp` adapter, `MAIL_FROM` default `hello@truebex.com`) with
  PF3's additions: `Message.template`, `try_send`, a strict `render` (a missing `$name` raises `KeyError`; it returns
  PF14's `Message`) and the console backend printing each message in the API console (the human test's invite links).
  Organisation and SSO jobs take PF14's `fn(now)` and open their own session (PF1's `fn(db, now)` form is gone: every
  round would have raised `TypeError`), and `app.tasks` loads `orgs.jobs` and `sso.jobs`, so `python -m app.worker`
  runs them. `plans.plan_rank` became PF2's `plans.rank`. `subscriptions.organisation_id` sits beside PF2's columns.
  `scripts/sqlite_to_postgres.py` copies PF3's ten tables; `infra/secrets/server.env.example` and the README carry
  `SSO_SECRET_KEY`, `SAML_SP_ENTITY_ID` and `AUDIT_RETENTION_DAYS`. The SSO test keys had never been committed (the
  root `.gitignore` drops `*.pem`; the suite passed only in T9's own worktree): the mock providers now write a
  test-only set on import when one is missing (`make_test_keys.ensure()`). `test_sso` compares callback URLs with
  `API_URL` (conftest now sets `http://testserver`). Site: the dashboard nav is Overview and Billing, the Organisation
  group (by role), Developer, then PF14's Admin group for `is_admin` accounts; `/privacy/` keeps the Organisations item
  beside PF2's billing-records text. Counts: pytest 208 passed + 3 Postgres-only skipped on SQLite; on a local
  Postgres 17 (`TEST_APP_DATABASE_URL` and `TEST_DATABASE_URL`) every PF3 test passes, the last-seat race test included
  (that PF14 carry-over is done, as is the `smtp` adapter). The one Postgres failure is PF2's
  `test_wayl_checkout_and_verified_webhook`, which assumes a UTC database session (`.replace(tzinfo=utc)` on a `+03:00`
  value): a PF2 test fix, not this merge's. Still open → PF2: checkout does not send `custom_data.org_id` or set
  `organisation_id`, and `billing.service.seats_assigned` still answers 1, so organisation seats are granted by hand
  (`grant_org_seats.py`) and the console's Billing link (`?org=`) opens the personal billing page.
  Second sync (PF14a, T20): `grant_org_seats.py` imports `app` before SQLAlchemy (PF14a's fix for fresh processes
  dying with 0xC000070A; `test_fresh_process_never_queries_wmi` now loads PF3's hand scripts too), and the deploy
  skill names `SSO_SECRET_KEY`, `SAML_SP_ENTITY_ID`, `AUDIT_RETENTION_DAYS` and the hand-seat command, as
  `test_deploy_skill.py` requires.
