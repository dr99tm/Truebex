# @truebex/sdk — the JavaScript SDK for the Truebex developer API

Typed access to projects, exports, shares, the marketplace, supplier feeds and
webhooks, generated from the API's own OpenAPI document (`openapi/v1.json`).
Node 18+, browsers and edge workers; no dependencies.

```bash
npm install @truebex/sdk
```

## Authenticate

Create a key under **Dashboard → API keys** on truebex.com with the scopes you
need, and keep it on your server in an environment variable:

```bash
export TRUEBEX_API_KEY=tbx_live_…
```

```js
import { Truebex } from "@truebex/sdk";

const truebex = new Truebex(); // reads process.env.TRUEBEX_API_KEY
const project = await truebex.projects.create({ name: "API House", doc_version: 38 });
const { ops } = await truebex.projects.pullOps(project.project_id, { after: 0, wait_s: 25 });
const job = await truebex.jobs.create({
  kind: "pack",
  project_id: project.project_id,
  at_seq: project.head_seq,
  params: { items: ["sheets"] },
});
```

Groups: `account`, `projects`, `jobs`, `uploads`, `shares`, `market`, `feeds`,
`webhooks`. Path parameters come first, then one object with the body's fields
and the query, then options (`{ idempotencyKey, signal }`). Writes that take an
idempotency key get one automatically, so retries on 429, 5xx and network
errors never repeat them.

## Errors

```js
import { TruebexError } from "@truebex/sdk";

try {
  await truebex.projects.delete(projectId);
} catch (err) {
  if (err instanceof TruebexError) console.log(err.status, err.code, err.requestId); // 403 session_required
}
```

## Webhooks: verify the signature

```js
import { verifyWebhook } from "@truebex/sdk/webhooks";

const event = await verifyWebhook(process.env.TRUEBEX_WEBHOOK_SECRET, req.headers, rawBody);
```

Pass the raw body as received. It refuses a wrong signature and a timestamp
more than 5 minutes off (`WebhookVerificationError`).

## Publishing (Truebex staff)

Regenerate with `scripts\gen-sdks.ps1` at the repository root, then from
`sdks/js`: `npm publish --access public`.
