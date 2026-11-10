# Support API (`/internal/support`)

The server-to-server gates the Truebex Desk (the Cloudflare Worker in `truebex-support`) calls when a
customer signs in, signs up or asks about their account from WhatsApp (or e-mail). Code:
`server/app/routers/support.py`, `server/app/support/`; tests: `server/tests/test_support_api.py`.

- Base URL: `https://api.truebex.com/internal/support` (staging: `https://api-staging.truebex.com/internal/support`).
- Hidden from the OpenAPI schema and the SDKs. Never called from a browser or the app.
- **Off unless `SUPPORT_SERVICE_SECRET` is set**: then every route answers `404 not_found`, signed or not.
- Account data is answered for an account id the Desk learned from one of these gates (an e-mail code, a
  password, or a link approved on truebex.com). The API never hands the Desk a session token or a JWT.

## 1. Signing

Every request is signed with the shared secret, Standard Webhooks style, verified by
`server/app/webhooks/signing.py: verify()`.

### Secret

`SUPPORT_SERVICE_SECRET` = `whsec_` + standard base64 of 32 random bytes (24 at least). The HMAC key is the
decoded bytes (not the text). The API holds it in `infra/secrets/server.sops.env`; the Worker holds the same value as its
`SUPPORT_SERVICE_SECRET` secret. During a rotation the API accepts a comma-separated list,
`whsec_new,whsec_old`; the Worker signs with one.

### Headers (all three required on every request)

| Header | Value |
|---|---|
| `webhook-id` | A new unique id for **every** request, retries included: 1–128 characters of `A-Z a-z 0-9 _ . : -` (e.g. `msg_` + 24 random hex). |
| `webhook-timestamp` | Unix time in whole seconds when signed. Refused when more than 300 s off the API's clock, either way. |
| `webhook-signature` | `v1,` + standard base64 (with padding) of the HMAC-SHA256. Several space-separated signatures are allowed; one `v1` match is enough. |
| `content-type` | `application/json` on requests with a body (POST). |

### Signed content

```
<webhook-id>.<webhook-timestamp>.<METHOD> <path>[?<query>]\n<body>
```

- `METHOD`: upper case (`POST`, `GET`, `DELETE`).
- `path`: the request path exactly as sent, starting `/internal/support/…`; `?<query>` only when the
  request has a query string, byte for byte as sent.
- `\n`: one line feed (0x0A).
- `body`: the exact bytes sent (UTF-8 JSON), or nothing for GET and DELETE.

This is Standard Webhooks' `id.timestamp.body` with the request line put in front of the body: webhooks
always go to one URL, these requests do not, so the method and path are signed too (a GET's or DELETE's
signature then names its account and device).

### Replays

An id is accepted once (kept 24 h). A second request with the same `webhook-id` answers
`401 replayed_request`, even after a failure of the first, so a retry is signed again with a new id and a
new timestamp. A request refused for its signature does not use its id up.

### Worked example

Secret `whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw` (the Standard Webhooks specification's example; never use
it for real), `webhook-id` `msg_2KWPBgLlAfxdpx2AI54pPJ85f4W`, `webhook-timestamp` `1794312000`
(2026-11-10T12:00:00Z), `POST /internal/support/email-code` with the body

```
{"email":"customer@example.com","contact_hash":"5f9801c1f8a8507e661ac3f136471d3eec7332db0859fd5026c8101c09af38c8"}
```

Signed content (one line feed after `email-code`):

```
msg_2KWPBgLlAfxdpx2AI54pPJ85f4W.1794312000.POST /internal/support/email-code
{"email":"customer@example.com","contact_hash":"5f9801c1f8a8507e661ac3f136471d3eec7332db0859fd5026c8101c09af38c8"}
```

`webhook-signature: v1,3P81RD2ErBcLvksX9BvhjTWW9/WQrV6WeMofSReITjs=`

The same secret and timestamp, `webhook-id` `msg_2KWPBgLlAfxdpx2AI54pPJ85f4X`,
`GET /internal/support/users/42/summary` (no body: the content ends with the line feed):
`v1,JFtL4ueD62LHPAV6mW6godMvNd00yw5AdUxdcpO6HF4=`.

`test_worked_example_from_the_contract` checks both values and sends the first request.

In the Worker (Web Crypto):

```ts
async function sign(secret: string, id: string, ts: number, method: string, target: string, body: string) {
  const raw = Uint8Array.from(atob(secret.replace(/^whsec_/, "")), (c) => c.charCodeAt(0));
  const key = await crypto.subtle.importKey("raw", raw, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const content = new TextEncoder().encode(`${id}.${ts}.${method} ${target}\n${body}`);
  const mac = new Uint8Array(await crypto.subtle.sign("HMAC", key, content));
  return "v1," + btoa(String.fromCharCode(...mac));
}
// target = "/internal/support/users/42/summary" (+ "?" + query when there is one); send exactly `body`.
```

## 2. Shared conventions

- **`contact_hash`**: 64 lowercase hex characters (a SHA-256 hex digest) the Desk computes for the chat
  contact, e.g. HMAC-SHA256 of the E.164 number under a Desk-only key. The API never sees the number. It keys
  the per-contact rate limits and the audit line; a link code stores it as its fingerprint.
- **E-mail addresses** are trimmed and lower-cased; `.test` and other invalid addresses are `422`.
- **Times** are RFC 3339 UTC with `Z`.
- **Errors** use the API's shared envelope, with the same `X-Request-Id` header:

  ```json
  {"detail": "…", "code": "invalid_code", "status": 401, "request_id": "<32 hex>", "retry_after_s": null, "data": {"attempts_left": 3}}
  ```

  `detail` is English text fit to show; branch on `code`. A `429` also sends `Retry-After`.

Errors any route can answer:

| Status | `code` | When |
|---|---|---|
| 404 | `not_found` | `SUPPORT_SERVICE_SECRET` is empty (every route, before anything else). |
| 401 | `invalid_signature` | A header is missing or malformed, the timestamp is more than 300 s off, or no signature matches. |
| 401 | `replayed_request` | This `webhook-id` was already accepted. |
| 422 | `validation_failed` | The body or path is not valid; `data.fields[]` names each field. |
| 503 | `unavailable` | No configured secret is `whsec_` + strict base64 of at least 24 bytes (a server set-up fault, logged). |
| 500 | `internal_error` | A fault on the API's side (recorded in its crash store). |

## 3. Routes

### `POST /email-code` → 202

Mails a six-digit one-time code to the address. **The answer is the same whether or not the address has
an account** (and for an address of a domain that requires SSO): the account is only revealed by
`/email-code/verify`, to whoever holds the code.

| Request | |
|---|---|
| `email` | string, an e-mail address |
| `contact_hash` | string, 64 hex, required |

Response: `{"status": "sent", "expires_in_s": 600, "code_length": 6}`.

- The code lives 10 minutes, allows 5 tries and works once. Asking again replaces the address's earlier
  code (the old one stops working). Stored only as HMAC-SHA256 under a key derived from `SECRET_KEY`.
- The e-mail is the `support_code` template ("Your Truebex code"); the code is never in the subject. A mail
  outage is logged, never answered (the answer stays the same).
- Errors: `422`, `429 rate_limited`.

### `POST /email-code/verify` → 200

| Request | |
|---|---|
| `email` | string, the same address |
| `code` | string ≤ 16; spaces and dashes are ignored, then it must be 6 digits |
| `contact_hash` | string, 64 hex, optional (rate limit, audit) |

| Response | |
|---|---|
| `verification_id` | string (43 URL-safe characters): single use, for `/register`, valid 15 minutes. Keep it secret. |
| `expires_in_s` | `900` |
| `exists` | bool: the address has an account |
| `user_id` | int or `null`: the account, when `exists` and its domain does not require SSO. **The code is then a full sign-in**: link the contact to this id. `null` otherwise. |
| `has_password` | bool (false when no account) |
| `google_linked` | bool (false when no account) |
| `sso_required` | bool: the address's domain belongs to an organisation that requires SSO. Then `user_id` is `null` even for an existing account: use the link sign-in. |
| `org_name` | string or `null`: that organisation's name |

A right code for an existing account also sets `users.email_verified_at`.

| Errors | |
|---|---|
| `401 invalid_code` | Wrong code; it cost a try. `data.attempts_left` (0–4); at 0 the code is dead. |
| `410 code_expired` | No live code for the address: never sent, expired, used, replaced or out of tries. Ask for a new one. |
| `422`, `429` | |

### `POST /register` → 201

Creates a password account for an address a code verified, and only for that. The address comes from the
verification, never from the request.

| Request | |
|---|---|
| `verification_id` | from `/email-code/verify` |
| `password` | string, 8–128 characters (the website's rule) |
| `name` | string ≤ 200, optional (trimmed; empty = none) |
| `contact_hash` | string, 64 hex, optional |

Response: `{"user_id": 123, "email": "customer@example.com"}`. The account's `email_verified_at` is set.

The verification is spent by the first `/register` that gets past the checks below, whatever follows (so it
makes at most one account).

| Errors | |
|---|---|
| `410 verification_expired` | Unknown, spent or older than 15 minutes: verify the address again. |
| `403 sso_required` | The domain's organisation requires SSO (`data.org_name`): use the link sign-in, which goes through SSO on truebex.com. |
| `409 account_exists` | The address already has an account (sign in instead). |
| `422`, `429` | |

### `POST /login` → 200

| Request | |
|---|---|
| `email` | string |
| `password` | string, 1–128 |
| `contact_hash` | string, 64 hex, optional |

Response: `{"user_id": 123}`.

| Errors | |
|---|---|
| `401 invalid_credentials` | Unknown address or wrong password (the same answer and timing for both). |
| `403 use_link_sign_in` | No password sign-in for this address: `data.reason` is `sso_required` (the domain requires SSO; `data.org_name`) or `no_password` (a Google or SSO account; `data.google_linked` says which). Offer the e-mail code (not for `sso_required`) or the link. |
| `422`, `429` | |

There is no password reset and no break-glass code here.

### `POST /link/start` → 201

The website link sign-in (the device flow of `licence/links.py`) for customers who sign in with Google or
SSO, or prefer to: the customer opens `verify_url`, signs in on truebex.com any way they like, sees
"Truebex support · WhatsApp +44 *** 0123" and presses Approve.

Whoever approves a code links *their* account to the chat that started it, so a code forwarded by someone
else is the risk (as with any device code). Send `contact_label` so the page shows which chat asked, and
tell the customer to approve only a code they asked for in their own chat.

| Request | |
|---|---|
| `contact_hash` | string, 64 hex, required |
| `channel` | `"whatsapp"` (default) or `"email"`: shown on the approval page as `WhatsApp` / `Email` |
| `contact_label` | string ≤ 20 of `0-9 A-Z a-z + * . @ -` and spaces, optional: a **masked** hint of the chat, e.g. `+44 *** 0123` (never the whole number); shown after the channel |

| Response | |
|---|---|
| `link_code` | `"QX7D-K9MP"` (8 characters, a hyphen in the middle): show it to the customer |
| `verify_url` | `https://truebex.com/dashboard/link/?code=QX7D-K9MP`: send it to the customer |
| `poll_secret` | 43 characters: keep it in the Desk only, never show it |
| `expires_in_s` | `600` |
| `interval_s` | `5`: poll no faster |

Errors: `422`, `429`.

### `POST /link/poll` → 200

| Request | |
|---|---|
| `poll_secret` | from `/link/start` |

Response: `{"status": "pending", "user_id": null}` until the customer approves, then once
`{"status": "approved", "user_id": 123}`. Never a session or token. Each poll is a signed request with a
new `webhook-id`.

| Errors | |
|---|---|
| `410 link_expired` | Unknown, older than 10 minutes, already handed over, or not a support link (a device's link never answers here, and a support link never answers the app's poll). Start again. |
| `403 link_denied` | The customer pressed Deny. |
| `429 rate_limited` | Polled faster than every 5 s (`retry_after_s`). |

### `GET /users/{user_id}/summary` → 200

Optional query `?contact_hash=<64 hex>` (signed with the path; used for the audit line only).

| Field | |
|---|---|
| `user` | `{id, email, name, created_at, has_password, google_linked, email_verified_at}` |
| `plan`, `plan_name` | The tier id (`free`, `pro`, `studio`, `team`, `enterprise`) and its name, from the best seat the account holds (the app's Account panel). |
| `trial` | `{used, active, ends_at}` |
| `seat` | `{kind, org_id, org_name}`; `kind` is `free`, `personal`, `trial`, `named` or `floating` |
| `seats` | `{total, assigned}` |
| `devices` | `{active: [{device_id, name, os, app_version, activated_at, last_seen_at, current}], count, limit}`; `limit` is `null` for no limit; `current` is always false here |
| `subscription` | The Billing page's subscription (`GET /billing/subscription`): `{tier, interval, seats, status, provider, current_period_end, cancel_at_period_end, founding, can_manage, currency, can_cancel, cooling_off_until, withdrawal_until, org_id, seats_assigned}`; `status` `none` on Free |
| `payments` | The 5 latest personal payments, newest first, as `GET /billing/payments`: `{reference, provider, plan, amount, currency, status, created_at, paid_at, interval, seats, tax_minor, consent_version, key_info, key_info_at, business, organisation_id, item, credits}`; `amount` and `tax_minor` in minor units |
| `api_keys` | The account's developer keys as the dashboard lists them (active first): `{id, name, prefix, created_at, last_used_at, revoked_at, scopes, legacy}`. Never the key or its hash. |
| `release` | The latest stable Windows release, or `null`: `{version, channel, platform, published_at, mandatory, file, bytes, sha256, notes_url, download_page_url}`. `download_page_url` is `https://truebex.com/download/`; the counted download endpoint is never called. |
| `analysis_jobs` | The 10 latest wind, energy, acoustics and airflow jobs, newest first: `{job_id, kind, state, project_id, created_at, finished_at, progress, message, error, report_pdf_url}`. `report_pdf_url` is a signed link to the report PDF valid 1 h, or `null` (not finished, or no report). |
| `report_urls_expire_in_s` | `3600` |
| `manage_url` | `https://truebex.com/dashboard/billing/` |

Errors: `404 not_found` (no such account), `422`.

### `GET /users/{user_id}/invoices` → 200

Optional `?contact_hash=`. The account's own VAT invoices from every payment provider it bought through
(the Billing page's list), newest first:

```json
{"invoices": [{"id": "txn_…", "number": "…", "issued_at": "2026-11-10T12:00:00Z", "total_minor": 1188,
  "tax_minor": 198, "currency": "GBP", "status": "paid",
  "pdf_url": "https://api.truebex.com/billing/invoices/txn_…/pdf?u=123&p=paddle&exp=…&sig=…"}],
 "pdf_links_expire_in_s": 3600}
```

`pdf_url` is absolute (`API_URL` + the signed path), opens without a session and redirects to the
provider's PDF; it is valid 1 h, so fetch the list again when sending one later.

Errors: `404 not_found`, `502 upstream_failed` (a provider did not answer; try again in a minute), `422`.

### `DELETE /users/{user_id}/devices/{device_id}` → 200

Optional `?contact_hash=`. Signs a computer out: its slot is freed and its device token stops working at
once (as `DELETE /licence/devices/{id}`; the licence event `device.revoked`, reason `removed`). Confirm with
the customer first.

Response: `{device_id, name, os, app_version, activated_at, last_seen_at, current, deactivated_at, removed}`;
`removed` is false when it was already signed out (repeating it is harmless).

Errors: `404 not_found` (no such account, or the device is not on it), `422`.

## 4. Rate limits

Token buckets (`server/app/ratelimit.py`; shared across processes on the VM). Never per IP: every Desk call
leaves from Cloudflare's addresses. A refused call answers `429 rate_limited` with `retry_after_s`.

| Route | Bucket | Burst | Refill |
|---|---|---|---|
| `/email-code` | per `contact_hash` | 10 | 10 an hour |
| | per address | 5 | 5 an hour |
| | all addresses together | 60 | 300 an hour |
| `/email-code/verify` | per `contact_hash` (when sent) | 20 | 20 an hour |
| | per address | 10 | 10 an hour |
| `/register` | per `contact_hash` (when sent) | 10 | 10 an hour |
| | per verified address | 5 | 5 an hour |
| `/login` | per `contact_hash` (when sent) | 20 | 20 an hour |
| | per address | 10 | 10 an hour |
| `/link/start` | per `contact_hash` | 10 | 10 an hour |
| `/link/poll` | per link code | one poll every 5 s | |

Buckets are checked in the order listed; a call refused by a later bucket has already spent a token of an
earlier one. On top of the buckets each code allows 5 tries. The per-address `/login` bucket also means
anyone who knows an address can hold its password sign-in for up to an hour; the e-mail code and the link
still work then.

## 5. Audit and logs

Every accepted call writes one line to the `truebex.support` logger (the API container's log):

```
support POST /internal/support/login by desk msg=msg_… contact=5f9801c1f8a8 user=123 -> ok (request <32 hex>)
```

- `msg` is the `webhook-id`, `contact` the first 12 characters of `contact_hash`, `user` the account (from
  the path or the gate's answer; `-` when none), then the outcome (`ok` or the error `code`) and the API's
  request id (the `X-Request-Id` the Desk received).
- Refused signatures and replays log a warning line with the id and the outcome.
- Never logged: codes, passwords, verification ids, poll secrets, signatures or the secret. The `console`
  mail backend (local development and tests only) prints whole e-mails, codes included; production uses
  `smtp`.

## 6. Data kept

| Table | What | Lifetime |
|---|---|---|
| `support_email_codes` | address, code HMAC, `contact_hash`, tries, `used_at` | 10 min; purged (spent or expired) every 10 min by `support.codes.purge` |
| `support_verifications` | SHA-256 of the verification id, address, `contact_hash`, `used_at` | 15 min; the same job |
| `idempotency_keys` (account `support`) | SHA-256 of each accepted `webhook-id` (first 32 hex) | 24 h (`idempotency.expire`) |
| `link_codes` (`purpose = support`) | the link, its poll secret's SHA-256, `contact_hash` as fingerprint | 10 min (`licence.links.purge`) |
| `users.email_verified_at` | when the account last proved its address with a code | kept |

`users.email_verified_at` and `link_codes.purpose` are added on start-up to existing databases
(`database._ADDED_COLUMNS`). The website's `GET /licence/link/{code}` gains `purpose` (`device` or
`support`) so the approval page can word a support sign-in as a chat.

## 7. The approval page (website)

`/dashboard/link/` works today: it shows "Truebex support · WhatsApp" and the code, and Approve and Deny
work. Its other text is written for a computer, so a support sign-in reads oddly until the page branches on
the new `purpose` field (`src/app/dashboard/link/page.tsx`, `LinkInfo` in `src/lib/licence.ts`):

| Now | For `purpose: "support"` |
|---|---|
| "Truebex on a computer asked to sign in to your account." | "Truebex support asked to sign you in from a chat." |
| "Only approve a code shown on your own computer." | "Only approve a code Truebex support sent to your own chat." |
| "Approved. Return to Truebex: it finishes signing in within a few seconds." | "Approved. Return to the chat: Truebex support finishes signing you in within a few seconds." |
| "Denied. That computer was not signed in." | "Denied. The chat was not signed in." |
| "Start the sign-in again in Truebex" | "Ask for a new code in the chat" |
| The monitor icon | a chat icon |

## 8. Owner set-up

1. Make a secret, in your own terminal (never in a chat, a task or a file in the repo):
   `server\.venv\Scripts\python.exe -c "import base64, secrets; print('whsec_' + base64.b64encode(secrets.token_bytes(32)).decode())"`
2. API: `sops infra\secrets\server.sops.env`, add `SUPPORT_SERVICE_SECRET=<it>`, save. Deploy the merged
   `master` with `infra\deploy.ps1 -VmHost truebex@<vm> -HealthUrl https://api-staging.truebex.com/health/deep`,
   then check `https://api.truebex.com/health/deep`. `api-staging.truebex.com` is a hostname of the same VM
   and containers (`infra/host/Caddyfile`, `deploy.ps1 -ApiHosts`), so the API has one value.
3. Desk: in `X:\truebex-support`, `npx wrangler secret put SUPPORT_SERVICE_SECRET` with the same value, for
   each Desk environment (staging and production Workers both call this API).
4. Check: a signed `POST /internal/support/email-code` from the staging Desk answers 202; unsigned, 401;
   before step 2, 404.
