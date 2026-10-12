# PF3d — OpenID Connect sign-in from identity providers that omit `email_verified` (launch priority 2)

**Needs merged:** PF3, PF14b (both on `master` at 6ef7928). **Unblocks:** PF3's carry-over "Providers that omit `email_verified` (some Entra ID set-ups) → a per-connection 'trust the IdP's e-mail' switch". **Contract:** none (platform routes only; no app-facing endpoint changes).

## Status

**Built on branch `ap/t56-pf3d-sso-openid-connect-sign-in` (2026-10-12); see As-built.** Before this task, on `master` 6ef7928:

| Area | Where (master 6ef7928) | Gap |
|---|---|---|
| ID-token check | `server/app/sso/oidc.py:221` `verify_id_token` | any token whose `email_verified` is not true is refused ("The identity provider did not confirm this e-mail address."). Microsoft Entra ID puts no `email_verified` in its ID tokens, so an Entra organisation cannot sign in over OIDC |
| SAML | `server/app/sso/saml.py` | already trusts the asserted address |
| Both paths | `server/app/sso/service.py:290` `sign_in` | refuses any address outside the organisation's verified domains (`domains.is_verified_for`) |
| Connection | `server/app/sso/models.py:18` `SsoConnection` | no per-connection setting for this |

Trusting the organisation's own identity provider for its own verified domains gives OIDC the trust SAML has today.

## Goal

An organisation whose OpenID Connect provider never marks addresses as verified (Microsoft Entra ID is the common case) can still sign its people in through SSO. The owner turns on one switch on the SSO tab, "Trust the e-mail address from your identity provider". Only addresses in the organisation's verified domains can sign in, as before, and a provider that says an address is *not* verified is still refused. Until the switch is on, the failure page tells the person exactly which setting the owner needs.

## Read first

* `docs/roadmap/40/00-contract.md` (P.2 to P.4).
* `PF3-organisations-seats-and-sso.md`: Design (OIDC and account linking), As-built deviations 5, 8, 11, 12 and 15, and the carry-over line.
* `PF14b-outbound-requests-pinned.md` (`oidc.py`'s pinned outbound client; the loopback rule for the mock provider).
* `server/app/sso/{oidc,service,models,schemas}.py`, `server/app/routers/sso.py`, `server/app/database.py` (`_ADDED_COLUMNS`), `server/scripts/sqlite_to_postgres.py`, `server/tests/{mock_oidc,test_sso}.py`, `src/app/dashboard/organisation/sso/page.tsx`.
* Microsoft identity platform, optional claims: `xms_edov` ("email domain owner verified", a boolean).
* `.claude/skills/truebex-brand-voice/SKILL.md` (no other vendor named on the page).

## Scope

**In:**

1. The ID-token rule in `verify_id_token` accepts the address when `email_verified` is true, when Entra's optional `xms_edov` is true, or when `email_verified` is absent and the connection's switch is on. An explicit `email_verified: false` stays refused with the switch on, because the provider says the address is not verified. A missing `email` keeps its own refusal. `finish_oidc` passes the connection's switch in.
2. `sso_connections.trust_idp_email`, a boolean defaulting to off, added to existing databases through `_ADDED_COLUMNS`. GET and PUT `/orgs/{org_id}/sso` read and write it (owner only, as the rest of the tab). It is OIDC's: SAML refuses it on. Each change is written to the organisation's audit log (`sso.trust_email_on` / `sso.trust_email_off`).
3. The refusal (401 `sso_failed`, JSON and the HTML failure page) tells the organisation what to do when `email_verified` is absent and the switch is off.
4. The SSO tab's OpenID Connect form gets the checkbox, off by default, with a one-line explanation; the copy in its own block at the end of `src/lib/constants.ts` (no other vendor named). The audit tab names the two new events.
5. `server/tests/mock_oidc.py` gets an environment switch (one small block) so the tests and the human test can play Entra: `MOCK_OIDC_EMAIL_VERIFIED=true|false|absent`, `MOCK_OIDC_XMS_EDOV=1`.

**Out (and where it goes):**

* Reading `email` from Entra's `preferred_username` or `upn` when `email` is missing: not done (those are sign-in names, not necessarily mailboxes). Entra sends `email` for an account with an e-mail address when the `email` scope (which the sign-in asks for: `openid email profile`) or the `email` optional claim is configured. A provider that sends no `email` keeps its refusal.
* The `userinfo` endpoint as a second source of `email_verified`: not used (the ID token is the only source, as in PF3).
* `discover()` and the https rule for the discovery document's endpoints → PF3c (Autopilot T53, running at the same time; see Risks).

## Design

### API

No new endpoints. Visible behaviour:

| Where | Before | After |
|---|---|---|
| OIDC callback, ID token without `email_verified`, switch off | 401 `sso_failed` "The identity provider did not confirm this e-mail address." | 401 `sso_failed` "Your identity provider did not mark this address as verified. An owner can turn on “Trust the e-mail address from your identity provider” in Organisation → SSO." (JSON, or the "Single sign-on did not finish" page for a browser) |
| the same, switch on | 401 | 302 to `${SITE_URL}/login/sso/#token=…`; just-in-time member as today |
| ID token with `xms_edov: true`, no `email_verified` | 401 | 302 (switch on or off) |
| `email_verified: false` (or `"false"`, `0`, any present value that is not true), switch on | 401 | 401 "The identity provider did not confirm this e-mail address." (also beside `xms_edov: true`) |
| address outside the verified domains, switch on | 401 | 401 "…outside the organisation's verified domains." (unchanged, `service.sign_in`) |
| `GET /orgs/{id}/sso` | — | adds `"trust_idp_email": false\|true` (false when nothing is configured) |
| `PUT /orgs/{id}/sso` `{kind: "oidc", …, trust_idp_email}` | — | sets it; left out keeps the stored value (as an empty `client_secret` keeps the secret); a new connection starts off |
| `PUT /orgs/{id}/sso` `{kind: "saml", …, trust_idp_email: true}` | — | 422 `validation_failed`, field `trust_idp_email` "applies to OpenID Connect only"; `false` or left out is accepted, and saving SAML clears a stored switch |
| PUT by an admin who is not the owner | 403 `forbidden` | unchanged (the SSO tab is the owner's) |

The rule, in `oidc.verify_id_token(…, trust_idp_email=False)`, after the signature, `iss`, `aud`, `azp`, `exp` and `nonce` checks:

1. no `email` string with an `@` → "The identity provider sent no e-mail address." (now checked first, so a token with neither claim gets this one);
2. `email_verified` present and not true → `NOT_VERIFIED` (the switch does not override it);
3. `email_verified` true, or `xms_edov` true, or the switch on → accepted; else `NOT_MARKED_VERIFIED`.

"True" is JSON `true`, or the string `"true"` / `"1"` or the number `1` that some providers send (`_says_true`); "absent" includes JSON `null`. The accepted address then goes through `service.sign_in` unchanged: verified domain of this organisation, link an existing account with that address, just-in-time membership, `sso.signin` audit row.

### Data

| Table / column | Type | Notes |
|---|---|---|
| `sso_connections.trust_idp_email` | `BOOLEAN`, nullable, default false | `_ADDED_COLUMNS["sso_connections"]` (its own labelled block); NULL (rows from before PF3d) reads as off. `scripts/sqlite_to_postgres.py` needs no change: it copies every model column the source has, and the column is nullable, so its precheck has nothing to flag |

### UI

| Page | What changes |
|---|---|
| `src/app/dashboard/organisation/sso/page.tsx` | a checkbox `name="trust_idp_email"` under the OpenID Connect fields, only while OpenID Connect is chosen, with `SSO_TRUST_EMAIL.label` and `.help`; sent with the OIDC settings |
| `src/app/dashboard/organisation/audit/page.tsx` | labels for `sso.trust_email_on` / `_off` from `SSO_TRUST_EMAIL.audit` |
| `src/lib/orgs.ts` | `SsoSettings.trust_idp_email`, `SsoSettingsInput.trust_idp_email?` |
| `src/lib/constants.ts` (end) | `SSO_TRUST_EMAIL = { label: "Trust the e-mail address from your identity provider", help: "Some providers never mark addresses as verified. Only addresses in your verified domains can sign in.", audit: {…} }` |

The API's refusal names the switch by the same label (`oidc.NOT_MARKED_VERIFIED`); a test reads the label from `constants.ts` and checks the two agree.

### Jobs / workers

None.

### Security and privacy

* The switch widens trust only to the organisation's own identity provider, for its own verified domains: `sign_in` still refuses every other address, and only a verified domain routes to a provider at all. That is the trust level SAML has had since PF3. Account linking stays as PF3 designed it: an existing account is joined only when its domain is verified for this organisation.
* An explicit "not verified" from the provider is always refused; the switch covers silence only.
* Only an owner can turn it on or off, and every change is in the audit log with the actor.

## Deliverables

- [x] `server/app/sso/oidc.py` (`verify_id_token`, `NOT_VERIFIED`, `NOT_MARKED_VERIFIED`, `_says_true`), `server/app/sso/service.py` (`connection_json`, `save`, `finish_oidc`), `server/app/sso/models.py`, `server/app/sso/schemas.py`, `server/app/database.py` (`_ADDED_COLUMNS` block), `server/app/routers/sso.py` (docstring)
- [x] `server/tests/mock_oidc.py` (the PF3d block and one call line in `token()`), `server/tests/test_sso_pf3d.py` (12 tests)
- [x] `src/app/dashboard/organisation/sso/page.tsx`, `src/app/dashboard/organisation/audit/page.tsx`, `src/lib/orgs.ts`, `SSO_TRUST_EMAIL` at the end of `src/lib/constants.ts`
- [x] This doc, the PF3d row in `docs/roadmap/40/README.md`, PF3's carry-over marked done, a section at the end of `README.md`

## Tests

All in `server/tests/test_sso_pf3d.py`, with `test_sso.py`'s `idp` fixture and helpers (the mock provider as the server's HTTP client), the provider played through the mock's environment switch.

| Name | Kind | Asserts |
|---|---|---|
| `test_pf3d_absent_email_verified_refused_without_switch` | pytest | `email_verified` absent, switch off → 401 `sso_failed` with `NOT_MARKED_VERIFIED`, which names the SSO tab's label (read from `constants.ts`) and "Organisation → SSO"; no account, no membership, no `sso.signin`; a browser gets the failure page with the same text |
| `test_pf3d_absent_with_switch_signs_in_jit` | pytest | switch on → 302 to `/login/sso/#token=…`; a new account, member just in time (`member.joined` via `sso.oidc`), `sso.signin` `{protocol: oidc, new_account: true}`; the same account the second time |
| `test_pf3d_explicit_false_refused_with_switch` | pytest | `false` (env), `"false"`, `0`, `"no"`, and `false` beside `xms_edov: true` → `NOT_VERIFIED` with the switch on; JSON `null` counts as absent (signed in); no `email` → its own refusal |
| `test_pf3d_xms_edov_signs_in_without_switch` | pytest | `MOCK_OIDC_XMS_EDOV=1` with `email_verified` absent → signed in with the switch off; `true`, `"true"`, `"1"`, `1` accepted; `false`, `"false"`, `0` → `NOT_MARKED_VERIFIED` |
| `test_pf3d_switch_on_outside_verified_domains_refused` | pytest | switch on, the token's address `c@gmail.com`, a subdomain, a look-alike domain → 401 "outside the organisation's verified domains"; no account, no membership |
| `test_pf3d_links_existing_account_only_in_verified_domain` | pytest | a password account in the verified domain is linked (same id, now a member); accounts in a pending (unverified) domain of the same organisation and in another domain are refused and not joined; one `sso.signin` with `new_account: false` |
| `test_pf3d_saml_unaffected_by_switch` | pytest | SAML refuses `trust_idp_email: true` (422 on that field); moving to SAML clears the switch (`sso.trust_email_off`); SAML signs in and refuses an outside address exactly as before with the stored column false or true |
| `test_pf3d_setting_owner_only_and_audited` | pytest | GET false before any connection and by default; PUT true → GET true; left out keeps it; the same value again logs nothing; one `sso.trust_email_on` and one `sso.trust_email_off` row with the owner as actor, target the organisation, `{protocol: oidc}`, also in the CSV; admin PUT and GET → 403, anonymous → 401, a non-boolean → 422; a new connection saved on logs `sso.trust_email_on` |
| `test_pf3d_column_migrated_and_copied` | pytest | a database from before PF3d (column dropped) gains the column on start, the old row reads NULL = off in `connection_json`; `sqlite_to_postgres` prechecks clean and copies NULL and true unchanged (SQLite target) |
| `test_pf3d_mock_oidc_env_switch` | pytest | the mock's default is still `email_verified: true`; `true` / `FALSE` / ` false ` / `absent`; `MOCK_OIDC_XMS_EDOV=1` adds `xms_edov: true`; the tests' TWEAKS still win; an unknown value fails loudly and the start-up note names it |
| `test_pf3d_sso_tab_source_sends_the_switch` | pytest | `SSO_TRUST_EMAIL` copy as specified, no other vendor named; the SSO tab uses it and sends `trust_idp_email` with the OIDC settings only |
| `test_pf3d_site_sso_tab_chunk_has_checkbox_copy` | build check | the scripts `out/dashboard/organisation/sso/index.html` loads carry the label, the help line and `trust_idp_email` |
| existing `test_sso*`, `test_pf14b_outbound*`, `test_ops*` | pytest | green, unchanged |

## Human test

Local API on `127.0.0.1:8000`, the site built against it and served by Try it on `127.0.0.1:3156`, the mock OIDC provider on `:8098` playing a provider that sends no `email_verified` (as PF14b's step 5, PF3's step 10).

1. Terminal 1, in `server\`: `$env:SECRET_KEY='pf3d-local-test-secret-key-0123456789abcdef'; $env:API_URL='http://127.0.0.1:8000'; $env:SITE_URL='http://127.0.0.1:3156'; $env:CORS_ORIGINS='http://127.0.0.1:3156'; .\run.bat`. Terminal 2, in `server\`: `$env:MOCK_OIDC_EMAIL_VERIFIED='absent'; .venv\Scripts\python.exe -m uvicorn tests.mock_oidc:app --port 8098` → it prints `mock oidc: ID tokens follow MOCK_OIDC_EMAIL_VERIFIED=absent`. Terminal 3, in the worktree: `$env:NEXT_PUBLIC_AUTH_URL='http://127.0.0.1:8000'; npm run build`, then `$env:AUTOPILOT_TASK_ID='T56'; powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` → it prints `http://127.0.0.1:3156/`.
2. Sign up as `owner@example.com` → Dashboard → Organisation → create "Studio North". Terminal 4, in `server\`: `.venv\Scripts\python.exe scripts\verify_org_domain.py --org studio-north --domain example.com` → `studio-north: example.com verified`.
3. Organisation → SSO: OpenID Connect, issuer `http://127.0.0.1:8098`, client id `truebex-local`, secret `mock-oidc-secret`. Under the three fields there is an unticked box "Trust the e-mail address from your identity provider" with "Some providers never mark addresses as verified. Only addresses in your verified domains can sign in." beneath it (choosing SAML 2.0 hides it). Leave it unticked, Enabled → Save → "Saved."
4. Sign out → Log in → "Continue with SSO" → `c@example.com` → Continue → a dark page "Single sign-on did not finish": "Your identity provider did not mark this address as verified. An owner can turn on “Trust the e-mail address from your identity provider” in Organisation → SSO." and "Back to sign in".
5. Back to sign in → log in as `owner@example.com` → Organisation → SSO → tick the box → Save → "Saved." (reload: still ticked). Sign out → "Continue with SSO" with `c@example.com` → back on the dashboard, signed in as c@example.com (the address bar passes through `/login/sso/`).
6. Sign in as `owner@example.com` → Organisation → Audit log → a row "Trusted the identity provider's e-mail" by owner@example.com, kind `sso.trust_email_on`, details `protocol: oidc`. Members lists c@example.com as a Member.
7. SSO tab → untick → Save → "Saved." Sign out → "Continue with SSO" with `c@example.com` → the failure page of step 4 again. As owner, Audit log → "Stopped trusting the identity provider's e-mail" above the step-6 row.
8. Optional, Entra's own claim: Ctrl+C in terminal 2, `$env:MOCK_OIDC_XMS_EDOV='1'`, start the mock again → "Continue with SSO" with `c@example.com` signs in with the box unticked. Then `Remove-Item Env:MOCK_OIDC_EMAIL_VERIFIED, Env:MOCK_OIDC_XMS_EDOV` before other tests.

## Risks / traps

* **Merging with PF3c (T53).** T53 changes `discover()`, the module docstring and the constants block of `oidc.py`, and the docstring, imports and discovery of `mock_oidc.py`. This branch keeps out of those lines: its `oidc.py` edits are a block above `verify_id_token` and the function itself; its mock edit is one call line in `token()` and a block at the end of the file that imports `os` locally (T53 adds a top-level `import os`). `test_sso_pf3d.py` imports `test_sso.py`'s fixture and helpers, so a helper renamed there needs the same rename here.
* **An Entra set-up that sends no `email` at all** (no `email` optional claim, no mailbox) still gets "The identity provider sent no e-mail address."; the organisation adds the `email` claim in its app registration.
* **Browsers log the refusal.** The failure page answers 401 (as since PF3), and Chromium logs "Failed to load resource: … 401" for it; that line is the refusal itself, not a page error.
* RAM: no `next dev`. Step 1's build is the static export. The verify gate's `out/` is built against `.env.local`'s production API, so step 1 rebuilds it.

## As-built

* **Date, branch, commits:** 2026-10-12, `ap/t56-pf3d-sso-openid-connect-sign-in` from `master` 6ef7928. `b133f76`: the rule, the column, the settings, the mock switch, the tests and the site. A second commit: this doc, the tracker row, PF3's carry-over note, the README section.
* **Counts:** test functions in `server/tests` 616 → 628 (12 new, all in `test_sso_pf3d.py`); every name in the Tests table exists verbatim. `scripts/autopilot-verify.ps1` green (lint, build, pytest; see the report). No new page, so `out/` has the same pages; the SSO and audit tabs' chunks change.
* **Self-test beyond pytest:** the API under uvicorn (`API_URL=http://127.0.0.1:18056`, a scratch SQLite database), `mock_oidc` under uvicorn on `127.0.0.1:18156` with `MOCK_OIDC_EMAIL_VERIFIED=absent`, `out/` built with `NEXT_PUBLIC_AUTH_URL=http://127.0.0.1:18056` and served like `autopilot-serve.ps1` on :3156, headless Edge over CDP: the owner filled the SSO tab and saved with the box unticked ("Saved.", reload unticked, the box absent under SAML 2.0); "Continue with SSO" as c@example.com ended on "Single sign-on did not finish" with the new message (and JSON 401 `sso_failed` with the same detail over HTTP; nobody joined); the owner ticked the box and saved; "Continue with SSO" passed through `/login/sso/#token=…` to `/dashboard/` signed in as c@example.com, a member; the audit tab listed "Trusted the identity provider's e-mail" by owner@example.com; unticked → refused again and "Stopped trusting the identity provider's e-mail" listed. Browser console: nothing but serve-out.py's `__next.*.txt` prefetch 404s and the two refusals' own 401 page loads (Risks).
* **Deviations and decisions:**
  1. *An explicit false wins.* `email_verified` present and not true is refused even with `xms_edov: true` beside it and with the switch on: the provider says the address is not verified. The task listed `xms_edov` as a plain "or"; the contradicting case was not named, and refusing is the safe reading.
  2. *What counts as true and as absent:* JSON `true`, `"true"`, `"1"` and `1` for both claims (the old check took `true` and `"true"` for `email_verified`); JSON `null` counts as absent.
  3. *The missing-e-mail check now runs first*, so a token with neither claim says "sent no e-mail address" rather than asking for the switch.
  4. *SAML refuses the switch on* (422 `validation_failed`, field `trust_idp_email`, "applies to OpenID Connect only") rather than ignoring it, so a client's mistake is visible; `false` or left out is accepted, and saving SAML clears a stored switch (logged as `sso.trust_email_off` when it was on). SAML sign-in never reads the column.
  5. *Left out of a PUT, the switch keeps its value*, as an empty `client_secret` keeps the secret, so a client that does not know the field (an older cached SSO tab) cannot turn it off by saving.
  6. *The column is nullable* (`BOOLEAN`, NULL = off), as `_ADDED_COLUMNS` columns are, so old rows need no backfill and the Postgres copy's precheck has nothing to flag.
  7. *Audit:* `sso.trust_email_on` / `sso.trust_email_off`, only when the value changes, actor the owner, target the organisation, details `{protocol}`; `sso.configured` is unchanged. The audit tab's labels come from `SSO_TRUST_EMAIL.audit`.
  8. *The mock's switch* is read at each token (so `monkeypatch.setenv` works), refuses an unknown value with a 500 that names the variable, and prints the active mode at start for the human test.
  9. *The site build check* lives in `test_sso_pf3d.py`, as the task asked, rather than a `test_site_pf3d.py`. The copy ships in the shared constants chunk and the form in the page's own chunk; the check reads the scripts the SSO tab's HTML loads.
* **PF3c landed meanwhile:** `master` moved to 3a18a37 (PF3c, Autopilot T53) during this task. A trial merge (`git merge-tree`, nothing committed) conflicts only in the two append-at-end files, `README.md` and this folder's tracker; `oidc.py` and `mock_oidc.py` merge cleanly. On that merged tree `test_sso_pf3d.py`, `test_sso.py`, `test_pf3c_sso_https.py` and `test_pf14b_outbound.py` pass (39 passed; the build check skipped there for want of `out/`). The human test works with PF3c's https rule: the mock's plain-http endpoints on 127.0.0.1 stay allowed while the API runs on loopback.
* **Contract *implemented by* rows:** none (no contract document).
* **Carry-over:** none. PF3's carry-over line is marked done.
