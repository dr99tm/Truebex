"use client";

// PF7b: what the "Buy this look" basket page asks the API. The regions (5.2)
// and prices (5.5) are the contract's catalogue reads, sent without a
// credential; the lines' names and their `default` variant come from the
// platform route POST /market/basket; the order goes through 5.7 with the
// session and an Idempotency-Key, then on to PF7's checkout page.
import { api } from "@/lib/api";
import type { BasketItem, ItemRef, OrderLineOut } from "@/lib/basket";
import type { MarketOrder, Price } from "@/lib/market";

const CONTRACT = { "X-Truebex-Contract": "marketplace-api/1.1" };

export interface Region {
  region: string;
  name: string;
  currency: string;
  exponent: number;
  tax: { name: string; rate_bp: number; prices_include_tax: boolean };
}

/** 5.2: the regions the marketplace serves. */
export const marketRegions = () => api<{ regions: Region[] }>("/market/regions", { headers: CONTRACT, auth: false });

export interface DescribedLine extends ItemRef {
  status: "found" | "withdrawn" | "not_found";
  product_id?: string;
  name?: string;
  kind?: string;
  supplier_name?: string | null;
  thumbnail_url?: string | null;
  /** False: the supplier takes requests for quote only. */
  orderable?: boolean;
  /** The variant the line stands for (`default` resolved), or null when unknown. */
  variant: { variant_id: string; options: Record<string, string>; resolved: "asked" | "only" | "first" } | null;
  /** The product's versions, when it has several (the page offers the others). */
  variants?: { variant_id: string; options: Record<string, string> }[];
}

/** POST /market/basket: names and resolved variants for ≤ 100 lines. */
export const describeBasket = (region: string, items: ItemRef[]) =>
  api<{ region: string; items: DescribedLine[] }>("/market/basket", {
    method: "POST",
    json: { region, items: items.map(({ supplier_id, sku, variant_id }) => ({ supplier_id, sku, variant_id })) },
    auth: false,
  });

export interface Availability {
  state: string;
  stock: number | null;
  lead_time_days: number | null;
  updated_at: string | null;
}

export interface Substitute {
  product_id: string;
  supplier_id: string;
  supplier_name: string | null;
  sku: string;
  variant_id: string;
  name: string;
  thumbnail_url: string | null;
  price: Price | null;
  availability: Availability | null;
}

export interface PricedLine extends ItemRef {
  price: Price | null;
  availability: Availability | null;
  substitutes: Substitute[];
  /** PF7's per-line status (absent when the line is sold in the region). */
  status?: "not_found" | "withdrawn" | "not_sold_in_region";
}

/** 5.5: prices and availability of the lines for the region (no credential). */
export const priceBasket = (region: string, items: BasketItem[]) =>
  api<{ region: string; at: string; stale_after: string; items: PricedLine[] }>("/market/prices", {
    method: "POST",
    json: { region, items },
    headers: CONTRACT,
    auth: false,
  });

export interface BasketOrderIn {
  kind: "order" | "quote";
  region: string;
  contact: { name: string; email: string; phone: string | null; message: string | null };
  delivery: { country: string; city: string; postcode: string | null; address: string };
  lines: OrderLineOut[];
}

/** 5.7 with the session: a retried click with the same key replays the first order. */
export const placeBasketOrder = (body: BasketOrderIn, idempotencyKey: string) =>
  api<MarketOrder>("/market/orders", {
    method: "POST",
    json: { ...body, project: {} },
    headers: { ...CONTRACT, "Idempotency-Key": idempotencyKey },
  });
