"use client";

import { useState } from "react";
import { ErrorNote, PageHeader, Panel, useDashboardUser } from "@/components/dashboard/DashboardShell";
import { OrgGate, useOrgs } from "@/components/dashboard/OrgContext";
import { dangerButton, errorText, inputClass, tableClass, tdClass, thClass } from "@/components/dashboard/orgUi";
import { useApiData } from "@/components/dashboard/useApiData";
import {
  assignSeat,
  changeRole,
  isAdmin,
  listMembers,
  removeMember,
  ROLE_NAMES,
  SEAT_NAMES,
  type OrgSummary,
  type Role,
  type SeatKind,
} from "@/lib/orgs";
import { timeAgo } from "@/lib/time";

export default function MembersPage() {
  return <OrgGate>{(org) => <Members key={org.id} org={org} />}</OrgGate>;
}

function Members({ org }: { org: OrgSummary }) {
  const me = useDashboardUser();
  const { reload: reloadOrgs } = useOrgs();
  const members = useApiData(() => listMembers(org.id));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  const admin = isAdmin(org.role);
  const roles: Role[] = org.role === "owner" ? ["owner", "admin", "billing", "member"] : ["admin", "billing", "member"];

  async function act(userId: number, fn: () => Promise<unknown>) {
    setBusy(userId);
    setError("");
    try {
      await fn();
      await members.reload();
      if (userId === me.id) await reloadOrgs();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  const rows = members.data ?? [];
  return (
    <>
      <PageHeader
        title="Members"
        description={`Everyone in ${org.name}, their role and seat. Named seats belong to one person; floating seats are shared, one per running copy of Truebex.`}
      />
      {(error || members.error) && (
        <div className="mb-6">
          <ErrorNote message={error || members.error || ""} />
        </div>
      )}
      <Panel>
        {members.loading && !members.data ? (
          <p className="text-sm text-text-muted">Loading…</p>
        ) : (
          <div className="overflow-x-auto">
            <table className={tableClass}>
              <thead className="text-left text-text-muted">
                <tr>
                  <th className={thClass}>Member</th>
                  <th className={thClass}>Role</th>
                  <th className={thClass}>Seat</th>
                  <th className={thClass}>Last active</th>
                  <th className={thClass}>Devices</th>
                  <th className="py-2 font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((m) => {
                  const self = m.user_id === me.id;
                  const canEditRole = admin && (org.role === "owner" || m.role !== "owner");
                  return (
                    <tr key={m.user_id} className="border-t border-border" data-member={m.email}>
                      <td className="py-3 pr-4">
                        <span className="text-text-primary">{m.name || m.email}</span>
                        {m.name && <span className="block text-xs text-text-muted">{m.email}</span>}
                        {self && <span className="block text-xs text-text-muted">you</span>}
                      </td>
                      <td className={tdClass}>
                        {canEditRole ? (
                          <select
                            aria-label={`Role of ${m.email}`}
                            value={m.role}
                            disabled={busy === m.user_id}
                            onChange={(e) => act(m.user_id, () => changeRole(org.id, m.user_id, e.target.value as Role))}
                            className={inputClass}
                          >
                            {(roles.includes(m.role) ? roles : [m.role, ...roles]).map((r) => (
                              <option key={r} value={r}>
                                {ROLE_NAMES[r]}
                              </option>
                            ))}
                          </select>
                        ) : (
                          ROLE_NAMES[m.role]
                        )}
                      </td>
                      <td className={tdClass}>
                        {admin ? (
                          <select
                            aria-label={`Seat of ${m.email}`}
                            value={m.seat_kind}
                            disabled={busy === m.user_id}
                            onChange={(e) =>
                              act(m.user_id, () => assignSeat(org.id, m.user_id, e.target.value as SeatKind))
                            }
                            className={inputClass}
                          >
                            {(["named", "floating", "none"] as SeatKind[]).map((k) => (
                              <option key={k} value={k}>
                                {SEAT_NAMES[k]}
                              </option>
                            ))}
                          </select>
                        ) : (
                          SEAT_NAMES[m.seat_kind]
                        )}
                      </td>
                      <td className={tdClass}>{timeAgo(m.last_active_at)}</td>
                      <td className={tdClass}>{m.devices}</td>
                      <td className="py-3 text-right">
                        {(self || (admin && (org.role === "owner" || m.role !== "owner"))) && (
                          <button
                            className={dangerButton}
                            disabled={busy === m.user_id}
                            onClick={() => {
                              const q = self ? `Leave ${org.name}?` : `Remove ${m.email} from ${org.name}?`;
                              if (window.confirm(q)) void act(m.user_id, () => removeMember(org.id, m.user_id));
                            }}
                          >
                            {self ? "Leave" : "Remove"}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}
