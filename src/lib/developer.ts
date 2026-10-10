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
  /** The billing intervals with a founding price (absent from older APIs: both). */
  intervals?: Interval[];
}

/** PF2b: the subscription consumer rules the API has switched on. */
export interface BillingRules {
  wording_approved: boolean;
  consent_variant: "digital_content" | "service";
  /** The consent version checkout must carry now. */
  consent_version: string;
  key_info_version: string | null;
  eu_withdrawal: boolean;
  renewal_notices: boolean;
}

export interface Catalog {
  tiers: PlanInfo[];
  founding: FoundingOffer;
  /** The provider checkout uses, or null while online payment is not set up. */
  provider: Provider | null;
  currencies: string[];
  /** Absent until the API answers (the static catalogue has none). */
  rules?: BillingRules;
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
  // PF2b: cancel in Billing (the easy exit); the renewal cooling-off and the
  // EU withdrawal period end then (null when not offered).
  can_cancel: boolean;
  cooling_off_until: string | null;
  withdrawal_until: string | null;
}

/** A cancellation made in Billing (PF2b). The plan changes once the payment
 *  provider confirms it. */
export interface ExitResult {
  kind: "cancel" | "cooling_off" | "withdrawal";
  requested_at: string;
  effective_at: string | null;
  refund_minor: number | null;
  currency: string | null;
  status: "done" | "processing";
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
  // PF2b: what the buyer agreed to (key_info only once the wording is approved).
  consent_version?: string | null;
  key_info?: string | null;
  key_info_at?: string | null;
  business?: boolean | null;
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
  // PF2b, once the wording is approved: the key information was acknowledged.
  key_info?: { version: string; acknowledged: true };
  business?: boolean;
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
export const getPayment = (reference: string) =>
  api<Payment>(`/billing/payments/${encodeURIComponent(reference)}`);
/** Cancel at the period end, or (refund) now within the renewal cooling-off. */
export const cancelSubscription = (refund = false) =>
  api<ExitResult>("/billing/cancel", { method: "POST", json: { confirm: true, refund } });
export const withdrawContract = () =>
  api<ExitResult>("/billing/withdraw", { method: "POST", json: { confirm: true } });

/** Fill `{name}` slots of a wording text (BILLING.rules, BILLING.exit). */
export function fillWording(text: string, values: Record<string, string | number>): string {
  return text.replace(/\{(\w+)\}/g, (slot, key: string) =>
    key in values ? String(values[key]) : slot
  );
}

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
