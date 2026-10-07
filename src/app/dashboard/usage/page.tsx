"use client";

import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { UsageChart } from "@/components/dashboard/UsageChart";
import { UsageMeter } from "@/components/dashboard/UsageMeter";
import { useApiData } from "@/components/dashboard/useApiData";
import { formatDate } from "@/lib/api";
import { getUsage } from "@/lib/developer";

const nf = new Intl.NumberFormat("en-US");

function Breakdown({ title, rows }: { title: string; rows: Record<string, number> }) {
  const entries = Object.entries(rows).sort((a, b) => b[1] - a[1]);
  return (
    <Panel>
      <h2 className="font-semibold">{title}</h2>
      {entries.length === 0 ? (
        <p className="mt-4 text-sm text-text-muted">No requests yet this month.</p>
      ) : (
        <table className="mt-4 w-full text-sm">
          <tbody>
            {entries.map(([name, count]) => (
              <tr key={name} className="border-t border-border first:border-t-0">
                <td className="py-2 pr-4 font-mono text-text-secondary">{name}</td>
                <td className="py-2 text-right tabular-nums text-text-primary">{nf.format(count)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}

export default function UsagePage() {
  const { data, error, loading } = useApiData(getUsage);

  return (
    <>
      <PageHeader
        title="Usage"
        description={
          data
            ? `Billing period ${formatDate(data.period_start)} – ${formatDate(data.period_end)} (UTC). Every API call counts, across all your keys.`
            : "Requests made with your API keys this month."
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
          <Panel className="mb-6">
            <UsageMeter used={data.used} limit={data.limit} />
          </Panel>
          <Panel className="mb-6">
            <h2 className="mb-6 font-semibold">Daily API requests</h2>
            <UsageChart data={data.daily} />
          </Panel>
          <div className="grid gap-6 md:grid-cols-2">
            <Breakdown title="By endpoint" rows={data.by_endpoint} />
            <Breakdown title="By key" rows={data.by_key} />
          </div>
        </div>
      )}
    </>
  );
}
