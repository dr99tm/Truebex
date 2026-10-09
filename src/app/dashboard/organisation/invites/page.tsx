"use client";

import { useState } from "react";
import { UserPlus } from "lucide-react";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { OrgGate } from "@/components/dashboard/OrgContext";
import { dangerButton, errorText, inputClass, linkButton, tableClass, tdClass, thClass } from "@/components/dashboard/orgUi";
import { useApiData } from "@/components/dashboard/useApiData";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/lib/api";
import {
  createInvite,
  listInvites,
  resendInvite,
  revokeInvite,
  ROLE_NAMES,
  SEAT_NAMES,
  type OrgSummary,
  type Role,
  type SeatKind,
} from "@/lib/orgs";

export default function InvitesPage() {
  return <OrgGate level="admin">{(org) => <Invites key={org.id} org={org} />}</OrgGate>;
}

function Invites({ org }: { org: OrgSummary }) {
  const invites = useApiData(() => listInvites(org.id));
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("member");
  const [seat, setSeat] = useState<SeatKind>("none");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const roles: Role[] = org.role === "owner" ? ["member", "billing", "admin", "owner"] : ["member", "billing", "admin"];

  async function act(fn: () => Promise<unknown>, done: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      setNotice(done);
      await invites.reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const to = email.trim();
    void act(async () => {
      await createInvite(org.id, to, role, seat);
      setEmail("");
    }, `Invitation sent to ${to}.`);
  }

  const all = invites.data ?? [];
  const pending = all.filter((i) => i.status === "pending");
  const past = all.filter((i) => i.status !== "pending");

  return (
    <>
      <PageHeader
        title="Invites"
        description="Invite people by e-mail. The link works for 7 days and only for an account with the invited address."
      />
      <Panel className="mb-6">
        <form onSubmit={submit} className="grid gap-3 md:grid-cols-[1fr_auto_auto_auto]">
          <label className="sr-only" htmlFor="invite-email">
            E-mail address
          </label>
          <input
            id="invite-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="name@practice.com"
            className={inputClass}
          />
          <label className="sr-only" htmlFor="invite-role">
            Role
          </label>
          <select id="invite-role" value={role} onChange={(e) => setRole(e.target.value as Role)} className={inputClass}>
            {roles.map((r) => (
              <option key={r} value={r}>
                {ROLE_NAMES[r]}
              </option>
            ))}
          </select>
          <label className="sr-only" htmlFor="invite-seat">
            Seat
          </label>
          <select id="invite-seat" value={seat} onChange={(e) => setSeat(e.target.value as SeatKind)} className={inputClass}>
            <option value="none">No seat</option>
            <option value="named">Named seat</option>
            <option value="floating">Floating seat</option>
          </select>
          <Button type="submit" disabled={busy || !email.trim()}>
            <UserPlus size={16} aria-hidden />
            <span className="ml-2">{busy ? "Sending…" : "Invite"}</span>
          </Button>
        </form>
        {notice && (
          <p role="status" className="mt-4 text-sm text-emerald-400">
            {notice}
          </p>
        )}
        {(error || invites.error) && (
          <div className="mt-4">
            <ErrorNote message={error || invites.error || ""} />
          </div>
        )}
      </Panel>

      <Panel>
        <h2 className="font-semibold">Pending</h2>
        {invites.loading && !invites.data ? (
          <p className="mt-4 text-sm text-text-muted">Loading…</p>
        ) : pending.length === 0 ? (
          <p className="mt-4 text-sm text-text-muted">No pending invitations.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className={tableClass}>
              <thead className="text-left text-text-muted">
                <tr>
                  <th className={thClass}>E-mail</th>
                  <th className={thClass}>Role</th>
                  <th className={thClass}>Seat</th>
                  <th className={thClass}>Expires</th>
                  <th className="py-2 font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {pending.map((i) => (
                  <tr key={i.id} className="border-t border-border">
                    <td className="py-3 pr-4 text-text-primary">{i.email}</td>
                    <td className={tdClass}>{ROLE_NAMES[i.role]}</td>
                    <td className={tdClass}>{SEAT_NAMES[i.seat_kind]}</td>
                    <td className={tdClass}>{formatDate(i.expires_at)}</td>
                    <td className="py-3 text-right">
                      <span className="inline-flex gap-4">
                        <button className={linkButton} disabled={busy} onClick={() => act(() => resendInvite(org.id, i.id), `Sent a new link to ${i.email}.`)}>
                          Resend
                        </button>
                        <button className={dangerButton} disabled={busy} onClick={() => act(() => revokeInvite(org.id, i.id), `Invitation to ${i.email} withdrawn.`)}>
                          Revoke
                        </button>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {past.length > 0 && (
          <details className="mt-6">
            <summary className="cursor-pointer text-sm text-text-muted">
              {past.length} earlier {past.length === 1 ? "invitation" : "invitations"}
            </summary>
            <ul className="mt-3 space-y-1 text-sm text-text-muted">
              {past.map((i) => (
                <li key={i.id}>
                  {i.email} · {ROLE_NAMES[i.role]} · {i.status} · {formatDate(i.created_at)}
                </li>
              ))}
            </ul>
          </details>
        )}
      </Panel>
    </>
  );
}
