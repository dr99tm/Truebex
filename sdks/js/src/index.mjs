// @truebex/sdk: the Truebex developer API for JavaScript (Node 18+, browsers,
// workers). Every operation of openapi/v1.json is a method of a group
// (client.projects.create, client.jobs.get …), built from OPERATIONS; the
// types are in index.d.ts. Keys stay out of logs and error messages.
import { OPERATIONS } from "./operations.mjs";
export { OPERATIONS } from "./operations.mjs";
export { verifyWebhook, WebhookVerificationError } from "./webhooks.mjs";

export const DEFAULT_BASE_URL = "https://api.truebex.com";
const RETRY = new Set([408, 429, 500, 502, 503, 504, 530]);
const sleep = (s) => new Promise((r) => setTimeout(r, s * 1000));
const hex = (bytes) => [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, "0")).join("");
const newKey = () => hex(crypto.getRandomValues(new Uint8Array(16)));

/** An error answer: branch on `code` (forbidden, not_found, rate_limited …). */
export class TruebexError extends Error {
  constructor(status, code, detail, { data = null, requestId = null, retryAfterS = null } = {}) {
    super(`${status} ${code}: ${detail}`);
    this.name = "TruebexError";
    Object.assign(this, { status, code, detail, data, requestId, retryAfterS });
  }
}

export class Truebex {
  /** @param {{apiKey?: string, baseUrl?: string, maxRetries?: number, fetch?: typeof fetch}} [opts] */
  constructor(opts = {}) {
    const env = typeof process !== "undefined" ? process.env : {};
    const apiKey = opts.apiKey ?? env.TRUEBEX_API_KEY ?? "";
    const baseUrl = (opts.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
    const maxRetries = opts.maxRetries ?? 2;
    const doFetch = opts.fetch ?? globalThis.fetch.bind(globalThis);
    Object.defineProperty(this, "baseUrl", { value: baseUrl, enumerable: true });
    // Not enumerable: console.log(client) never prints the key.
    Object.defineProperty(this, "_send", {
      value: (method, path, init, idempotent) => send(doFetch, apiKey, baseUrl, maxRetries, method, path, init, idempotent),
    });
    for (const [id, op] of Object.entries(OPERATIONS)) {
      this[op.group] ??= {};
      this[op.group][op.name] = (...args) => this._call(id, args);
    }
  }

  async _call(id, args) {
    const op = OPERATIONS[id];
    const pathValues = args.slice(0, op.pathParams.length);
    let rest = args.slice(op.pathParams.length);
    const data = op.body === "binary" ? rest.shift() : undefined;
    const [params = {}, options = {}] = rest;
    let path = op.path;
    op.pathParams.forEach((name, i) => (path = path.replace(`{${name}}`, encodeURIComponent(String(pathValues[i])))));
    const query = new URLSearchParams();
    for (const name of op.query) if (params[name] != null) query.set(name, String(params[name]));
    if ([...query].length) path += `?${query}`;
    const headers = {};
    if (op.contract) headers["X-Truebex-Contract"] = op.contract;
    const idempotent = op.headers.includes("idempotency-key");
    if (idempotent) headers["Idempotency-Key"] = options.idempotencyKey ?? newKey();
    let body;
    if (op.body === "json") {
      const json = {};
      for (const name of op.bodyProps) if (params[name] !== undefined) json[name] = params[name];
      body = JSON.stringify(json);
      headers["Content-Type"] = "application/json";
    } else if (op.body === "binary") {
      body = data instanceof Blob ? new Uint8Array(await data.arrayBuffer()) : new Uint8Array(data);
      headers["Content-Type"] = "application/octet-stream";
      headers["X-Part-Sha256"] = params.partSha256 ?? hex(await crypto.subtle.digest("SHA-256", body));
    } else if (op.body === "multipart") {
      body = new FormData();
      const file = params.file instanceof Blob ? params.file : new Blob([params.file]);
      body.set("file", file, params.filename ?? "feed");
      for (const name of op.bodyProps) if (name !== "file" && params[name] != null) body.set(name, String(params[name]));
    }
    return this._send(op.method, path, { headers, body, signal: options.signal }, idempotent);
  }
}

async function send(doFetch, apiKey, baseUrl, maxRetries, method, path, init, idempotent) {
  if (!apiKey) throw new TruebexError(401, "unauthenticated", "No API key: pass apiKey or set TRUEBEX_API_KEY.");
  const headers = { Authorization: `Bearer ${apiKey}`, Accept: "application/json", ...init.headers };
  const mayRetry = method !== "POST" || idempotent;
  for (let attempt = 0; ; attempt++) {
    let res;
    try {
      res = await doFetch(baseUrl + path, { method, headers, body: init.body, signal: init.signal });
    } catch (err) {
      if (attempt < maxRetries && mayRetry && err?.name !== "AbortError") {
        await sleep(Math.min(60, 2 ** attempt) * (0.8 + 0.4 * Math.random()));
        continue;
      }
      throw new TruebexError(0, "network_error", `Could not reach ${baseUrl}: ${err?.message ?? err}`);
    }
    if (res.ok) return res.status === 204 ? undefined : res.json();
    const retryAfter = Number(res.headers.get("Retry-After"));
    if (attempt < maxRetries && RETRY.has(res.status) && (mayRetry || res.status === 429)) {
      await sleep(retryAfter > 0 ? retryAfter : Math.min(60, 2 ** attempt) * (0.8 + 0.4 * Math.random()));
      continue;
    }
    const body = await res.json().catch(() => ({}));
    throw new TruebexError(res.status, body?.code ?? `http_${res.status}`, typeof body?.detail === "string" ? body.detail : `Request failed (${res.status})`, {
      data: body?.data ?? null,
      requestId: body?.request_id ?? res.headers.get("X-Request-Id"),
      retryAfterS: body?.retry_after_s ?? null,
    });
  }
}
