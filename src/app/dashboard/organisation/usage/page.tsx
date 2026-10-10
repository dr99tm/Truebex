"use client";

import { useEffect, useState } from "react";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { OrgGate } from "@/components/dashboard/OrgContext";
import { errorText, inputClass, tableClass, tdClass, thClass } from "@/components/dashboard/orgUi";
import { getUsage, monthOf, ROLE_NAMES, type MemberUsage, type OrgSummary } from "@/lib/orgs";
import { timeAgo } from "@/lib/time";

export default function UsagePage() {
  return <OrgGate level="admin">{(org) => <UsageView key={org.id} org={org} />}</OrgGate>;
}

const later = (v: number | null) => (v === null ? "—" : v.toLocaleString());

function UsageView({ org }: { org: OrgSummary }) {
  const [month, setMonth] = useState(monthOf);
  const [rows, setRows] = useState<MemberUsage[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    getUsage(org.id, month)
      .then((data) => {
        if (!cancelled) {
          setRows(data);
          setError("");
        }
      })
      .catch((err) => {
        if (!cancelled) setError(errorText(err));
      });
    return () => {
      cancelled = true;
    };
  }, [org.id, month]);

  return (
    <>
      <PageHeader
        title="Member usage"
        description="Who uses what this month: devices, last activity, API requests and floating-seat hours. Cloud storage, panoramas and AI credits appear here once those services start counting them."
        actions={
          <label className="flex items-center gap-2 text-sm text-text-secondary">
            Month
            <input
              type="month"
              value={month}
              max={monthOf()}
              onChange={(e) => e.target.value && setMonth(e.target.value)}
              className={inputClass}
            />
          </label>
        }
      />
      {error && (
        <div className="mb-6">
          <ErrorNote message={error} />
        </div>
      )}
      <Panel>
        {!rows ? (
          <p className="text-sm text-text-muted">Loading…</p>
        ) : (
          <div className="overflow-x-auto">
            <table className={tableClass}>
              <thead className="text-left text-text-muted">
                <tr>
                  <th className={thClass}>Member</th>
                  <th className={thClass}>Devices</th>
                  <th className={thClass}>Last active</th>
                  <th className={thClass}>API requests</th>
                  <th className={thClass}>Floating hours</th>
                  <th className={thClass}>Cloud storage</th>
                  <th className={thClass}>Panoramas</th>
                  <th className={thClass}>AI credits</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.user_id} className="border-t border-border">
                    <td className="py-3 pr-4">
                      <span className="text-text-primary">{r.name || r.email}</span>
                      <span className="block text-xs text-text-muted">{ROLE_NAMES[r.role]}</span>
                    </td>
                    <td className={tdClass}>{r.devices}</td>
                    <td className={tdClass}>{timeAgo(r.last_active_at)}</td>
                    <td className={tdClass}>{r.api_requests.toLocaleString()}</td>
                    <td className={tdClass}>{r.floating_hours.toFixed(1)} h</td>
                    <td className={tdClass}>{r.storage_bytes === null ? "—" : `${(r.storage_bytes / 1e9).toFixed(2)} GB`}</td>
                    <td className={tdClass}>{later(r.panoramas)}</td>
                    <td className={tdClass}>{later(r.ai_credits)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}
