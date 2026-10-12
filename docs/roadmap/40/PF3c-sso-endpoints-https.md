# PF3c — SSO: an OpenID Connect provider's endpoints must be https, like its issuer (launch priority 1)

**Needs merged:** PF3 (OIDC sign-in, `tests/mock_oidc.py`), PF14b (the pinned client, `private_issuers_allowed()`); both on `master` 6ef7928. **Unblocks:** PF14b's carry-over to PF3 ("require https for the discovery document's `jwks_uri` and `token_endpoint`; they are already limited to public addresses"). **Contract:** none. No endpoint, request or response shape changes; a refusal is the existing 401 `sso_failed`.

## Status

**Built on branch `ap/t53-pf3c-sso-an-oidc-providers-endpo` (2026-10-12, Autopilot T53); see As-built.** Before this task, on `master` 6ef7928, the gap looked like this:

| Where (master 6ef7928) | What it did |
|---|---|
| `server/app/sso/oidc.py:64` `issuer_is_acceptable` | The issuer must be https on a public address. Plain http is allowed only to 127.0.0.1 / localhost / ::1 while `private_issuers_allowed()` (API on loopback, or `SSO_ALLOW_PRIVATE_ISSUERS`). |
| `server/app/sso/oidc.py:84` `discover`, `:100` | It checked only that `authorization_endpoint`, `token_endpoint` and `jwks_uri` are strings, then cached the document (`:103`) for an hour. |
| `server/app/sso/oidc.py:172` `exchange_code` | It POSTs the client secret (Basic auth or form), the authorisation code and the PKCE verifier to `token_endpoint`. If that was `http://`, all of it went in clear text. |
| `server/app/sso/oidc.py:107` `_keys`, `:113` | It fetches the signing keys from `jwks_uri`. Over http, someone on the path can swap the keys and then sign an ID token of their own. |
| `server/app/sso/oidc.py:152` `authorize_url` | It sends the browser to `authorization_endpoint`. Over http, `state`, the PKCE challenge and the login hint travel in clear text, and the provider's sign-in page can be replaced on the way. |

PF14b's pinned client (`app.net.outbound`) already kept every call on public addresses, but nothing required https.

## Goal

An organisation's identity provider is always reached over https: the browser's sign-in page, the token request that carries the organisation's client secret, and the keys that vouch for every ID token. A provider whose discovery document names a plain-http endpoint is refused at "Continue with SSO" with a message that names the field, before anything secret is sent. The local mock provider on the owner's PC keeps working, just as the issuer rule already allows.

## Read first

* `docs/roadmap/40/00-contract.md` P.2 to P.4.
* As-built of `PF3-organisations-seats-and-sso.md` (OIDC, the mock providers) and `PF14b-outbound-requests-pinned.md` (the pinned client, `private_issuers_allowed()`, the carry-over this closes).
* `server/app/net/outbound.py`, `server/app/sso/oidc.py`, `server/app/sso/service.py` (`start`, `finish_oidc`), `server/app/routers/sso.py` (`_failure`).
* `server/tests/test_sso.py` (`idp` fixture), `server/tests/test_pf14b_outbound.py` (`local_idp`), `server/tests/mock_oidc.py`, `server/tests/mock_paddle.py` (`MOCK_PADDLE_DROP`, the switch pattern).

## Scope

**In:**

1. `discover()` refuses a document whose `authorization_endpoint`, `token_endpoint` or `jwks_uri` is not https. The one exception is the issuer's: plain http, only while `private_issuers_allowed()`, and only to a host in `LOCAL_HOSTS` (the local mock provider). The failure is the existing `fail(…)` (401 `sso_failed`) and names the field. Nothing is cached, and neither the token endpoint nor the keys are called.
2. Any other endpoint the code calls from the document follows the same rule. Checked: `userinfo_endpoint` and `end_session_endpoint` are not called (nor is any other URL from the document). `oidc.ENDPOINTS` is the one list of the document URLs the code uses, and a test fails if the SSO code reads an `*_endpoint` / `*_uri` / `*_url` key that is not on it.
3. `tests/mock_oidc.py` gains a switch, `MOCK_OIDC_HTTP_ENDPOINT`, that makes its discovery document name an http endpoint on a host that is not local (`localtest.me`), for the human test.

**Out (and where it goes):**

* SAML: the metadata is pasted XML and the sign-in URL is a browser redirect, so the API never fetches either (PF14b's As-built).
* The fixed provider hosts (Paddle, Stripe, Wayl, Anthropic).
* Any change to the issuer rule itself (`issuer_is_acceptable` is unchanged).

## Design

**API:** no endpoint changes. What is visible:

| Where | Before | After |
|---|---|---|
| `GET /auth/sso/start`, public https issuer whose document gives `token_endpoint: http://…` | 302 to the provider; the callback then POSTed the client secret and the code over http | 401 `sso_failed` "The identity provider's discovery document must give token_endpoint as an https URL."; the browser gets the "Single sign-on did not finish" page with the same sentence |
| the same with `jwks_uri` / `authorization_endpoint` over http | 302; keys fetched over http at the callback / the browser sent to an http sign-in page | 401 `sso_failed` naming `jwks_uri` / `authorization_endpoint` |
| `GET /auth/sso/oidc/callback` for a sign-in started before the document changed (the hour's cache over) | the token request went to the http endpoint | 401 `sso_failed` naming the field; no token request |
| API on loopback, the mock at `http://127.0.0.1:8098` (endpoints http on 127.0.0.1) | signs in | signs in (unchanged) |
| `SSO_ALLOW_PRIVATE_ISSUERS=true`, an http endpoint on `localtest.me` or `192.168.1.20` | allowed (the pinned client lets private addresses through in that mode) | 401 `sso_failed` naming the field; plain http only to 127.0.0.1 / localhost / ::1 by name |

**The rule** (`oidc.endpoint_is_acceptable(url)`): parse the URL (a malformed one is refused). There must be a host. https is accepted on any host, because the pinned client still checks the address when the endpoint is called. http is accepted only when the host is in `LOCAL_HOSTS` (127.0.0.1, localhost, ::1, case-insensitive) and `private_issuers_allowed()`. Every other scheme is refused. `discover()` applies it to each of `oidc.ENDPOINTS` = (`authorization_endpoint`, `token_endpoint`, `jwks_uri`) after the "is a string" check and before the document is cached, so a refused document is fetched again next time and never used.

**Data:** none. **UI:** none. The site's "Continue with SSO" form already shows the API's `detail` (`AuthForm.tsx` `SsoPanel`), and the browser failure page shows it too (`routers/sso.py` `_failure`). **Jobs:** none.

**Security and privacy:** the token request carries the organisation's client secret and the authorisation code, so it must never go over plain http to anything but this computer. The same holds for the keys that vouch for every ID token and for the page where people type their password. The local exception is by host name, not by address. A public name that answers 127.0.0.1 (`localtest.me`), or a LAN address, does not qualify even with `SSO_ALLOW_PRIVATE_ISSUERS` on, because only the names 127.0.0.1, localhost and ::1 cannot be someone else's machine.

## Deliverables

- [x] `server/app/sso/oidc.py`: `ENDPOINTS`, `endpoint_is_acceptable()`, the check in `discover()`
- [x] `server/tests/mock_oidc.py`: `MOCK_OIDC_HTTP_ENDPOINT` (comma-separated field names), `HTTP_HOST` (`localtest.me`), `CALLS` (every request, for tests)
- [x] `server/tests/test_pf3c_sso_https.py` (10 tests)
- [x] This doc, the PF3c row in `docs/roadmap/40/README.md`, an "SSO endpoints over https (PF3c)" section at the end of `README.md`

## Tests

All in `server/tests/test_pf3c_sso_https.py`. The public-issuer tests use `test_sso.py`'s `idp` fixture: the mock provider is the server's HTTP client, and `idp.test` resolves to a public address. The local ones run `tests/mock_oidc.py` on a loopback port over PF14b's pinned connection (`test_pf14b_outbound.py`'s `local_idp`), as the human test does.

| Name | Kind | Asserts |
|---|---|---|
| `test_discovery_refuses_http_token_endpoint` | pytest | `https://idp.test` (public) has a sign-in pending. Its document then gives `token_endpoint` as `http://idp.test/token` and the cache is cleared. Start answers 401 `sso_failed` naming the field (JSON, and the HTML page); the pending callback answers 401 naming it. Nothing cached; the provider sees three discovery fetches and no token or keys request. On master: start answers 200 with the provider URL. |
| `test_discovery_refuses_http_jwks_uri` | pytest | the same for `jwks_uri` |
| `test_discovery_refuses_http_authorization_endpoint` | pytest | the same for `authorization_endpoint` |
| `test_local_mock_provider_still_signs_in` | pytest | `API_URL` on loopback, setting off: the mock at `http://127.0.0.1:<port>` with http 127.0.0.1 endpoints signs a person in end to end; its `POST /token` and `GET /jwks` were called |
| `test_private_issuers_switch_keeps_http_local_only` | pytest | `SSO_ALLOW_PRIVATE_ISSUERS` on, API not on loopback. Each of the three fields as http on `localtest.me` (resolved to 127.0.0.1) and on `192.168.1.20`: 401 naming the field, only the discovery fetch, nothing cached. Token endpoint and keys on `http://localhost:<port>`: signs in. |
| `test_endpoint_rule_matches_the_issuer_exception` | pytest | `endpoint_is_acceptable`: https on any host (any case); http to 127.0.0.1 / localhost / LOCALHOST / [::1] only in private mode (API on loopback, or the setting); http to public, `nip.io`, `localtest.me` or LAN hosts, other schemes, no host, relative or malformed URLs always refused |
| `test_every_endpoint_the_code_calls_is_checked` | pytest | an `ast` scan of `app/sso/*.py` and `app/routers/sso.py`: the only `*_endpoint` / `*_uri` / `*_url` keys read from a mapping are `oidc.ENDPOINTS`; `userinfo_endpoint` and `end_session_endpoint` are not read |
| `test_mock_switch_names_an_http_endpoint[…]` (3) | pytest | `MOCK_OIDC_HTTP_ENDPOINT=<field>`: that field is `http://localtest.me:<port><path>`, the others stay on the issuer; an unknown field name raises |
| existing `test_sso.py` (9), `test_pf14b_outbound.py` (9) | pytest | green, unchanged. `test_sso.py`'s fixture already serves https endpoints (`https://idp.test`), so nothing there needed changing. |

## Human test

Local API on `127.0.0.1:8000`, the site built against it and served by Try it on `http://127.0.0.1:3153/`, the mock OIDC provider on `:8098`.

1. Terminal 1, in `server\`: `$env:SECRET_KEY='pf3c-local-test-secret-key-0123456789abcdef'; $env:API_URL='http://127.0.0.1:8000'; $env:SITE_URL='http://127.0.0.1:3153'; $env:CORS_ORIGINS='http://127.0.0.1:3153'; .\run.bat`.
2. Terminal 2, in `server\`: `$env:MOCK_OIDC_HTTP_ENDPOINT='token_endpoint'; .venv\Scripts\python.exe -m uvicorn tests.mock_oidc:app --port 8098`. The first line says `mock oidc: discovery gives token_endpoint as http://localtest.me (MOCK_OIDC_HTTP_ENDPOINT)`.
3. Terminal 3, in the worktree: `$env:NEXT_PUBLIC_AUTH_URL='http://127.0.0.1:8000'; npm run build`, then `$env:AUTOPILOT_TASK_ID='T53'; powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1`. It prints `http://127.0.0.1:3153/` (the task id fixes the port that terminal 1's `SITE_URL` and `CORS_ORIGINS` name).
4. Open it, Sign up as `owner@example.com`, then Dashboard → Organisation → create "Studio North". Terminal 4, in `server\`: `.venv\Scripts\python.exe scripts\verify_org_domain.py --org studio-north --domain example.com`. On the SSO tab choose OpenID Connect, issuer `http://127.0.0.1:8098`, client id `truebex-local`, secret `mock-oidc-secret`, enabled → Save. It saves; the save does not contact the provider.
5. Sign out → Log in → "Continue with SSO" → `c@example.com` → Continue. The form stays on the page and shows "The identity provider's discovery document must give token_endpoint as an https URL." Terminal 2 shows only `GET /.well-known/openid-configuration`, with no `POST /token` and no `GET /jwks`.
6. Optional: Ctrl+C in terminal 2 and repeat steps 2 and 5 with `jwks_uri`, then `authorization_endpoint`. Each time the message names that field.
7. Ctrl+C in terminal 2, then `Remove-Item Env:MOCK_OIDC_HTTP_ENDPOINT; .venv\Scripts\python.exe -m uvicorn tests.mock_oidc:app --port 8098`. "Continue with SSO" → `c@example.com` → Continue. The browser passes through the mock and lands on the dashboard, signed in as c@example.com. Terminal 2 now shows `GET /authorize…`, `POST /token` and `GET /jwks`.

## Risks / traps

* **A provider that really publishes http endpoints** (rare; OIDC Discovery requires TLS) can no longer be used. Its admin sees the field named at "Continue with SSO", not at save, because saving does not fetch the document. That was already the case for the existing "has no token_endpoint" check.
* **Name, not address.** The local exception compares the host name with 127.0.0.1 / localhost / ::1. A mock reached as `127.0.0.2` or by the PC's LAN name needs https, as an issuer there already does.
* **Cache.** A document accepted before this change stays cached for up to an hour in a running API. A restart, which any deploy does, clears it.
* **Seams.** `test_sso.py` swaps `oidc.http_client` for a `TestClient`, so its endpoints are never resolved. The scheme check runs before any call, so it does not depend on that seam.
* RAM: no `next dev`. The human test's build is the static export.

## As-built

* **Date, branch, commits:** 2026-10-12, `ap/t53-pf3c-sso-an-oidc-providers-endpo` from `master` 6ef7928. `7560267`: the rule in `oidc.py`, the mock switch and the tests. A second commit: this doc, the tracker row and the README section.
* **Counts:** pytest 622 → 632 collected (10 new in `test_pf3c_sso_https.py`; the existing `test_sso.py` 9 and `test_pf14b_outbound.py` 9 green and unchanged). `scripts/autopilot-verify.ps1` green in 948 s: lint clean, the static build, pytest 616 passed + 16 skipped (the Postgres-only tests) in 630 s. Every name in the Tests table exists verbatim. On master's `oidc.py` the three refusal tests, the private-mode test, the rule test and the scan test fail (start answers with the provider URL; `ENDPOINTS` and `endpoint_is_acceptable` are missing). The local sign-in test and the three mock-switch tests pass there, as they should. No page or copy change.
* **Self-tests beyond pytest:**
  * *Real processes:* the API under uvicorn on `127.0.0.1:18053` with its own SQLite file, and the mock under uvicorn on `:18153` with `MOCK_OIDC_HTTP_ENDPOINT` set to each field in turn. Each time start answered 401 `sso_failed` naming the field (JSON, and the HTML failure page), and the mock's access log showed only discovery fetches. Without the switch the same person signed in (302 to `/login/sso/#token=…`, `/auth/me` = c@example.com), and the log showed `POST /token` and `GET /jwks`.
  * *Headless Edge over CDP:* `out/` built with `NEXT_PUBLIC_AUTH_URL` pointing at that API and served on `:3153`. Log in → "Continue with SSO" → `c@example.com` showed "The identity provider's discovery document must give token_endpoint as an https URL." in the form (the only console entry was the expected 401). Without the switch, the browser landed on `/dashboard/` with a session.
* **Deviations and decisions:**
  1. *Message:* "The identity provider's discovery document must give `<field>` as an https URL." It is API text like the other `fail(…)` messages in `oidc.py`, so it is not in `constants.ts`. The site shows the API's `detail` as it is.
  2. *Optional endpoints are not checked:* a document whose `userinfo_endpoint` or `end_session_endpoint` (or `registration_endpoint`, `revocation_endpoint`, …) is http is still accepted, because the API never calls them or sends the browser there. Refusing them would lock out a provider for nothing. `oidc.ENDPOINTS` lists what is used, and `test_every_endpoint_the_code_calls_is_checked` fails if the SSO code starts reading another document URL without adding it there.
  3. *`authorization_endpoint` refused at the callback too:* `discover()` checks all three whichever call needs the document, so a sign-in in flight when the document turns to http fails at the callback instead of finishing.
  4. *Mock host:* the switch's host is `localtest.me`, a public name that answers 127.0.0.1. On master, with the API on loopback, the pinned client allows loopback addresses, so the token request would have gone to the mock through that name over plain http. That is reasoning: this run tried only the new code against the mock. Now it is refused before anything is sent.
  5. *`test_sso.py` unchanged:* its `idp` fixture already serves `https://idp.test/…` endpoints (the mock builds them from the issuer it is reached on), so no fixture served an http endpoint for a public host.
* **Contract documents:** none touched (no endpoint in a contract changes).
* **Cut:** nothing from Scope: In.
* **Carry-over:** none.
