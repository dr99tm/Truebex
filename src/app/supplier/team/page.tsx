"use client";

import { useEffect, useState } from "react";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { Button } from "@/components/ui/Button";
import { Field, inputClass, OkNote, useMember } from "@/components/supplier/SupplierShell";
import { formatDate } from "@/lib/api";
import { SUPPLIER } from "@/lib/constants";
import { fill, supplierApi, type Role, type Team } from "@/lib/supplier";
import { cn } from "@/lib/utils";

const T = SUPPLIER.team;
const ROLES: Role[] = ["owner", "catalogue", "orders", "viewer"];

// Members by invitation with a role, pending invitations, and supplier keys
// for feeds (shown once).
export default function TeamPage() {
  const { me } = useMember();
  const [team, setTeam] = useState<Team | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [invite, setInvite] = useState<{ email: string; role: Role }>({ email: "", role: "catalogue" });
  const [keyName, setKeyName] = useState("");
  const [newKey, setNewKey] = useState("");
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    supplierApi
      .team()
      .then((t) => {
        if (!cancelled) setTeam(t);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function act(fn: () => Promise<Team | unknown>, ok?: string) {
    setBusy(true);
    setError("");
    setNote("");
    try {
      const out = await fn();
      if (out && typeof out === "object" && "members" in (out as object)) setTeam(out as Team);
      else setTeam(await supplierApi.team());
      if (ok) setNote(ok);
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title={T.title} description={T.description} />
      <div className="space-y-6">
        {error && <ErrorNote message={error} />}
        {note && <OkNote message={note} />}

        <Panel>
          <h2 className="font-semibold">{T.members}</h2>
          <ul className="mt-3 divide-y divide-border">
            {team?.members.map((m) => (
              <li key={m.user_id} className="flex flex-wrap items-center gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-text-primary">
                    {m.name ? `${m.name} · ` : ""}
                    {m.email}
                    {m.user_id === me.user.id && <span className="ml-2 text-xs text-text-muted">({T.you})</span>}
                  </p>
                  <p className="text-xs text-text-muted">{SUPPLIER.roleHelp[m.role]}</p>
                </div>
                <select
                  aria-label={`${T.role}: ${m.email}`}
                  value={m.role}
                  disabled={busy}
                  onChange={(e) => void act(() => supplierApi.setRole(m.user_id, e.target.value as Role))}
                  className={cn(inputClass, "w-44")}
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {SUPPLIER.roles[r]}
                    </option>
                  ))}
                </select>
                {m.user_id !== me.user.id && (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busy}
                    onClick={() => {
                      if (window.confirm(fill(T.confirmRemove, { email: m.email }))) void act(() => supplierApi.removeMember(m.user_id));
                    }}
                  >
                    {T.remove}
                  </Button>
                )}
              </li>
            ))}
          </ul>

          <form
            className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-[1fr_12rem_auto] sm:items-end"
            onSubmit={(e) => {
              e.preventDefault();
              void act(async () => {
                await supplierApi.invite(invite.email, invite.role);
                setInvite({ ...invite, email: "" });
              }, fill(T.invited, { email: invite.email }));
            }}
          >
            <Field label={`${T.invite} — ${T.email}`}>
              <input type="email" required value={invite.email} onChange={(e) => setInvite({ ...invite, email: e.target.value })} className={inputClass} />
            </Field>
            <Field label={T.role}>
              <select value={invite.role} onChange={(e) => setInvite({ ...invite, role: e.target.value as Role })} className={inputClass}>
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {SUPPLIER.roles[r]}
                  </option>
                ))}
              </select>
            </Field>
            <Button type="submit" disabled={busy}>
              {T.send}
            </Button>
          </form>
          <p className="mt-2 text-xs text-text-muted">{SUPPLIER.roleHelp[invite.role]}</p>

          {team && team.invites.length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-semibold">{T.pending}</h3>
              <ul className="mt-2 space-y-2 text-sm">
                {team.invites.map((i) => (
                  <li key={i.invite_id} className="flex flex-wrap items-center gap-3">
                    <span className="text-text-primary">{i.email}</span>
                    <span className="text-text-muted">
                      {SUPPLIER.roles[i.role]} · {i.expired ? T.expired : `${T.expires} ${formatDate(i.expires_at)}`}
                    </span>
                    <button type="button" disabled={busy} onClick={() => void act(() => supplierApi.revokeInvite(i.invite_id))} className="text-xs text-red-300 hover:underline">
                      {T.revoke}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Panel>

        <Panel>
          <h2 className="font-semibold">{T.keys}</h2>
          <p className="mt-1 text-sm text-text-muted">{T.keysHelp}</p>
          {newKey && (
            <div className="mt-4 rounded-[var(--radius-button)] border border-accent/40 bg-accent/5 p-3">
              <p className="text-sm text-text-secondary">{T.newKey}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <code className="break-all font-mono text-xs text-accent">{newKey}</code>
                <button
                  type="button"
                  onClick={() => {
                    void navigator.clipboard?.writeText(newKey).then(() => setCopied(true));
                  }}
                  className="text-xs text-accent hover:underline"
                >
                  {copied ? T.copied : T.copy}
                </button>
              </div>
            </div>
          )}
          <form
            className="mt-4 flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              void act(async () => {
                const k = await supplierApi.createKey(keyName);
                setNewKey(k.key);
                setCopied(false);
                setKeyName("");
              });
            }}
          >
            <Field label={T.keyName} className="min-w-0 flex-1">
              <input required maxLength={100} value={keyName} onChange={(e) => setKeyName(e.target.value)} className={inputClass} />
            </Field>
            <Button type="submit" disabled={busy}>
              {T.createKey}
            </Button>
          </form>
          {team && team.keys.length === 0 && <p className="mt-3 text-sm text-text-muted">{T.noKeys}</p>}
          <ul className="mt-3 divide-y divide-border text-sm">
            {team?.keys.map((k) => (
              <li key={k.id} className="flex flex-wrap items-center gap-3 py-2">
                <span className="font-mono text-xs text-text-primary">{k.prefix}…</span>
                <span className="text-text-secondary">{k.name}</span>
                <span className="text-xs text-text-muted">
                  {k.created_by} · {formatDate(k.created_at)} ·{" "}
                  {k.revoked_at ? T.revoked : k.last_used_at ? `${T.lastUsed} ${formatDate(k.last_used_at)}` : T.never}
                </span>
                {!k.revoked_at && (
                  <button type="button" disabled={busy} onClick={() => void act(() => supplierApi.revokeKey(k.id))} className="ml-auto text-xs text-red-300 hover:underline">
                    {T.revoke}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </>
  );
}
