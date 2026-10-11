# PF14b — Outbound requests pinned to their checked addresses: media, feeds, webhooks, SSO (launch priority 1)

**Needs merged:** PF3, PF7, PF8, PF12, PF14 (all on `master` at 842768e). **Unblocks:** PF8's carry-over to PF14 ("pinning the resolved address in the fetchers"); PF12 As-built 9 ("the HTTP client resolves the name again (no address pinning)"). **Contract:** none. No endpoint, request or response shape changes.

## Status

**Built on branch `ap/t35-pf14b-outbound-requests-pinned-t` (2026-10-11); see As-built.** Before this task, on `master` 842768e, four callers sent requests to URLs that someone else chose. Each one checked the address with one DNS lookup, then let httpx look the name up again when it connected:

| Caller | Where (master 842768e) | Gap |
|---|---|---|
| Media fetcher (feed rows' `image_urls`, `geometry_url`; PF7) | `server/app/market/media.py:74` `_public_address`, `:93` `HttpFetcher`, `:110` `httpx.Client` | resolve + check, then a second resolution at connect (DNS rebinding reaches the VM's own network) |
| Feed pull (PF8 5.12) | `server/app/supplier/feeds.py:48` `public_host = media._public_address`, `:241`, `:247` | the same, per redirect hop |
| Webhook delivery (PF12) | `server/app/webhooks/delivery.py:51` `client_factory`, `:64` `urls.check(endpoint.url)` | checked at each delivery, then `client_factory()` resolves again |
| OIDC discovery, JWKS, token (PF3) | `server/app/sso/oidc.py:27` `http_client` (plain `httpx.Client`), `:45` `issuer_is_acceptable`; `server/app/sso/service.py:119-120` | no address check at all; `http://127.0.0.1` / `localhost` issuers accepted in every environment, so in production an organisation admin could make the API call its own loopback services; an https issuer whose name resolves to a private address accepted too |

`_public_address` also let through addresses that are not global although Python 3.12 does not flag them private: 100.64.0.0/10 (shared address space), multicast that Python counts as global (224.0.0.0/4, ff0e::/16), IPv6 site-local (fec0::/10), and the IPv4-mapped, NAT64 and 6to4 forms of a private IPv4.

## Goal

When the API fetches a supplier's feed or images, delivers a webhook, or talks to an organisation's identity provider, it connects only to the public internet address it checked, never to a second answer that DNS gives a moment later. A name that points at the VM's own network, the cloud metadata address or a private office network is refused before anything is sent. The supplier, the developer or the organisation admin still gets the same clear error as before. TLS still checks the certificate for the name they typed. The local mock identity provider keeps working when the API runs on the owner's PC.

## Read first

* `docs/roadmap/40/00-contract.md` P.2 to P.4.
* As-built of `PF8-…md` (feeds and their request-forgery check, carry-over to PF14), `PF7-…md` (media), `PF12-…md` (As-built 9: webhook URLs, "checked again at each delivery, against DNS rebinding"), `PF3-…md` (OIDC, `server/tests/mock_oidc.py`, the human test's issuer `http://127.0.0.1:8098`).
* `server/app/webhooks/urls.py`, `server/app/market/media.py`, `server/app/supplier/feeds.py`, `server/app/webhooks/delivery.py`, `server/app/sso/oidc.py`, `server/app/sso/service.py`.
* httpx 0.28.1 `HTTPTransport` and httpcore 1.0.9 `ConnectionPool(network_backend=…)`, `HTTPConnection._connect` (SNI = the origin's host).
* `.claude/skills/truebex-deploy/SKILL.md` (Secrets and switches), `server/tests/test_deploy_skill.py`.

## Scope

**In:**

1. One outbound module, `server/app/net/outbound.py`, used by every caller below. It resolves a host once and refuses the request unless every address is global unicast: `ipaddress` `is_global`, plus explicit refusals for private, loopback, link-local, multicast, reserved, unspecified, IPv6 site-local and 100.64.0.0/10. The IPv4-mapped (::ffff:0:0/96), NAT64 (64:ff9b::/96) and 6to4 (2002::/16) forms are judged by the IPv4 address they reach. It then connects to one of the checked addresses and never looks the name up again. TLS verifies the certificate against the original host name, with SNI and the Host header carrying the name.
2. Every redirect hop is checked again. Media and feeds already follow redirects by hand, and each hop goes through the module. The module's client follows none, and webhooks still treat a 3xx as a failure.
3. `media.py`, `supplier/feeds.py` and `webhooks/delivery.py` use the module. `urls.check` stays at save time (a clear 422). A delivery checks only the URL's form and then sends over the pinned connection. A refusal there keeps the save-time reason. Error codes and messages that the tests and the UI read are unchanged.
4. SSO: discovery, JWKS and token calls use the module. Loopback or private issuers are accepted only when the API itself runs on loopback (the host of `API_URL` is 127.0.0.1, localhost or ::1) or under `SSO_ALLOW_PRIVATE_ISSUERS` (off by default). Production refuses them with the `issuer` field error (422 `validation_failed`) at save time and with 401 `sso_failed` at sign-in.
5. The new setting in `server/app/config.py`, `server/.env.example`, `infra/secrets/server.env.example` and the deploy skill's secrets table.
6. `server/scripts/try_outbound.py`: a probe that sends one GET over the module and prints the lookup, the verdict on each address, the address it dials and the answer (for the human test).

**Out (and where it goes):**

* SAML: the metadata is pasted XML (no fetch), and the SAML sign-in URL is a browser redirect. `service.py:143`'s `http://127.0.0.1` / `localhost` sign-in URLs stay accepted (the API never requests them).
* Fixed provider hosts the code names itself: Paddle, Stripe, Wayl, Anthropic (`billing/*_provider.py`, the `stripe` and `anthropic` SDKs).
* Operator-configured internal servers: `server/app/ai/servers.py` and `server/app/ai/adapters/selfhosted.py` reach the render or AI PC on purpose. So do `PADDLE_API_BASE` / `WAYL_API_BASE` / `ANTHROPIC_BASE_URL` (local mocks) and `licence/signing.py`'s `RELEASE_PUBLIC_KEYS` URL (an operator setting).
* `server/app/ops.py`'s health checks and alert push (`ALERT_PUSH_URL`, operator-set).
* The OIDC `jwks_uri` and `token_endpoint` must be public (the module checks them), but they may still be plain `http` on a public address. Requiring https for them is OIDC hardening, not request forgery; it stays a PF3 follow-up.

## Design

**API:** no endpoint changes. The visible behaviour:

| Where | Before | After |
|---|---|---|
| `PUT /orgs/{id}/sso`, issuer `http://127.0.0.1:8098`, API on a public address | 200 | 422 `validation_failed`, field `issuer`: "an https URL on a public internet address" |
| the same, API on 127.0.0.1 / localhost (local trial) | 200 | 200, message unchanged when refused ("an https URL (or http://127.0.0.1 for a local test provider)") |
| `PUT /orgs/{id}/sso`, `https://<name resolving to 10.x>` | 200 | 422 on `issuer` |
| `GET /auth/sso/start` for an organisation whose issuer is not public | 302 to the issuer (the API called it) | 401 `sso_failed` "The identity provider is not on a public internet address."; the browser gets the "Single sign-on did not finish" page; nothing is sent to the issuer |
| webhook delivery to a name that now resolves to a private address | `refused: a host that resolves to public addresses only` (check), then a second lookup at connect | the same text, from the connection itself; no second lookup |
| feed pull / media fetch, a hop that resolves to a private address | `the host is not a public internet address` / `bad_url` | unchanged text, raised by the connection |

**The module** (`app/net/outbound.py`):

* `is_public(address)`: the rule in Scope 1. `allowed(address, private=, loopback=)` widens it for local trials: loopback and private-network unicast (RFC 1918, fc00::/7, 100.64.0.0/10), never link-local (169.254.169.254), multicast, reserved or unspecified.
* `resolve(host)`: `socket.getaddrinfo`, every address once, in the resolver's order (the tests' seam). `check_host(host, private=, loopback_names=)` makes one lookup and either returns the addresses or raises `Refused(host, UNRESOLVED | NOT_PUBLIC)`. `public_host(host)` is the boolean form, used at save time by feeds (through `media._public_address`) and SSO.
* `client(timeout=, private=, loopback_names=)`: an `httpx.Client(transport=PinnedTransport(…), follow_redirects=False, trust_env=False)`. `PinnedTransport` is httpx's `HTTPTransport` over an httpcore `ConnectionPool` built with `network_backend=_PinnedBackend`. Its `connect_tcp(host, port, …)` does lookup, check and connect in one step, and dials the checked literal addresses (up to 4, in order) through `connect()` (the seam), so no lookup happens at connect time. httpcore then runs TLS with `server_hostname` = the URL's host, so SNI and certificate verification use the name and httpx's Host header carries it. Every connection the pool opens goes through this, every redirect hop (a new request) and every retry included. `trust_env=False` and passing a transport mean no proxy from the environment (a proxy would resolve the name itself) and no `.netrc`.
* `Refused` subclasses `httpx.ConnectError`, so code that knows only httpx still sees a failure. httpx re-raises a non-httpcore exception from the pool unchanged, so callers catch `Refused` first and keep their own wording.

**Callers:**

* `media.HttpFetcher`: each hop through `outbound.client`; `Refused` → `MediaError("bad_url", "the host is not a public internet address")`. Its `resolver=` argument is now an optional extra name check (tests); `_public_address(host)` = `outbound.public_host(host)`.
* `feeds.HttpFeedFetcher`: each hop through `outbound.client`; `Refused` → `PullError("the host is not a public internet address")`. `feeds.public_host` still checks a URL being registered (5.12, 422).
* Webhooks: `urls.resolve` delegates to `outbound.resolve`, and `urls._public` is `outbound.is_public`, so save time uses the same stricter rule. `delivery._post` runs `urls.check(url, resolve_host=False)`: the form and literal addresses, no lookup. Then it sends through `client_factory()` = `outbound.client(timeout=WEBHOOKS_TIMEOUT_S, loopback_names=LOCAL_HOSTS if WEBHOOKS_ALLOW_HTTP_LOCAL else ())`. `Refused` → `refused: ` + `urls.refusal(exc)` (the save-time text).
* SSO: `oidc.private_issuers_allowed()` = `SSO_ALLOW_PRIVATE_ISSUERS` or the host of `API_URL` in (127.0.0.1, localhost, ::1). `http_client()` = `outbound.client(timeout=10, private=private_issuers_allowed())`. `issuer_is_acceptable`: with private issuers allowed, any https host or http to a loopback name (as before); otherwise https and `outbound.public_host(host)`. `issuer_requirement()` gives the field error's text. `discover`, `_keys` and `exchange_code` map `Refused` to `fail(…)` (401 `sso_failed`) before the generic 502 `sso_unavailable`.

**Data:** none. **UI:** none. The dashboard shows the API's messages as before. **Jobs:** `market.feeds.pull`, `webhooks.deliver` unchanged apart from the client.

**Security and privacy:** the refusal messages name the host the person entered, never the address it resolved to (a split-horizon resolver's internal answers stay private). The local escape hatches stay narrow. `WEBHOOKS_ALLOW_HTTP_LOCAL` lets only the names 127.0.0.1 / localhost / ::1 reach loopback, never a public name that rebinds. SSO's private mode follows where the API runs, or an explicit setting that the deploy skill says stays `false` on the VM.

## Deliverables

- [x] `server/app/net/__init__.py`, `server/app/net/outbound.py`
- [x] `server/app/market/media.py`, `server/app/supplier/feeds.py`, `server/app/webhooks/urls.py`, `server/app/webhooks/delivery.py`, `server/app/sso/oidc.py`, `server/app/sso/service.py` on the module
- [x] `SSO_ALLOW_PRIVATE_ISSUERS`: `server/app/config.py` (end block), `server/.env.example` (end), `infra/secrets/server.env.example` (end), `.claude/skills/truebex-deploy/SKILL.md` secrets table
- [x] `server/scripts/try_outbound.py` (the probe)
- [x] `server/tests/test_pf14b_outbound.py` (9 tests); `server/tests/test_sso.py` fixture and `server/tests/test_pf12_webhooks.py::test_webhooks_refuse_private_address_at_delivery` updated (As-built)
- [x] This doc, the PF14b row in `docs/roadmap/40/README.md`, a "Outbound requests (PF14b)" section at the end of `README.md`

## Tests

All in `server/tests/test_pf14b_outbound.py`, with no real network. `FakeNet` answers DNS from a table (`outbound.resolve`), takes the module's connections (`outbound.connect`) to an in-process TLS server, and trusts that server's test CA (`outbound.tls_context`). The CA and a certificate for the test names are made per run with `cryptography`. The SSO tests run `tests/mock_oidc.py` under uvicorn on a loopback port, as the human test does.

| Name | Kind | Asserts |
|---|---|---|
| `test_outbound_refuses_non_global_addresses` | pytest | 40 addresses refused by `is_public`, each also refused as a name's answer through a client with nothing dialled: loopback, RFC 1918 and fc00::/7, link-local, multicast (v4 and v6, also the ones Python calls global), reserved, broadcast, unspecified, 100.64.0.0/10, documentation and benchmarking, IPv6 site-local, the IPv4-mapped / NAT64 (well-known and local-use) / 6to4 forms of 127/8, 10/8, 169.254/16 and 100.64/10, Teredo. Public v4, v6, mapped, NAT64 and 6to4 forms of a public IPv4 allowed. A mixed answer, an unresolvable name, literal addresses in URLs refused; `Refused` is an `httpx.ConnectError`; the `private` and `loopback_names` modes |
| `test_outbound_connects_to_the_checked_address` | pytest | the resolver answers a public address first and 127.0.0.1 after: the request reaches the public address after exactly one lookup; the next connection looks up again and dials nothing; with several addresses the next one is tried |
| `test_tls_name_kept` | pytest | the connection goes to the address, SNI and Host carry `public.example.com` (and `:8443` when the URL names a port); a name the certificate does not carry fails verification at the same address |
| `test_media_redirect_to_private_refused` | pytest | `HttpFetcher` follows a hop to another public host; a hop to a name on 10.0.0.7, to 169.254.169.254 or to `http://` is `bad_url` "the host is not a public internet address" with nothing dialled; `too_large` kept; `_public_address` uses the module's rule |
| `test_feed_pull_rebinding_refused` | pytest | registration refuses a private name (422) and accepts a public one; the first daily pull reads the file from the checked address; when the name rebinds to 127.0.0.1 the pull fails ("the host is not a public internet address") with nothing dialled, and a redirect to a private name is refused |
| `test_webhook_delivery_rebinding_refused` | pytest | a delivery reaches the checked address (SNI, Host, signature header); after the name rebinds to 192.168.1.20 the next one is `failed`, `refused: a host that resolves to public addresses only`, no request reaches anything; a name that stops resolving gives `refused: a host that resolves (hooks.example.com does not)` |
| `test_sso_loopback_issuer_refused_in_production` | pytest | `API_URL` on a public name: `http://127.0.0.1:<port>`, `http://localhost`, `https://127.0.0.1`, `https://localhost`, `https://[::1]`, a name on 10.0.0.7, an unresolvable name and plain http are 422 on `issuer`; a public issuer saves, and when its name rebinds sign-in is 401 `sso_failed`; a loopback issuer saved while the API ran locally gets 401 `sso_failed` (JSON) and the HTML failure page; nothing is dialled, the mock provider sees nothing |
| `test_sso_loopback_issuer_allowed_for_local_api` | pytest | `API_URL=http://127.0.0.1:8000`: `http://192.168.1.20:8098` still refused (plain http only to this computer), the mock provider on a loopback port saves, and a person signs in through it end to end over the module's connections; `API_URL` on a LAN address refuses it again (`sso_failed`) until `SSO_ALLOW_PRIVATE_ISSUERS` is on, then sign-in works |
| `test_try_outbound_script` | pytest | the probe prints the lookup, "public" / "NOT public" / "allowed by --private", the dialled address and the answer; exit codes 0 / 2 / 1; the module's seams are put back |
| existing `test_sso*`, `test_pf12_webhooks*`, `test_pf11_pf12_meet`, `test_market*`, `test_supplier*`, `test_deploy_skill*` | pytest | green (two updated, As-built 4) |

## Human test

Local API on `127.0.0.1:8000`, the site built against it and served by Try it, the mock OIDC provider on `:8098`. `localtest.me` and `*.nip.io` are public DNS names that answer 127.0.0.1, so they stand in for "a name that points inside" (the PC needs internet DNS).

1. Terminal 1, in `server\`: `$env:SECRET_KEY='pf14b-local-test-secret-key-0123456789abcdef'; $env:API_URL='http://127.0.0.1:8000'; $env:SITE_URL='http://127.0.0.1:3135'; $env:CORS_ORIGINS='http://127.0.0.1:3135'; .\run.bat`. Terminal 2, in `server\`: `.venv\Scripts\python.exe -m uvicorn tests.mock_oidc:app --port 8098`. Terminal 3, in the worktree: `$env:NEXT_PUBLIC_AUTH_URL='http://127.0.0.1:8000'; npm run build`, then `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` → it prints `http://127.0.0.1:3135/`.
2. Sign up as `owner@example.com` → Dashboard → Webhooks → add `https://localtest.me/hook` → the form shows "url: a host that resolves to public addresses only". `https://localhost/hook` → "url: a public host, not a local one". `https://example.com/hook` → saved.
3. Delivery after a rebinding: Terminal 4, in `server\`: `.venv\Scripts\python.exe -c "import sqlite3; db = sqlite3.connect('auth.db'); db.execute('update webhook_endpoints set url = ?', ('https://localtest.me/hook',)); db.commit()"` (the saved name now points at 127.0.0.1). Reload Webhooks → Send test on the endpoint → within about 5 s the delivery log shows `failed` with no response code. Hovering it shows "refused: a host that resolves to public addresses only". A retry is queued as `pending`.
4. Terminal 4: `.venv\Scripts\python.exe scripts\try_outbound.py https://example.com/` → `lookup example.com -> …`, each address `public`, `connect <one of them> port 443 (the checked address; no second lookup)`, `answer HTTP 200, Host: example.com, certificate checked for example.com (SNI example.com)`. Then `… scripts\try_outbound.py https://localtest.me/` → `127.0.0.1: NOT public`, `refused localtest.me resolves to an address that is not public: nothing was sent`.
5. SSO still works locally: Dashboard → Organisation → create "Studio North". Terminal 4: `.venv\Scripts\python.exe scripts\verify_org_domain.py --org studio-north --domain example.com`. SSO tab: OpenID Connect, issuer `http://127.0.0.1:8098`, client id `truebex-local`, secret `mock-oidc-secret`, enabled → Save → saved. Sign out → Log in → "Continue with SSO" with `c@example.com` → back on the dashboard, signed in as c@example.com.
6. The production rule: Ctrl+C in terminal 1, then `$env:API_URL='https://api.example.com'; .\run.bat`. Sign in as owner again → SSO tab → Save → "issuer: an https URL on a public internet address". Sign out → "Continue with SSO" with `c@example.com` → the form shows "The identity provider is not on a public internet address." Terminal 2 shows no new request.
7. Optional: Ctrl+C, `$env:SSO_ALLOW_PRIVATE_ISSUERS='true'; .\run.bat` → the SSO tab saves the loopback issuer again. Then `Remove-Item Env:SSO_ALLOW_PRIVATE_ISSUERS, Env:API_URL` before other tests.

## Risks / traps

* **Seams.** Tests that replace `delivery.client_factory` with an `httpx.MockTransport`, or `oidc.http_client` with a `TestClient`, bypass the pinned connection by design. A rebinding test must run over the real client (`FakeNet`, or `outbound.resolve` / `outbound.connect` patched), as `test_webhooks_refuse_private_address_at_delivery` now does.
* **httpx internals.** `PinnedTransport` relies on `HTTPTransport.handle_request` and `close` using only `self._pool` (true in httpx 0.28.1, pinned in `requirements.txt`). An httpx upgrade that changes that fails `test_outbound_connects_to_the_checked_address` and `test_tls_name_kept` at once.
* **Save-time DNS for SSO.** An https issuer is now looked up when the SSO tab is saved in production. A provider whose name does not resolve yet cannot be saved (as for webhooks and feeds).
* **API_URL decides SSO's mode.** A LAN trial (`API_URL=http://<LAN address>:8000`, PF5's phone test) refuses the loopback mock provider unless `SSO_ALLOW_PRIVATE_ISSUERS=true`.
* **IPv6 forms.** Python 3.12.10 already judges `::ffff:a.b.c.d` by its IPv4 and calls all of 2002::/16 private. The module judges mapped, NAT64 and 6to4 by their IPv4 itself, so a public 6to4 or NAT64 address is allowed and a private one refused whatever the Python version.
* RAM: no `next dev`. The build in step 1 is the static export.

## As-built

* **Date, branch, commits:** 2026-10-11, `ap/t35-pf14b-outbound-requests-pinned-t` from `master` 842768e. `665fca8`: the module, the callers, the setting and the tests. A second commit: the probe script and its test, this doc, the tracker row and the README section.
* **Counts:** `scripts/autopilot-verify.ps1` green: lint, the static build, pytest 553 passed + 5 skipped (the Postgres tests), 544 passed before, 9 new. Every name in the Tests table exists verbatim. No page or copy change, so the build's output is the same.
* **Self-tests beyond pytest:** a headless run of the human test against the real API and `mock_oidc` under uvicorn on loopback, with real DNS and nothing patched. Webhooks: `localtest.me` and `127.0.0.1.nip.io` were refused at save (422), `localhost` was refused by name, `example.com` was saved. After the stored URL changed to `localtest.me` the delivery was `failed` "refused: a host that resolves to public addresses only", with a retry `pending`. SSO with `API_URL=http://127.0.0.1:8135`: the `http://127.0.0.1:8198` issuer saved and the person signed in to `/login/sso/#token=…`. With `API_URL=https://api.example.com`: save gave 422 "issuer: an https URL on a public internet address", start gave 401 `sso_failed` (JSON) and the HTML failure page, and the provider saw no new call. `try_outbound.py` against real DNS: `example.com` connected to its checked address (HTTP 200, certificate checked for the name); `127.0.0.1.nip.io` and `localtest.me` were refused with nothing sent.
* **Deviations and decisions:**
  1. *How:* the task's suggested shape, an httpx transport whose network backend does lookup, check and connect in one step. The pool is built in `PinnedTransport.__init__` because `HTTPTransport` takes no network backend.
  2. *Refusal text in production:* the `issuer` field error keeps its code and field. Its message is "an https URL on a public internet address" when the API is not on loopback, because the old "(or http://127.0.0.1 for a local test provider)" would be wrong there. Locally it is unchanged.
  3. *`media.HttpFetcher(resolver=…)`* stays as an optional extra name check (`test_market_admin.py` passes one); by default there is none, since the pinned connection checks every hop. Feeds no longer call `public_host` per hop either, for the same reason: one lookup per connection.
  4. *Two existing tests updated, intent kept:* `test_sso.py`'s `idp` fixture now also answers DNS for `idp.test`, because the issuer is resolved at save. `test_pf12_webhooks.py::test_webhooks_refuse_private_address_at_delivery` runs over the real delivery client, with `outbound.resolve` on the test's `HOSTS` table and `outbound.connect` recording, instead of a `MockTransport` that would bypass the pinning. It asserts nothing is dialled and the attempt is `refused`.
  5. *Stricter save-time rule for webhooks:* `urls._public` is now `outbound.is_public`, so 100.64.0.0/10, multicast, site-local and the NAT64 / 6to4 forms of private addresses are refused at save as well.
  6. *A DNS failure at delivery* is reported as before ("refused: a host that resolves (… does not)") and retried on the schedule.
* **Gate fix (Autopilot's verify run 1):** `test_render.py::test_jobs_status_long_poll_rev` failed once: 1.17 s from the heartbeat to the woken long poll's answer, against its 1 s limit. It normally takes 16 ms, and about 0.1 s under synthetic disk or CPU load. Two other tasks' verify gates (T36, T37) were running on the PC at the time. The long poll answers the moment the change commits, so the time was a whole-process stall. A full-suite run with a GC probe found the cause: late in the suite the test process holds about 800k objects, and Python's full garbage collection, which stops every thread, takes 0.25-0.73 s and fires in whichever test happens to allocate. `tests/conftest.py` now has `timing_window()`: one full collection before the window and none inside it. It wraps the two 1 s wake-up windows (`test_render.py::test_jobs_status_long_poll_rev`, `test_projects.py::test_pull_long_poll_wakes_on_push`); their assertions are unchanged. Freezing the import-time heap (`gc.freeze()`) was tried and dropped: Python 3.12 then ran full collections more often (25 instead of 14 in a run), with no shorter pauses.
* **Out of scope, as the task set it:** SAML (pasted metadata, browser-redirect sign-in URL; `service.py`'s http-loopback SAML URL stays accepted because the API never requests it). The fixed provider hosts (Paddle, Stripe, Wayl, Anthropic). The operator-configured internal servers (`ai/servers.py`, `ai/adapters/selfhosted.py`, the `*_API_BASE` / `ANTHROPIC_BASE_URL` mocks, `RELEASE_PUBLIC_KEYS` as a URL). `ops.py`'s health checks and `ALERT_PUSH_URL`.
* **Carry-over:** PF3: require https for the discovery document's `jwks_uri` and `token_endpoint` (they are already limited to public addresses). PF12: if webhooks ever follow redirects, keep `follow_redirects=False` on the module's client and follow each hop by hand, as feeds do.
