// Verify a Truebex webhook (Standard Webhooks) with WebCrypto: Node 18+,
// browsers and edge workers. Pass the raw body exactly as received.
//
//   const event = await verifyWebhook(process.env.TRUEBEX_WEBHOOK_SECRET, req.headers, rawBody);

export class WebhookVerificationError extends Error {
  constructor(message) {
    super(message);
    this.name = "WebhookVerificationError";
  }
}

const TOLERANCE_S = 5 * 60;
const enc = new TextEncoder();

function header(headers, name) {
  if (typeof headers?.get === "function") return headers.get(name);
  const hit = Object.keys(headers ?? {}).find((k) => k.toLowerCase() === name);
  const value = hit === undefined ? undefined : headers[hit];
  return Array.isArray(value) ? value[0] : value;
}

function fromBase64(text) {
  const bin = atob(text);
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

function toBase64(bytes) {
  let bin = "";
  for (const b of new Uint8Array(bytes)) bin += String.fromCharCode(b);
  return btoa(bin);
}

function same(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/** `v1,<base64 HMAC-SHA256 of "id.timestamp.body">`. */
export async function signWebhook(secret, msgId, timestamp, body) {
  const key = await crypto.subtle.importKey(
    "raw",
    fromBase64(secret.startsWith("whsec_") ? secret.slice(6) : secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const raw = typeof body === "string" ? enc.encode(body) : new Uint8Array(body);
  const prefix = enc.encode(`${msgId}.${Math.trunc(Number(timestamp))}.`);
  const content = new Uint8Array(prefix.length + raw.length);
  content.set(prefix);
  content.set(raw, prefix.length);
  return `v1,${toBase64(await crypto.subtle.sign("HMAC", key, content))}`;
}

/** The parsed event, or a WebhookVerificationError. */
export async function verifyWebhook(secret, headers, body, { toleranceS = TOLERANCE_S, now } = {}) {
  const id = header(headers, "webhook-id");
  const stamp = header(headers, "webhook-timestamp");
  const signatures = header(headers, "webhook-signature");
  if (!id || !stamp || !signatures) throw new WebhookVerificationError("missing webhook-id, webhook-timestamp or webhook-signature");
  const ts = Number(stamp);
  if (!Number.isInteger(ts)) throw new WebhookVerificationError("bad webhook-timestamp");
  const current = now ?? Date.now() / 1000;
  if (Math.abs(current - ts) > toleranceS) throw new WebhookVerificationError("timestamp too old or too new");
  const expected = (await signWebhook(secret, id, ts, body)).slice(3);
  for (const item of String(signatures).split(" ")) {
    const [version, value] = item.split(",", 2);
    if (version === "v1" && value && same(value, expected)) {
      const text = typeof body === "string" ? body : new TextDecoder().decode(body);
      try {
        return JSON.parse(text);
      } catch {
        throw new WebhookVerificationError("the body is not JSON");
      }
    }
  }
  throw new WebhookVerificationError("no matching signature");
}
