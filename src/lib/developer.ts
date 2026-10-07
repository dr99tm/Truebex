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

export type Provider = "stripe" | "wayl";

export interface PlanInfo {
  id: string;
  name: string;
  price_usd_cents: number | null;
  price_iqd: number | null;
  monthly_requests: number;
  max_api_keys: number;
  purchasable: boolean;
}

export interface Subscription {
  plan: string;
  status: string;
  provider: Provider | null;
  current_period_end: string | null;
  can_manage: boolean;
}

export interface Payment {
  reference: string;
  provider: Provider;
  plan: string;
  amount: number;
  currency: string;
  status: "pending" | "paid" | "failed" | "canceled";
  created_at: string;
  paid_at: string | null;
}

export const listKeys = () => api<ApiKey[]>("/keys");
export const createKey = (name: string) =>
  api<CreatedApiKey>("/keys", { method: "POST", json: { name } });
export const revokeKey = (id: number) =>
  api<ApiKey>(`/keys/${id}`, { method: "DELETE" });

export const getUsage = () => api<UsageSummary>("/usage");

export const getCatalog = () =>
  api<{ plans: PlanInfo[]; providers: Provider[] }>("/billing/plans", {
    auth: false,
  });
export const getSubscription = () => api<Subscription>("/billing/subscription");
export const listPayments = () => api<Payment[]>("/billing/payments");
export const startCheckout = (plan: string, provider: Provider) =>
  api<{ url: string; reference: string }>("/billing/checkout", {
    method: "POST",
    json: { plan, provider },
  });
export const refreshPayment = (reference: string) =>
  api<Payment>(`/billing/payments/${encodeURIComponent(reference)}/refresh`, {
    method: "POST",
  });
export const openBillingPortal = () =>
  api<{ url: string }>("/billing/portal", { method: "POST" });

export function formatMoney(amount: number, currency: string): string {
  if (currency === "USD") {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(amount / 100);
  }
  return `${new Intl.NumberFormat("en-US").format(amount)} ${currency}`;
}
