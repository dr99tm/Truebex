"use client";

import { useEffect, useState } from "react";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { UsageChart } from "@/components/dashboard/UsageChart";
import { Field, inputClass, useMember } from "@/components/supplier/SupplierShell";
import { SUPPLIER } from "@/lib/constants";
import { formatMoney, supplierApi, type Analytics, type AnalyticsCounts } from "@/lib/supplier";
import { cn } from "@/lib/utils";

const A = SUPPLIER.analytics;
const METRICS = ["views", "impressions", "geometry_downloads", "quotes", "orders"] as const;
type Metric = (typeof METRICS)[number];
const nf = new Intl.NumberFormat("en-US");

function iso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function daysBack(n: number): { from: string; to: string } {
  const to = new Date();
  const from = new Date(to.getTime() - (n - 1) * 86_400_000);
  return { from: iso(from), to: iso(to) };
}

// Counts per day and product for a date range and region: search
// impressions, product views, placements (3D downloads), requests for quote,
// orders and their value. No buyer is identified.
export default function AnalyticsPage() {
  const { me } = useMember();
  const [range, setRange] = useState(() => daysBack(30));
  const [region, setRegion] = useState("");
  const [metric, setMetric] = useState<Metric>("views");
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    supplierApi
      .analytics(range.from, range.to, region)
      .then((res) => {
        if (cancelled) return;
        setData(res);
        setError("");
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
      });
    return () => {
      cancelled = true;
    };
  }, [range, region]);

  const regions = me.supplier?.regions ?? [];
  const total = (t: AnalyticsCounts) => t.impressions + t.views + t.geometry_downloads + t.quotes + t.orders;

  return (
    <>
      <PageHeader title={A.title} description={A.description} />
      <div className="space-y-6">
        <div className="flex flex-wrap items-end gap-3">
          {[7, 30, 90].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setRange(daysBack(n))}
              className="rounded-full border border-border px-3 py-1 text-sm text-text-secondary hover:text-text-primary"
            >
              {n === 7 ? A.last7 : n === 30 ? A.last30 : A.last90}
            </button>
          ))}
          <Field label={A.from}>
            <input type="date" value={range.from} max={range.to} onChange={(e) => e.target.value && setRange({ ...range, from: e.target.value })} className={cn(inputClass, "w-40")} />
          </Field>
          <Field label={A.to}>
            <input type="date" value={range.to} min={range.from} onChange={(e) => e.target.value && setRange({ ...range, to: e.target.value })} className={cn(inputClass, "w-40")} />
          </Field>
          <Field label={A.region}>
            <select value={region} onChange={(e) => setRegion(e.target.value)} className={cn(inputClass, "w-40")}>
              <option value="">{A.allRegions}</option>
              {regions.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </Field>
        </div>
        {error && <ErrorNote message={error} />}
        {data && (
          <>
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {METRICS.map((m) => (
                <div key={m} className="rounded-[var(--radius-card)] border border-border bg-surface p-3">
                  <dt className="text-xs text-text-muted">{A.metrics[m]}</dt>
                  <dd className="text-xl font-semibold tabular-nums">{nf.format(data.totals[m])}</dd>
                </div>
              ))}
              <div className="rounded-[var(--radius-card)] border border-border bg-surface p-3">
                <dt className="text-xs text-text-muted">{A.orderValue}</dt>
                <dd className="text-sm font-semibold tabular-nums">
                  {data.totals.order_value.length ? data.totals.order_value.map((v) => <span key={v.currency} className="block">{formatMoney(v)}</span>) : "—"}
                </dd>
              </div>
            </dl>

            <Panel>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <h2 className="font-semibold">{A.metrics[metric]}</h2>
                <select aria-label={A.metric} value={metric} onChange={(e) => setMetric(e.target.value as Metric)} className={cn(inputClass, "w-48")}>
                  {METRICS.map((m) => (
                    <option key={m} value={m}>
                      {A.metrics[m]}
                    </option>
                  ))}
                </select>
              </div>
              <UsageChart
                data={data.days.map((d) => ({ day: d.day, count: d[metric] }))}
                unit={A.metrics[metric].toLowerCase()}
                label={A.metrics[metric]}
              />
            </Panel>

            <Panel>
              <h2 className="font-semibold">{A.product}</h2>
              {data.products.length === 0 || total(data.totals) === 0 ? (
                <p className="mt-2 text-sm text-text-muted">{A.empty}</p>
              ) : (
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-left text-xs text-text-muted">
                      <tr>
                        <th className="px-2 py-2 font-medium">{A.product}</th>
                        {METRICS.map((m) => (
                          <th key={m} className="px-2 py-2 text-right font-medium">
                            {A.metrics[m]}
                          </th>
                        ))}
                        <th className="px-2 py-2 text-right font-medium">{A.orderValue}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.products.map((p) => (
                        <tr key={p.product_id} className="border-t border-border">
                          <td className="px-2 py-2">
                            <p className="text-text-primary">{p.name}</p>
                            <p className="text-xs text-text-muted">{p.sku}</p>
                          </td>
                          {METRICS.map((m) => (
                            <td key={m} className="px-2 py-2 text-right tabular-nums">
                              {nf.format(p[m])}
                            </td>
                          ))}
                          <td className="px-2 py-2 text-right tabular-nums">
                            {p.order_value.map((v) => formatMoney(v)).join(", ") || "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Panel>
          </>
        )}
      </div>
    </>
  );
}
