"use client";

import { useEffect, useState } from "react";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { OrgGate } from "@/components/dashboard/OrgContext";
import { errorText, inputClass, tableClass, tdClass, thClass } from "@/components/dashboard/orgUi";
import { MEMBER_USAGE } from "@/lib/constants";
import { formatCount, formatStorage } from "@/lib/memberUsage";
import { getUsage, monthOf, ROLE_NAMES, type MemberUsage, type OrgSummary } from "@/lib/orgs";
import { timeAgo } from "@/lib/time";

export default function UsagePage() {
  return <OrgGate level="admin">{(org) => <UsageView key={org.id} org={org} />}</OrgGate>;
}

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
        title={MEMBER_USAGE.title}
        description={MEMBER_USAGE.description}
        actions={
          <label className="flex items-center gap-2 text-sm text-text-secondary">
            {MEMBER_USAGE.month}
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
          <p className="text-sm text-text-muted">{MEMBER_USAGE.loading}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className={tableClass}>
              <thead className="text-left text-text-muted">
                <tr>
                  <th className={thClass}>{MEMBER_USAGE.columns.member}</th>
                  <th className={thClass}>{MEMBER_USAGE.columns.devices}</th>
                  <th className={thClass}>{MEMBER_USAGE.columns.lastActive}</th>
                  <th className={thClass}>{MEMBER_USAGE.columns.apiRequests}</th>
                  <th className={thClass}>{MEMBER_USAGE.columns.floatingHours}</th>
                  <th className={thClass}>{MEMBER_USAGE.columns.storage}</th>
                  <th className={thClass}>{MEMBER_USAGE.columns.panoramas}</th>
                  <th className={thClass}>{MEMBER_USAGE.columns.aiCredits}</th>
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
                    <td className={tdClass}>{formatCount(r.api_requests)}</td>
                    <td className={tdClass}>{r.floating_hours.toFixed(1)} h</td>
                    <td className={tdClass} title={r.storage_bytes === null ? MEMBER_USAGE.storageCurrentOnly : undefined}>
                      {formatStorage(r.storage_bytes)}
                    </td>
                    <td className={tdClass}>{formatCount(r.panoramas)}</td>
                    <td className={tdClass}>{formatCount(r.ai_credits)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <ul className="mt-4 space-y-1 text-xs text-text-muted">
              {MEMBER_USAGE.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        )}
      </Panel>
    </>
  );
}
