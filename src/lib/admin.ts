"use client";

// Admin calls (users.is_admin only; the API answers 403 to everyone else).
import { api } from "@/lib/api";

export const GROWTH_METRICS = ["signups", "downloads", "trials", "checkouts", "paid"] as const;
export type GrowthMetric = (typeof GROWTH_METRICS)[number];

export type GrowthDay = { day: string } & Record<GrowthMetric, number>;

export interface Growth {
  from: string;
  to: string;
  days: GrowthDay[];
  totals: Record<GrowthMetric, number>;
}

function isoDay(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Daily conversions for the last `days` UTC days, today included. */
export function getGrowth(days: number): Promise<Growth> {
  const to = new Date();
  const from = new Date(to.getTime() - (days - 1) * 86_400_000);
  return api<Growth>(`/admin/growth?from=${isoDay(from)}&to=${isoDay(to)}`);
}
