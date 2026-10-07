"use client";

import { useState } from "react";
import { Check, Copy, KeyRound } from "lucide-react";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { useApiData } from "@/components/dashboard/useApiData";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/lib/api";
import { createKey, listKeys, revokeKey, type CreatedApiKey } from "@/lib/developer";

export default function KeysPage() {
  const { data: keys, error, loading, reload } = useApiData(listKeys);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [created, setCreated] = useState<CreatedApiKey | null>(null);
  const [copied, setCopied] = useState(false);
  const [confirming, setConfirming] = useState<number | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setActionError("");
    try {
      const key = await createKey(name.trim() || "Default");
      setCreated(key);
      setCopied(false);
      setName("");
      await reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Couldn't create the key.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRevoke(id: number) {
    setActionError("");
    try {
      await revokeKey(id);
      setConfirming(null);
      if (created?.id === id) setCreated(null);
      await reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Couldn't revoke the key.");
    }
  }

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  const active = keys?.filter((k) => !k.revoked_at) ?? [];
  const revoked = keys?.filter((k) => k.revoked_at) ?? [];

  return (
    <>
      <PageHeader
        title="API keys"
        description="Keys authenticate calls to the Truebex API. Treat them like passwords."
      />

      {created && (
        <Panel className="mb-6 border-accent/40">
          <p className="font-semibold">Your new key “{created.name}”</p>
          <p className="mt-1 text-sm text-warn">
            Copy it now — for your security it won&apos;t be shown again.
          </p>
          <div className="mt-4 flex flex-col gap-2 sm:flex-row">
            <code className="min-w-0 flex-1 break-all rounded-[var(--radius-button)] border border-border bg-background px-3 py-2.5 font-mono text-sm text-text-primary">
              {created.key}
            </code>
            <Button size="md" variant="secondary" onClick={() => copy(created.key)}>
              {copied ? <Check size={16} aria-hidden /> : <Copy size={16} aria-hidden />}
              <span className="ml-2">{copied ? "Copied" : "Copy"}</span>
            </Button>
          </div>
        </Panel>
      )}

      <Panel className="mb-6">
        <form onSubmit={handleCreate} className="flex flex-col gap-3 sm:flex-row">
          <label className="sr-only" htmlFor="key-name">
            Key name
          </label>
          <input
            id="key-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={100}
            placeholder="Key name, e.g. “Production” or “CI”"
            className="min-w-0 flex-1 rounded-[var(--radius-button)] border border-border bg-background px-4 py-2.5 text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50"
          />
          <Button type="submit" disabled={busy}>
            <KeyRound size={16} aria-hidden />
            <span className="ml-2">{busy ? "Creating…" : "Create key"}</span>
          </Button>
        </form>
        {(actionError || error) && (
          <div className="mt-4">
            <ErrorNote message={actionError || error || ""} />
          </div>
        )}
      </Panel>

      <Panel>
        <h2 className="font-semibold">Active keys</h2>
        {loading && !keys ? (
          <p className="mt-4 text-sm text-text-muted">Loading…</p>
        ) : active.length === 0 ? (
          <p className="mt-4 text-sm text-text-muted">No active keys yet.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-text-muted">
                <tr>
                  <th className="py-2 pr-4 font-medium">Name</th>
                  <th className="py-2 pr-4 font-medium">Key</th>
                  <th className="py-2 pr-4 font-medium">Created</th>
                  <th className="py-2 pr-4 font-medium">Last used</th>
                  <th className="py-2 font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {active.map((k) => (
                  <tr key={k.id} className="border-t border-border">
                    <td className="py-3 pr-4 text-text-primary">{k.name}</td>
                    <td className="py-3 pr-4 font-mono text-text-secondary">{k.prefix}…</td>
                    <td className="py-3 pr-4 text-text-secondary">{formatDate(k.created_at)}</td>
                    <td className="py-3 pr-4 text-text-secondary">{formatDate(k.last_used_at)}</td>
                    <td className="py-3 text-right">
                      {confirming === k.id ? (
                        <span className="inline-flex gap-3">
                          <button
                            className="text-red-400 hover:underline"
                            onClick={() => handleRevoke(k.id)}
                          >
                            Confirm revoke
                          </button>
                          <button
                            className="text-text-muted hover:underline"
                            onClick={() => setConfirming(null)}
                          >
                            Cancel
                          </button>
                        </span>
                      ) : (
                        <button
                          className="text-text-muted hover:text-red-400"
                          onClick={() => setConfirming(k.id)}
                        >
                          Revoke
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {revoked.length > 0 && (
          <details className="mt-6">
            <summary className="cursor-pointer text-sm text-text-muted">
              {revoked.length} revoked {revoked.length === 1 ? "key" : "keys"}
            </summary>
            <ul className="mt-3 space-y-1 text-sm text-text-muted">
              {revoked.map((k) => (
                <li key={k.id}>
                  {k.name} · <span className="font-mono">{k.prefix}…</span> · revoked{" "}
                  {formatDate(k.revoked_at)}
                </li>
              ))}
            </ul>
          </details>
        )}
      </Panel>
    </>
  );
}
