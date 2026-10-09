"use client";

import { useEffect, useState } from "react";
import { ErrorNote, PageHeader, Panel, useDashboardUser } from "@/components/dashboard/DashboardShell";
import { UsageChart } from "@/components/dashboard/UsageChart";
import { getGrowth, GROWTH_METRICS, type Growth, type GrowthMetric } from "@/lib/admin";
import { cn } from "@/lib/utils";

const nf = new Intl.NumberFormat("en-US");

function formatDay(day: string): string {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

const LABEL: Record<GrowthMetric, { title: string; unit: string; note: string }> = {
  signups: { title: "Sign-ups", unit: "sign-ups", note: "accounts created" },
  downloads: { title: "Downloads", unit: "downloads", note: "installer downloads" },
  trials: { title: "Trials", unit: "trials", note: "Pro trials started" },
  checkouts: { title: "Checkouts", unit: "checkouts", note: "checkouts opened" },
  paid: { title: "Paid", unit: "payments", note: "payments confirmed" },
};

const RANGES = [7, 30, 90] as const;

/**
 * Admin Growth panel: conversions counted from the platform's own records
 * (no browser tracking), per UTC day. Totals as stat tiles; one metric at a
 * time as daily bars (one series, one axis) with a table view.
 */
export default function GrowthPage() {
  const user = useDashboardUser();
  const [days, setDays] = useState<(typeof RANGES)[number]>(30);
  const [metric, setMetric] = useState<GrowthMetric>("signups");
  const [data, setData] = useState<Growth | null>(null);
  const [error, setError] = useState<string | null>(null);
  // The range the shown answer is for; loading while it differs from `days`
  // (the old numbers stay visible, dimmed, until the new ones arrive).
  const [loaded, setLoaded] = useState<number | null>(null);
  const loading = loaded !== days;

  useEffect(() => {
    if (!user.is_admin) return;
    let cancelled = false;
    getGrowth(days)
      .then((g) => {
        if (cancelled) return;
        setData(g);
        setError(null);
        setLoaded(days);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Something went wrong.");
        setLoaded(days);
      });
    return () => {
      cancelled = true;
    };
  }, [user.is_admin, days]);

  if (!user.is_admin) {
    return (
      <>
        <PageHeader title="Growth" />
        <ErrorNote message="This page is for Truebex admins." />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Growth"
        description={
          data
            ? `${formatDay(data.from)} – ${formatDay(data.to)} (UTC days). Counted from account, download and billing records; no personal data.`
            : "Sign-ups, downloads, trials and checkouts per day."
        }
        actions={
          <div role="radiogroup" aria-label="Range" className="inline-flex shrink-0 rounded-full border border-border bg-surface p-1">
            {RANGES.map((r) => (
              <button
                key={r}
                type="button"
                role="radio"
                aria-checked={days === r}
                onClick={() => setDays(r)}
                className={cn(
                  "whitespace-nowrap rounded-full px-3 py-1 text-sm transition-colors",
                  days === r ? "bg-accent text-background" : "text-text-secondary hover:text-text-primary"
                )}
              >
                {r} days
              </button>
            ))}
          </div>
        }
      />
      {error && (
        <div className="mb-6">
          <ErrorNote message={error} />
        </div>
      )}
      {!data ? (
        <p className="text-sm text-text-muted">{loading ? "Loading…" : ""}</p>
      ) : (
        <div className={loading ? "opacity-60 transition-opacity" : "transition-opacity"}>
          <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            {GROWTH_METRICS.map((m) => (
              <Panel key={m} className="p-4 md:p-5">
                <p className="text-sm text-text-muted">{LABEL[m].title}</p>
                <p className="mt-2 text-3xl font-semibold tabular-nums text-text-primary">
                  {nf.format(data.totals[m])}
                </p>
                <p className="mt-1 text-xs text-text-muted">{LABEL[m].note}</p>
              </Panel>
            ))}
          </div>
          <Panel>
            <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <h2 className="font-semibold">{LABEL[metric].title} per day</h2>
              <div role="radiogroup" aria-label="Metric" className="flex flex-wrap gap-1">
                {GROWTH_METRICS.map((m) => (
                  <button
                    key={m}
                    type="button"
                    role="radio"
                    aria-checked={metric === m}
                    onClick={() => setMetric(m)}
                    className={cn(
                      "rounded-full border px-3 py-1 text-xs transition-colors",
                      metric === m
                        ? "border-accent/40 bg-accent/10 text-accent"
                        : "border-border text-text-secondary hover:text-text-primary"
                    )}
                  >
                    {LABEL[m].title}
                  </button>
                ))}
              </div>
            </div>
            <UsageChart
              data={data.days.map((d) => ({ day: d.day, count: d[metric] }))}
              label={`${LABEL[metric].title} per day`}
              unit={LABEL[metric].unit}
            />
          </Panel>
        </div>
      )}
    </>
  );
}
