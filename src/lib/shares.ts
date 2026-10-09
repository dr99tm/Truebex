"use client";

// Share links (contract share-bundle v1.0, 5.6-5.9) as the website's
// dashboard uses them: list, one share with its visits, extend, end.
import { api } from "@/lib/api";

const CONTRACT = { "X-Truebex-Contract": "share-bundle/1.0" };

export type ShareState = "uploading" | "live" | "expired" | "revoked";

export interface ShareVisits {
  total: number;
  unique: number;
  last_at: string | null;
  by_day?: { day: string; count: number; unique?: number }[];
}

export interface Share {
  share_id: string;
  slug: string | null;
  url: string | null;
  title: string;
  state: ShareState;
  created_at: string;
  published_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  bytes: number;
  watermark: boolean;
  visits: ShareVisits;
}

export interface ShareLimits {
  share_links: number | null;
  share_days: number;
  share_bytes: number;
}

export const listShares = () =>
  api<{ shares: Share[]; limits: ShareLimits }>("/shares", { headers: CONTRACT });

export const getShare = (id: string) => api<Share>(`/shares/${encodeURIComponent(id)}`, { headers: CONTRACT });

/** Move the expiry to `days` from now (the plan's longest, by default). */
export const extendShare = (id: string, days: number) =>
  api<Share>(`/shares/${encodeURIComponent(id)}`, {
    method: "PATCH",
    json: { expires_at: new Date(Date.now() + days * 86_400_000 - 60_000).toISOString() },
    headers: CONTRACT,
  });

export const revokeShare = (id: string) =>
  api<Share>(`/shares/${encodeURIComponent(id)}`, { method: "DELETE", headers: CONTRACT });

/** Live and uploading shares first, then ended ones; newest first in each. */
export function sortShares(shares: Share[]): Share[] {
  const open = (s: Share) => (s.state === "live" || s.state === "uploading" ? 0 : 1);
  return [...shares].sort((a, b) => open(a) - open(b) || b.created_at.localeCompare(a.created_at));
}

/** The last `n` UTC days, oldest first, with each day's count (0 when none). */
export function fillDays(byDay: { day: string; count: number }[], n = 30, now = new Date()): { day: string; count: number }[] {
  const counts = new Map(byDay.map((d) => [d.day, d.count]));
  const out = [];
  for (let i = n - 1; i >= 0; i--) {
    const day = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - i)).toISOString().slice(0, 10);
    out.push({ day, count: counts.get(day) ?? 0 });
  }
  return out;
}
