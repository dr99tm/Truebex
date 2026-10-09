"use client";

// Dashboard calls: API keys, usage, billing.
import { api } from "@/lib/api";

export interface ApiKey {
  id: number;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface CreatedApiKey extends ApiKey {
  key: string;
}

export interface UsageSummary {
  plan: string;
  period_start: string;
  period_end: string;
  used: number;
  limit: number;
  remaining: number;
  daily: { day: string; count: number }[];
  by_endpoint: Record<string, number>;
  by_key: Record<string, number>;
}

export type Provider = "paddle" | "stripe";
export type Interval = "month" | "year";

export interface TierPrice {
  interval: Interval;
  currency: string;
  /** Per seat, in minor units of `currency`. */
  amount_minor: number;
}

export interface PlanInfo {
  id: string;
  name: string;
  purchasable: boolean;
  per_seat: boolean;
  min_seats: number;
  prices: TierPrice[];
}

export interface FoundingOffer {
  enabled: boolean;
  total: number;
  remaining: number;
  discount_percent: number;
  ends_at: string | null;
  tiers: string[];
}

export interface Catalog {
  tiers: PlanInfo[];
  founding: FoundingOffer;
  /** The provider checkout uses, or null while online payment is not set up. */
  provider: Provider | null;
  currencies: string[];
}

export interface Subscription {
  tier: string;
  interval: Interval | null;
  seats: number;
  status: string;
  // "paddle" | "stripe" | "wayl", or "trial": the one 14-day Pro trial
  // (started from the app).
  provider: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  founding: boolean;
  can_manage: boolean;
  currency: string | null;
}

export interface Payment {
  reference: string;
  /** Past rows keep the provider they were paid through. */
  provider: string;
  plan: string;
  amount: number;
  currency: string;
  status: "pending" | "paid" | "failed" | "canceled";
  created_at: string;
  paid_at: string | null;
  interval: Interval | null;
  seats: number | null;
  tax_minor: number | null;
}

export interface Invoice {
  id: string;
  number: string | null;
  issued_at: string | null;
  total_minor: number;
  tax_minor: number;
  currency: string;
  status: string;
  /** Absolute (provider) or relative to the API ("/billing/invoices/…"). */
  pdf_url: string | null;
}

export interface CheckoutRequest {
  tier: string;
  interval: Interval;
  currency: string;
  seats: number;
  coupon?: string;
  consent: { version: string; accepted: true };
}

export const listKeys = () => api<ApiKey[]>("/keys");
export const createKey = (name: string) =>
  api<CreatedApiKey>("/keys", { method: "POST", json: { name } });
export const revokeKey = (id: number) =>
  api<ApiKey>(`/keys/${id}`, { method: "DELETE" });

export const getUsage = () => api<UsageSummary>("/usage");

export const getCatalog = () => api<Catalog>("/billing/plans", { auth: false });
export const getSubscription = () => api<Subscription>("/billing/subscription");
export const listPayments = () => api<Payment[]>("/billing/payments");
export const listInvoices = () => api<Invoice[]>("/billing/invoices");
export const startCheckout = (body: CheckoutRequest) =>
  api<{ url: string; reference: string; founding: boolean }>("/billing/checkout", {
    method: "POST",
    json: body,
  });
export const changeSeats = (seats: number) =>
  api<Subscription>("/billing/seats", { method: "POST", json: { seats } });
export const changePlan = (change: { tier?: string; interval?: Interval }) =>
  api<Subscription>("/billing/change", { method: "POST", json: change });
export const refreshPayment = (reference: string) =>
  api<Payment>(`/billing/payments/${encodeURIComponent(reference)}/refresh`, {
    method: "POST",
  });
export const openBillingPortal = () =>
  api<{ url: string }>("/billing/portal", { method: "POST" });

/** An amount in minor units, with the currency's own decimals (pence, cents;
 *  none for currencies without them). */
export function formatMoney(amountMinor: number, currency: string): string {
  let fmt: Intl.NumberFormat;
  try {
    fmt = new Intl.NumberFormat("en-GB", { style: "currency", currency });
  } catch {
    return `${amountMinor} ${currency}`;
  }
  const digits = fmt.resolvedOptions().maximumFractionDigits ?? 2;
  return fmt.format(amountMinor / 10 ** digits);
}
