"use client";

import { useCallback, useEffect, useState } from "react";
import { ErrorNote, Panel } from "@/components/dashboard/DashboardShell";
import { Button } from "@/components/ui/Button";
import {
  addInferenceServer,
  adminAiError,
  formatCredits,
  formatUsd,
  getAiAdmin,
  removeInferenceServer,
  type AiAdminOverview,
  type InferenceServer,
  type InferenceState,
} from "@/lib/ai";
import { fill } from "@/lib/catalogue";
import { ADMIN_AI } from "@/lib/constants";
import { timeAgo } from "@/lib/time";
import { cn } from "@/lib/utils";

const REFRESH_MS = 15_000;
const inputClass =
  "min-w-0 rounded-[var(--radius-button)] border border-border bg-background px-3 py-2 text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50";

function stateClass(state: InferenceState): string {
  if (state === "warm") return "text-accent";
  if (state === "stopped") return "text-text-muted";
  return "text-text-secondary";
}

function RegisterForm({ aliases, onAdded }: { aliases: string[]; onAdded: () => void }) {
  const [serverId, setServerId] = useState("");
  const [alias, setAlias] = useState(aliases[0] ?? "");
  const [baseUrl, setBaseUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  const chosen = aliases.includes(alias) ? alias : (aliases[0] ?? "");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setDone("");
    try {
      const row = await addInferenceServer(serverId.trim().toLowerCase(), chosen, baseUrl.trim());
      setDone(fill(ADMIN_AI.add.added, { id: row.server_id }));
      setServerId("");
      setBaseUrl("");
      onAdded();
    } catch (err) {
      setError(adminAiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-6 border-t border-border pt-5">
      <h4 className="text-sm font-semibold">{ADMIN_AI.add.title}</h4>
      {aliases.length === 0 ? (
        <p className="mt-3 text-sm text-text-muted">{ADMIN_AI.add.noAlias}</p>
      ) : (
        <form onSubmit={submit} className="mt-4 flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1 text-xs text-text-muted">
            {ADMIN_AI.add.id}
            <input
              value={serverId}
              onChange={(e) => setServerId(e.target.value)}
              placeholder={ADMIN_AI.add.idPlaceholder}
              required
              maxLength={40}
              pattern="[a-z0-9][a-z0-9\-]{0,39}"
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-text-muted">
            {ADMIN_AI.add.alias}
            <select value={chosen} onChange={(e) => setAlias(e.target.value)} className={inputClass}>
              {aliases.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>
          <label className="flex min-w-0 flex-1 basis-56 flex-col gap-1 text-xs text-text-muted">
            {ADMIN_AI.add.url}
            <input
              type="url"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder={ADMIN_AI.add.urlPlaceholder}
              required
              maxLength={300}
              pattern="https?://.+"
              className={inputClass}
            />
          </label>
          <Button type="submit" size="sm" disabled={busy || !serverId.trim() || !baseUrl.trim()}>
            {busy ? ADMIN_AI.add.busy : ADMIN_AI.add.submit}
          </Button>
        </form>
      )}
      {error && (
        <div className="mt-4">
          <ErrorNote message={error} />
        </div>
      )}
      {done && (
        <p role="status" className="mt-4 text-sm text-text-secondary">
          {done}
        </p>
      )}
    </div>
  );
}

/** The render admin's AI panel (PF11): this month's AI spend by alias against
 *  what the providers charged, and the self-hosted inference servers. */
export function AiAdmin({ className }: { className?: string }) {
  const [data, setData] = useState<AiAdminOverview | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(
    () =>
      getAiAdmin()
        .then((overview) => {
          setData(overview);
          setError("");
        })
        .catch((err: unknown) => setError(adminAiError(err))),
    []
  );

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(t);
  }, [load]);

  const remove = async (s: InferenceServer) => {
    if (!window.confirm(fill(ADMIN_AI.servers.confirm, { id: s.server_id }))) return;
    try {
      await removeInferenceServer(s.server_id);
      void load();
    } catch (err) {
      setError(adminAiError(err));
    }
  };

  const spend = [...(data?.spend ?? [])].sort((a, b) => b.credits - a.credits);
  const selfHosted = (data?.aliases ?? []).filter((a) => a.adapter === "selfhosted").map((a) => a.alias);
  const s = ADMIN_AI.spend;
  const v = ADMIN_AI.servers;

  return (
    <section aria-labelledby="ai-services" className={cn("space-y-6", className)}>
      <h2 id="ai-services" className="text-xl font-semibold tracking-tight">
        {ADMIN_AI.title}
      </h2>
      {error && <ErrorNote message={error} />}
      {data && (
        <>
          <Panel>
            <h3 className="font-semibold">{s.title}</h3>
            {spend.length === 0 ? (
              <p className="mt-4 text-sm text-text-muted">{s.empty}</p>
            ) : (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full min-w-[36rem] text-sm">
                  <thead className="text-left text-xs text-text-muted">
                    <tr>
                      <th className="pb-2 pr-4 font-medium">{s.alias}</th>
                      <th className="pb-2 pr-4 font-medium">{s.servedBy}</th>
                      <th className="pb-2 pr-4 text-right font-medium">{s.turns}</th>
                      <th className="pb-2 pr-4 text-right font-medium">{s.credits}</th>
                      <th className="pb-2 text-right font-medium">{s.cost}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {spend.map((r) => (
                      <tr key={`${r.alias}-${r.served_by}`} className="border-t border-border">
                        <td className="py-2 pr-4 font-mono text-text-primary">{r.alias}</td>
                        <td className="py-2 pr-4 text-text-secondary">{r.served_by}</td>
                        <td className="py-2 pr-4 text-right tabular-nums text-text-primary">{formatCredits(r.turns)}</td>
                        <td className="py-2 pr-4 text-right tabular-nums text-text-primary">{formatCredits(r.credits)}</td>
                        <td className="py-2 text-right tabular-nums text-text-primary">{formatUsd(r.provider_cost_usd)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
          <Panel>
            <h3 className="font-semibold">{v.title}</h3>
            <p className="mt-2 text-sm text-text-secondary">
              {v.wanted}:{" "}
              <span className="tabular-nums text-text-primary">{data.gpu_ai_wanted ?? v.unset}</span>
            </p>
            {data.servers.length === 0 ? (
              <p className="mt-4 text-sm text-text-muted">{v.empty}</p>
            ) : (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full min-w-[36rem] text-sm">
                  <thead className="text-left text-xs text-text-muted">
                    <tr>
                      <th className="pb-2 pr-4 font-medium">{v.id}</th>
                      <th className="pb-2 pr-4 font-medium">{v.alias}</th>
                      <th className="pb-2 pr-4 font-medium">{v.state}</th>
                      <th className="pb-2 pr-4 font-medium">{v.probe}</th>
                      <th className="pb-2">
                        <span className="sr-only">{v.actions}</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.servers.map((row) => (
                      <tr key={row.server_id} className="border-t border-border align-top">
                        <td className="py-2 pr-4">
                          <p className="font-mono text-text-primary">{row.server_id}</p>
                          <p className="break-all font-mono text-xs text-text-muted">{row.base_url}</p>
                        </td>
                        <td className="py-2 pr-4 font-mono text-text-secondary">{row.alias}</td>
                        <td className={cn("py-2 pr-4", stateClass(row.state))}>{v.states[row.state] ?? row.state}</td>
                        <td className="py-2 pr-4 text-text-secondary">{timeAgo(row.last_probe_at)}</td>
                        <td className="py-2 text-right">
                          <button
                            type="button"
                            onClick={() => void remove(row)}
                            aria-label={`${v.remove} ${row.server_id}`}
                            className="text-xs text-red-300 hover:underline"
                          >
                            {v.remove}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <RegisterForm aliases={selfHosted} onAdded={() => void load()} />
          </Panel>
        </>
      )}
    </section>
  );
}
