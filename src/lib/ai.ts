"use client";

// The AI tier (PF11) as the website uses it: the Cloud page's AI credits
// section (balance, recent turns, buying a credit pack through PF2's
// checkout) and the render admin's AI panel (spend by alias, the self-hosted
// inference servers). Server: server/app/routers/ai_account.py.
import { ApiError, api } from "@/lib/api";
import { ADMIN_AI, BILLING, CLOUD, CLOUD_AI } from "@/lib/constants";

export interface AiBalance {
  /** Allowance left plus bought credits left; null when the plan has no monthly limit. */
  credits_remaining: number | null;
  /** null: no monthly limit. */
  allowance_monthly: number | null;
  top_up_remaining: number;
  resets_at: string;
  plan: string;
  top_up_url: string;
  allowance_remaining: number;
}

export interface AiTurn {
  at: string;
  /** Our own alias ("truebex-assist"); `model` is the provider's and stays off the page. */
  alias: string;
  credits: number;
  tool_names: string[];
  model: string;
  stop_reason: string | null;
  input_tokens: number;
  output_tokens: number;
}

export interface CreditPack {
  id: string;
  credits: number;
  amount_minor: number;
  currency: string;
}

export type TopUpState = "pending" | "credited" | "canceled";

export interface TopUp {
  reference: string;
  pack: string;
  credits: number;
  state: TopUpState;
  created_at: string;
}

export interface AiAccount {
  feature: boolean;
  plan: string;
  plan_needed: string;
  balance: AiBalance | null;
  turns: AiTurn[];
  currency: string;
  currencies: string[];
  packs: CreditPack[];
  top_ups: TopUp[];
}

export const getAiAccount = (currency?: string) =>
  api<AiAccount>(`/account/ai${currency ? `?currency=${encodeURIComponent(currency)}` : ""}`);

/** Starts a checkout for a pack; the browser then goes to `url`. The consent
 *  version is the billing page's (the server checks the same one). */
export const startTopUp = (pack: string, currency: string) =>
  api<{ url: string; reference: string }>("/account/ai/top-ups", {
    method: "POST",
    json: { pack, currency, consent: { version: BILLING.consent.version, accepted: true } },
  });

// --- the admin ----------------------------------------------------------------------

export interface AiAlias {
  alias: string;
  adapter: string;
  model: string;
  enabled: boolean;
  credits_per_mtok: { input: number; output: number; cache_read: number; cache_write: number };
}

export interface AiSpendRow {
  alias: string;
  served_by: string;
  turns: number;
  credits: number;
  provider_cost_usd: number;
  input_tokens: number;
  output_tokens: number;
}

export type InferenceState = "warm" | "cold" | "stopped";

export interface InferenceServer {
  server_id: string;
  alias: string;
  base_url: string;
  state: InferenceState;
  warm_until: string | null;
  last_probe_at: string | null;
  last_turn_at: string | null;
}

export interface AiAdminOverview {
  period_start: string;
  aliases: AiAlias[];
  spend: AiSpendRow[];
  servers: InferenceServer[];
  gpu_ai_wanted: number | null;
}

export const getAiAdmin = () => api<AiAdminOverview>("/admin/ai");

export const addInferenceServer = (serverId: string, alias: string, baseUrl: string) =>
  api<InferenceServer>("/admin/ai/servers", {
    method: "POST",
    json: { server_id: serverId, alias, base_url: baseUrl },
  });

export const removeInferenceServer = (serverId: string) =>
  api<{ removed: string }>(`/admin/ai/servers/${encodeURIComponent(serverId)}`, { method: "DELETE" });

// --- formatting -----------------------------------------------------------------------

/** "12,500": whole credits with thousands separators. */
export function formatCredits(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 }).format(value);
}

/** "$1.2345": provider cost, up to four decimals (one turn can cost a fraction of a cent). */
export function formatUsd(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(value);
}

/** A job kind's label: PF6's kinds, then PF11's analysis kinds, else the id. */
export function kindLabel(kind: string): string {
  return (
    (CLOUD.kinds as Record<string, string>)[kind] ?? (CLOUD_AI.kinds as Record<string, string>)[kind] ?? kind
  );
}

export function aiError(err: unknown): string {
  if (err instanceof ApiError && err.code === "plan_required") return CLOUD_AI.locked.text;
  return err instanceof Error && err.message ? err.message : CLOUD_AI.errors.generic;
}

/** The admin panel's errors (the server's own detail, which names the field). */
export function adminAiError(err: unknown): string {
  return err instanceof Error && err.message ? err.message : ADMIN_AI.errors.generic;
}
