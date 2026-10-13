// PF7b: the "Buy this look" basket link the app's room themes open
// (contract marketplace-api §3, the PR2 line of 2026-10-11):
//   /market/basket?region=<r>&items=<supplier hex>:<sku>:<variant>:<qty>,...
// The app URL-encodes the whole items value once, so commas and colons arrive
// as %2C and %3A; URLSearchParams decodes it once and nothing here decodes it
// again (a SKU holding "%3A" keeps it). `default` stands for the product's
// variant when the app did not know it (the basket route resolves it).
//
// Pure functions without imports: server/tests/test_pf7b_basket.py runs this
// file with Node.

export const MAX_ITEMS = 100;
export const MAX_QTY = 99;
export const MAX_FIELD = 64;
export const DEFAULT_VARIANT = "default";

const HEX32 = /^[0-9a-fA-F]{32}$/;
const REGION = /^[A-Z]{2}(-[A-Z0-9]{1,3})?$/;
const DIGITS = /^[0-9]+$/;

export interface ItemRef {
  supplier_id: string;
  sku: string;
  variant_id: string;
}

export interface BasketItem extends ItemRef {
  qty: number;
}

export type RejectReason = "malformed" | "supplier" | "sku" | "variant" | "qty";

export interface Rejected {
  /** 1-based, among the link's items. */
  position: number;
  text: string;
  reason: RejectReason;
}

export interface ParsedBasket {
  /** Upper-cased; null when missing or not a region code. */
  region: string | null;
  items: BasketItem[];
  rejected: Rejected[];
  /** The item count when the link lists more than MAX_ITEMS (then nothing is read). */
  tooMany: number | null;
}

interface MoneyLike {
  amount: number;
  currency: string;
  exponent: number;
}

/** Characters as the server counts them (code points), not UTF-16 units. */
const length = (s: string) => Array.from(s).length;

export const refKey = (r: ItemRef) => `${r.supplier_id}\n${r.sku}\n${r.variant_id}`;

function parseItem(text: string): BasketItem | RejectReason {
  const parts = text.split(":");
  if (parts.length !== 4) return "malformed";
  const [supplier, sku, variant, qty] = parts.map((p) => p.trim());
  if (!HEX32.test(supplier)) return "supplier";
  if (!sku || length(sku) > MAX_FIELD) return "sku";
  if (!variant || length(variant) > MAX_FIELD) return "variant";
  const n = DIGITS.test(qty) ? Number(qty) : NaN;
  if (!(n >= 1 && n <= MAX_QTY)) return "qty";
  return { supplier_id: supplier.toLowerCase(), sku, variant_id: variant, qty: n };
}

/** `region` and `items` as URLSearchParams gives them (decoded once). */
export function parseBasket(region: string | null, items: string | null): ParsedBasket {
  const code = (region ?? "").trim().toUpperCase();
  const out: ParsedBasket = { region: REGION.test(code) ? code : null, items: [], rejected: [], tooMany: null };
  const texts = (items ?? "")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
  if (texts.length > MAX_ITEMS) {
    out.tooMany = texts.length;
    return out;
  }
  const seen = new Map<string, BasketItem>();
  texts.forEach((text, i) => {
    const item = parseItem(text);
    if (typeof item === "string") {
      out.rejected.push({ position: i + 1, text, reason: item });
      return;
    }
    // The same product and variant twice: one line (5.7 refuses a line listed twice).
    const same = seen.get(refKey(item));
    if (same) same.qty += item.qty;
    else {
      seen.set(refKey(item), item);
      out.items.push(item);
    }
  });
  return out;
}

/** The query string of a page URL ("?region=GB&items=…"). */
export function parseBasketQuery(query: string): ParsedBasket {
  const params = new URLSearchParams(query);
  return parseBasket(params.get("region"), params.get("items"));
}

/** The basket's query string, encoded as the app encodes it (one encoding of the whole value). */
export function basketQuery(region: string, items: BasketItem[]): string {
  const value = items.map((i) => `${i.supplier_id}:${i.sku}:${i.variant_id}:${i.qty}`).join(",");
  return `?region=${encodeURIComponent(region)}&items=${encodeURIComponent(value)}`;
}

/** Availability states that can be ordered (none sent = not tracked = in stock). */
export function canOrder(state: string | null | undefined): boolean {
  return state == null || state === "in_stock" || state === "low_stock" || state === "made_to_order";
}

export interface TotalLine {
  ref: ItemRef;
  qty: number;
  price: MoneyLike | null;
  /** False for a line that is not found, not sold in the region or not available. */
  included: boolean;
}

/** One total per currency, in the order the currencies first appear. */
export function totalsByCurrency(lines: TotalLine[]): MoneyLike[] {
  const totals = new Map<string, MoneyLike>();
  for (const l of lines) {
    if (!l.included || !l.price) continue;
    const t = totals.get(l.price.currency);
    if (t) t.amount += l.price.amount * l.qty;
    else totals.set(l.price.currency, { amount: l.price.amount * l.qty, currency: l.price.currency, exponent: l.price.exponent });
  }
  return [...totals.values()];
}

export interface OrderLineOut extends ItemRef {
  qty: number;
  price_seen: { amount: number; currency: string };
}

/** 5.7's lines: the included, priced lines, one per product and variant, each with the price shown. */
export function orderLines(lines: TotalLine[]): OrderLineOut[] {
  const out = new Map<string, OrderLineOut>();
  for (const l of lines) {
    if (!l.included || !l.price) continue;
    const same = out.get(refKey(l.ref));
    if (same) same.qty += l.qty;
    else
      out.set(refKey(l.ref), {
        supplier_id: l.ref.supplier_id,
        sku: l.ref.sku,
        variant_id: l.ref.variant_id,
        qty: l.qty,
        price_seen: { amount: l.price.amount, currency: l.price.currency },
      });
  }
  return [...out.values()];
}

/** {size: "3-seater", colour: "Oat"} → "3-seater, Oat". */
export function variantLabel(options: Record<string, string> | null | undefined): string {
  return Object.values(options ?? {})
    .filter(Boolean)
    .join(", ");
}

/** 32 hex for 5.7's Idempotency-Key (contract §8). */
export function newIdempotencyKey(): string {
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
