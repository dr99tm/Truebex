"use client";

import { useState } from "react";
import Link from "next/link";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { OrgGate } from "@/components/dashboard/OrgContext";
import { errorText, inputClass, tableClass, tdClass, thClass } from "@/components/dashboard/orgUi";
import { useApiData } from "@/components/dashboard/useApiData";
import { Button } from "@/components/ui/Button";
import { parseServerDate } from "@/lib/api";
import { getSeats, setFloating, type OrgSummary } from "@/lib/orgs";

export default function SeatsPage() {
  return <OrgGate level="admin">{(org) => <SeatsView key={org.id} org={org} />}</OrgGate>;
}

function clock(iso: string): string {
  return parseServerDate(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function SeatsView({ org }: { org: OrgSummary }) {
  const seats = useApiData(() => getSeats(org.id));
  const [floating, setFloatingInput] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const s = seats.data;
  const value = floating ?? (s ? String(s.floating.total) : "0");

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      seats.setData(await setFloating(org.id, Number(value)));
      setFloatingInput(null);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Seats"
        description="Named seats belong to one person. Floating seats are a shared pool: Truebex takes one while it runs and hands it back when it closes, or two hours after its last check-in."
      />
      {(error || seats.error) && (
        <div className="mb-6">
          <ErrorNote message={error || seats.error || ""} />
        </div>
      )}
      {s && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Panel>
            <h2 className="font-semibold">{s.tier_name ? `${s.tier_name} · ${s.total} seats` : "No seats yet"}</h2>
            <p className="mt-4 text-2xl font-semibold" data-seats-summary>
              Named {s.named.assigned} / {s.named.total} · Floating {s.floating.in_use} / {s.floating.total}
            </p>
            <p className="mt-1 text-sm text-text-secondary">
              {s.floating.members} {s.floating.members === 1 ? "member shares" : "members share"} the floating pool.
              Give seats on the{" "}
              <Link href="/dashboard/organisation/members/" className="text-accent hover:underline">
                Members
              </Link>{" "}
              page.
            </p>
          </Panel>
          <Panel>
            <h2 className="font-semibold">How many seats float</h2>
            <form onSubmit={save} className="mt-4 flex items-center gap-3">
              <label htmlFor="floating" className="sr-only">
                Floating seats
              </label>
              <input
                id="floating"
                type="number"
                min={0}
                max={s.total}
                value={value}
                onChange={(e) => setFloatingInput(e.target.value)}
                className={`w-24 ${inputClass}`}
              />
              <span className="text-sm text-text-secondary">of {s.total}</span>
              <Button type="submit" size="sm" disabled={busy || value === String(s.floating.total)}>
                {busy ? "Saving…" : "Save"}
              </Button>
            </form>
          </Panel>
        </div>
      )}
      {seats.loading && !s && <p className="text-sm text-text-muted">Loading…</p>}

      {s && (
        <Panel className="mt-6">
          <h2 className="font-semibold">Floating seats in use now</h2>
          {s.floating.leases.length === 0 ? (
            <p className="mt-4 text-sm text-text-muted">None in use.</p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className={tableClass}>
                <thead className="text-left text-text-muted">
                  <tr>
                    <th className={thClass}>Member</th>
                    <th className={thClass}>Computer</th>
                    <th className={thClass}>Since</th>
                    <th className={thClass}>Lapses at</th>
                  </tr>
                </thead>
                <tbody>
                  {s.floating.leases.map((l) => (
                    <tr key={`${l.device.device_id}`} className="border-t border-border">
                      <td className="py-3 pr-4 text-text-primary">{l.user.name || l.user.email}</td>
                      <td className={tdClass}>{l.device.name ?? "—"}</td>
                      <td className={tdClass}>{clock(l.since)}</td>
                      <td className={tdClass}>{clock(l.expires_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <Button type="button" size="sm" variant="ghost" className="mt-4 px-0" onClick={() => void seats.reload()}>
            Refresh
          </Button>
        </Panel>
      )}
    </>
  );
}
