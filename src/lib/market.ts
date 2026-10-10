"use client";

// The marketplace API (contract marketplace-api v1.1) as the website uses it:
// the buyer's orders and requests (5.7-5.10 with a session), the checkout
// page, and the admin tools under /admin/market. Money is always an integer
// of minor units with its currency's exponent; it is only turned into text
// here, for display.
import { api } from "@/lib/api";

const CONTRACT = { "X-Truebex-Contract": "marketplace-api/1.1" };

export interface Money {
  amount: number;
  currency: string;
  exponent: number;
}

export interface Price extends Money {
  region: string;
  includes_tax: boolean;
  tax_rate_bp: number;
  at: string | null;
}

export interface OrderLine {
  supplier_id: string;
  product_id: string;
  sku: string;
  variant_id: string;
  name: string;
  qty: number;
  price: Price;
  quoted_price: Price | null;
  total: Money;
}

export interface OrderSupplier {
  supplier_id: string;
  supplier_name: string | null;
  state: string;
  lines: number;
  subtotal: Money;
  delivery: Money;
  tax: Money;
  total: Money;
  delivery_days: { min: number | null; max: number | null };
  quote: { quoted_at: string | null; valid_until: string | null; message: string | null } | null;
  reason: string | null;
}

export interface MarketOrder {
  order_id: string;
  kind: "order" | "quote";
  state: string;
  payment: "platform" | "offline";
  region: string;
  currency: string;
  exponent: number;
  checkout_url: string | null;
  project: { name?: string | null; project_id?: string | null };
  delivery: { country: string; city?: string | null; postcode?: string | null; address?: string | null };
  contact?: { name: string; email: string; phone?: string | null; message?: string | null };
  suppliers: OrderSupplier[];
  lines: OrderLine[];
  subtotal: Money;
  delivery_total: Money;
  tax: Money;
  total: Money;
  quote_id: string | null;
  order_ref: string | null;
  expires_at: string | null;
  paid_at: string | null;
  created_at: string;
  updated_at: string;
}

/** 129900, AED, 2 → "AED 1,299.00" (each currency's own exponent; never assumes 2). */
export function formatMinor(amount: number, currency: string, exponent: number): string {
  const scale = 10 ** exponent;
  const sign = amount < 0 ? "-" : "";
  const abs = Math.abs(amount);
  const whole = Math.floor(abs / scale).toLocaleString("en-US");
  const frac = exponent > 0 ? `.${String(abs % scale).padStart(exponent, "0")}` : "";
  return `${sign}${currency} ${whole}${frac}`;
}

export const formatMoney = (m: Money): string => formatMinor(m.amount, m.currency, m.exponent);

// --- The buyer -------------------------------------------------------------

export const getOrder = (orderId: string) =>
  api<MarketOrder>(`/market/orders/${encodeURIComponent(orderId)}`, { headers: CONTRACT });

export const listOrders = () =>
  api<{ orders: MarketOrder[]; next_cursor: string | null }>("/market/orders", { headers: CONTRACT });

export const cancelOrder = (orderId: string) =>
  api<MarketOrder>(`/market/orders/${encodeURIComponent(orderId)}/cancel`, { method: "POST", headers: CONTRACT });

export const acceptQuote = (orderId: string) =>
  api<MarketOrder>(`/market/orders/${encodeURIComponent(orderId)}/accept`, { method: "POST" });

/** The payment provider's page for this order (opened in the same tab). */
export const startOrderCheckout = (orderId: string) =>
  api<{ url: string; order_id: string }>(`/market/checkout/${encodeURIComponent(orderId)}`, { method: "POST" });

/** Back from the payment page: the server asks the provider itself. */
export const refreshOrderCheckout = (orderId: string) =>
  api<MarketOrder>(`/market/checkout/${encodeURIComponent(orderId)}/refresh`, { method: "POST" });

// --- Admin ------------------------------------------------------------------

export interface AdminSupplier {
  supplier_id: string;
  name: string;
  legal_name: string | null;
  country: string;
  website: string | null;
  contact_email: string | null;
  regions: string[];
  status: "applied" | "verified" | "suspended";
  status_reason: string | null;
  commission_bp: number;
  listing_plan: string | null;
  connect_account_id: string | null;
  connect_ready: boolean;
  orderable: boolean;
  members: { email: string; role: string }[];
  products: Record<string, number>;
  created_at: string;
}

export interface AdminProduct {
  product_id: string;
  supplier_name: string | null;
  supplier_status: string | null;
  sku: string;
  name: string;
  kind: string;
  category: string;
  app_path: string | null;
  category_known: boolean;
  thumbnail_url: string | null;
  images: string[];
  status: string;
  review_note: string | null;
  variants: { variant_id: string; options: Record<string, string>; dims_mm: number[] | null; status: string; geometry: { format: string; bytes: number } | null }[];
  updated_at: string;
}

export interface AdminReview {
  review_id: string;
  product_name: string;
  rating: number;
  text: string;
  author: string;
  status: string;
  created_at: string;
}

export interface Statement {
  statement_id: string;
  supplier_name: string | null;
  month: string;
  orders: number;
  commission: Money;
  listing_fee: Money;
  total: Money;
  state: string;
  invoice_ref: string | null;
}

export interface Commission {
  order_id: string;
  supplier_name: string | null;
  rate_bp: number;
  base: Money;
  amount: Money;
  state: string;
  created_at: string;
}

export interface FeedReport {
  feed_id: string;
  supplier_name?: string | null;
  state: string;
  rows: number;
  created: number;
  updated: number;
  unchanged: number;
  rejected: number;
  hidden: number;
  errors: { row: number; column: string; code: string; value: string }[];
  format: string;
  mode: string;
  source: string;
  detail: string | null;
  created_at: string;
}

export interface MarketSummary {
  suppliers: Record<string, number>;
  products: Record<string, number>;
  reviews: Record<string, number>;
  orders: Record<string, number>;
  quotes: Record<string, number>;
  payments_enabled: boolean;
  stripe_ready: boolean;
}

const post = <T,>(path: string, json?: unknown) => api<T>(path, { method: "POST", json });

export const adminMarket = {
  summary: () => api<MarketSummary>("/admin/market/summary"),
  suppliers: () => api<{ suppliers: AdminSupplier[] }>("/admin/market/suppliers"),
  editSupplier: (id: string, json: Record<string, unknown>) =>
    api<AdminSupplier>(`/admin/market/suppliers/${id}`, { method: "PATCH", json }),
  connectLink: (id: string) => post<{ url: string }>(`/admin/market/suppliers/${id}/connect`),
  products: (status: string) =>
    api<{ products: AdminProduct[] }>(`/admin/market/products?status=${encodeURIComponent(status)}`),
  approve: (id: string) => post<AdminProduct>(`/admin/market/products/${id}/approve`),
  reject: (id: string, reason: string) => post<AdminProduct>(`/admin/market/products/${id}/reject`, { reason }),
  withdraw: (id: string, reason: string) => post<AdminProduct>(`/admin/market/products/${id}/withdraw`, { reason }),
  reviews: (status: string) =>
    api<{ reviews: AdminReview[] }>(`/admin/market/reviews?status=${encodeURIComponent(status)}`),
  publishReview: (id: string) => post<AdminReview>(`/admin/market/reviews/${id}/publish`),
  hideReview: (id: string) => post<AdminReview>(`/admin/market/reviews/${id}/hide`),
  orders: () => api<{ orders: MarketOrder[] }>("/admin/market/orders"),
  quoteFor: (orderId: string, supplierId: string, json: Record<string, unknown>) =>
    post<MarketOrder>(`/admin/market/orders/${orderId}/suppliers/${supplierId}/quote`, json),
  actFor: (orderId: string, supplierId: string, action: string, reason?: string) =>
    post<MarketOrder>(`/admin/market/orders/${orderId}/suppliers/${supplierId}/${action}`, reason ? { reason } : {}),
  commissions: () => api<{ commissions: Commission[]; statements: Statement[] }>("/admin/market/commissions"),
  makeStatements: () => post<{ statements: Statement[] }>("/admin/market/commissions/statements"),
  feeds: () => api<{ feeds: FeedReport[] }>("/admin/market/feeds"),
};
