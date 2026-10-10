"use client";

import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { OrgGate } from "@/components/dashboard/OrgContext";
import { errorText, inputClass, linkButton, tableClass, tdClass, thClass } from "@/components/dashboard/orgUi";
import { Button } from "@/components/ui/Button";
import { parseServerDate } from "@/lib/api";
import { downloadAuditCsv, getAudit, type AuditEvent, type OrgSummary } from "@/lib/orgs";

export default function AuditPage() {
  return <OrgGate level="admin">{(org) => <AuditView key={org.id} org={org} />}</OrgGate>;
}

const FILTERS: [string, string][] = [
  ["", "Everything"],
  ["member", "Members and roles"],
  ["invite", "Invitations"],
  ["seat", "Seat assignments"],
  ["lease", "Floating seats"],
  ["device", "Devices"],
  ["sso", "Single sign-on"],
  ["domain", "Domains"],
  ["org", "Organisation"],
];

const LABELS: Record<string, string> = {
  "org.created": "Created the organisation",
  "org.renamed": "Renamed the organisation",
  "org.deleted": "Deleted the organisation",
  "member.joined": "Joined",
  "member.left": "Left",
  "member.removed": "Removed a member",
  "member.role_changed": "Changed a role",
  "invite.created": "Invited",
  "invite.resent": "Resent an invitation",
  "invite.revoked": "Withdrew an invitation",
  "invite.accepted": "Accepted an invitation",
  "invite.expired": "Invitation expired",
  "seat.assigned": "Gave a seat",
  "seat.unassigned": "Took a seat back",
  "seats.floating_changed": "Changed floating seats",
  "lease.taken": "Took a floating seat",
  "lease.released": "Handed a floating seat back",
  "lease.lapsed": "Floating seat lapsed",
  "lease.refused": "No floating seat free",
  "device.activated": "Activated a device",
  "device.replaced": "Replaced a device",
  "device.revoked": "Device signed out",
  "trial.started": "Started a trial",
  "seat.device_limit": "Hit the device limit",
  "link.approved": "Approved a sign-in",
  "link.denied": "Denied a sign-in",
  "sso.configured": "Changed the SSO connection",
  "sso.policy_changed": "Changed the SSO policy",
  "sso.removed": "Removed the SSO connection",
  "sso.signin": "Signed in with SSO",
  "sso.break_glass_created": "Made a break-glass code",
  "sso.break_glass_used": "Used the break-glass code",
  "sso.break_glass_refused": "Break-glass code refused",
  "domain.added": "Added a domain",
  "domain.verified": "Verified a domain",
  "domain.removed": "Removed a domain",
  "subscription.granted": "Seats arranged",
  "subscription.revoked": "Arranged seats ended",
  "audit.exported": "Exported the audit log",
};

function when(iso: string): string {
  return parseServerDate(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function details(e: AuditEvent): string {
  return Object.entries(e.details ?? {})
    .filter(([, v]) => v !== null && v !== "" && v !== undefined)
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join(" · ");
}

function AuditView({ org }: { org: OrgSummary }) {
  const [kind, setKind] = useState("");
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getAudit(org.id, { kind })
      .then((page) => {
        if (cancelled) return;
        setEvents(page.events);
        setNext(page.next);
        setError("");
      })
      .catch((err) => {
        if (!cancelled) setError(errorText(err));
      });
    return () => {
      cancelled = true;
    };
  }, [org.id, kind]);

  async function more() {
    setBusy(true);
    try {
      const page = await getAudit(org.id, { kind, cursor: next });
      setEvents((prev) => [...(prev ?? []), ...page.events]);
      setNext(page.next);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function exportCsv() {
    setBusy(true);
    setError("");
    try {
      await downloadAuditCsv(org.id, kind || undefined);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Audit log"
        description="Every licence and organisation event: activations, seats, floating leases, invitations, roles and sign-ins through SSO. Kept for 24 months."
        actions={
          <Button variant="secondary" size="sm" onClick={exportCsv} disabled={busy}>
            <Download size={16} aria-hidden />
            <span className="ml-2">Export CSV</span>
          </Button>
        }
      />
      <div className="mb-4 flex items-center gap-2 text-sm text-text-secondary">
        <label htmlFor="audit-kind">Show</label>
        <select id="audit-kind" value={kind} onChange={(e) => setKind(e.target.value)} className={inputClass}>
          {FILTERS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      {error && (
        <div className="mb-6">
          <ErrorNote message={error} />
        </div>
      )}
      <Panel>
        {!events ? (
          <p className="text-sm text-text-muted">Loading…</p>
        ) : events.length === 0 ? (
          <p className="text-sm text-text-muted">Nothing recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className={tableClass}>
              <thead className="text-left text-text-muted">
                <tr>
                  <th className={thClass}>When</th>
                  <th className={thClass}>Who</th>
                  <th className={thClass}>What</th>
                  <th className={thClass}>Details</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id} className="border-t border-border align-top" data-kind={e.kind}>
                    <td className={`${tdClass} whitespace-nowrap`}>{when(e.at)}</td>
                    <td className={tdClass}>{e.actor?.email ?? "Truebex"}</td>
                    <td className="py-3 pr-4 text-text-primary">
                      {LABELS[e.kind] ?? e.kind}
                      <span className="block font-mono text-xs text-text-muted">{e.kind}</span>
                    </td>
                    <td className={`${tdClass} break-all`}>
                      {e.target ? `${e.target.kind} ${e.target.id}` : ""}
                      {details(e) && <span className="block text-xs text-text-muted">{details(e)}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {next && (
          <button className={`mt-4 text-sm ${linkButton}`} onClick={more} disabled={busy}>
            {busy ? "Loading…" : "Load more"}
          </button>
        )}
      </Panel>
    </>
  );
}
