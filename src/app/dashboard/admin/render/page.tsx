"use client";

import { useCallback, useEffect, useState } from "react";
import { AiAdmin } from "@/components/cloud/AiAdmin";
import { ErrorNote, PageHeader, Panel, useDashboardUser } from "@/components/dashboard/DashboardShell";
import { Button } from "@/components/ui/Button";
import { kindLabel } from "@/lib/ai";
import { fill } from "@/lib/catalogue";
import { ADMIN_RENDER, CLOUD } from "@/lib/constants";
import {
  formatCu,
  getRenderOverview,
  issueWorker,
  revokeWorker,
  type JobKind,
  type RenderOverview,
  type WorkerRow,
} from "@/lib/jobs";
import { timeAgo } from "@/lib/time";

const KINDS: JobKind[] = ["panorama", "tiles", "pack", "wind", "energy", "acoustics", "texture"];
const CLASSES = ["gpu-std", "cpu-8", "gpu-ai"];
const REFRESH_MS = 15_000;
const inputClass =
  "min-w-0 rounded-[var(--radius-button)] border border-border bg-background px-3 py-2 text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50";

function wait(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 60) return `${seconds} s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min`;
  return `${Math.floor(seconds / 3600)} h ${Math.floor((seconds % 3600) / 60)} min`;
}

function IssueForm({ onIssued }: { onIssued: () => void }) {
  const [name, setName] = useState("");
  const [kinds, setKinds] = useState<JobKind[]>(["panorama", "tiles"]);
  const [cls, setCls] = useState(CLASSES[0]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [issued, setIssued] = useState<{ name: string; token: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setCopied(false);
    try {
      const row = await issueWorker(name.trim(), kinds, cls);
      setIssued({ name: row.worker_id, token: row.token });
      setName("");
      onIssued();
    } catch (err) {
      setError(err instanceof Error ? err.message : CLOUD.errors.generic);
    } finally {
      setBusy(false);
    }
  };

  const toggle = (kind: JobKind) =>
    setKinds((old) => (old.includes(kind) ? old.filter((k) => k !== kind) : [...old, kind]));

  return (
    <Panel className="mb-6">
      <h2 className="font-semibold">{ADMIN_RENDER.issue.title}</h2>
      <form onSubmit={submit} className="mt-4 flex flex-col gap-4">
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1 text-xs text-text-muted">
            {ADMIN_RENDER.issue.name}
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={ADMIN_RENDER.issue.namePlaceholder}
              required
              maxLength={40}
              pattern="[a-z0-9][a-z0-9\-]{0,39}"
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-text-muted">
            {ADMIN_RENDER.issue.cls}
            <select value={cls} onChange={(e) => setCls(e.target.value)} className={inputClass}>
              {CLASSES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
        </div>
        <fieldset className="flex flex-wrap gap-4 text-sm">
          <legend className="mb-2 text-xs text-text-muted">{ADMIN_RENDER.issue.kinds}</legend>
          {KINDS.map((kind) => (
            <label key={kind} className="flex items-center gap-2 text-text-secondary">
              <input type="checkbox" checked={kinds.includes(kind)} onChange={() => toggle(kind)} />
              {kind}
            </label>
          ))}
        </fieldset>
        <div>
          <Button type="submit" size="sm" disabled={busy || kinds.length === 0 || !name.trim()}>
            {busy ? ADMIN_RENDER.issue.busy : ADMIN_RENDER.issue.submit}
          </Button>
        </div>
      </form>
      {error && (
        <div className="mt-4">
          <ErrorNote message={error} />
        </div>
      )}
      {issued && (
        <div className="mt-4 rounded-[var(--radius-button)] border border-accent/30 bg-accent/5 p-4" role="status">
          <p className="text-sm text-text-secondary">{fill(ADMIN_RENDER.issue.shown, { name: issued.name })}</p>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <code className="break-all font-mono text-sm text-text-primary">{issued.token}</code>
            <button
              type="button"
              className="text-xs text-accent hover:underline"
              onClick={() => {
                void navigator.clipboard?.writeText(issued.token).then(() => setCopied(true));
              }}
            >
              {copied ? ADMIN_RENDER.issue.copied : ADMIN_RENDER.issue.copy}
            </button>
          </div>
        </div>
      )}
    </Panel>
  );
}

function Workers({ rows, onRevoke }: { rows: WorkerRow[]; onRevoke: (w: WorkerRow) => void }) {
  return (
    <Panel className="mb-6">
      <h2 className="font-semibold">{ADMIN_RENDER.workers.title}</h2>
      {rows.length === 0 ? (
        <p className="mt-4 text-sm text-text-muted">{ADMIN_RENDER.workers.empty}</p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[40rem] text-sm">
            <thead className="text-left text-xs text-text-muted">
              <tr>
                <th className="pb-2 pr-4 font-medium">{ADMIN_RENDER.workers.name}</th>
                <th className="pb-2 pr-4 font-medium">{ADMIN_RENDER.workers.kinds}</th>
                <th className="pb-2 pr-4 font-medium">{ADMIN_RENDER.workers.version}</th>
                <th className="pb-2 pr-4 font-medium">{ADMIN_RENDER.workers.heartbeat}</th>
                <th className="pb-2 pr-4 font-medium">{ADMIN_RENDER.workers.state}</th>
                <th className="pb-2 pr-4 font-medium">{ADMIN_RENDER.workers.job}</th>
                <th className="pb-2" />
              </tr>
            </thead>
            <tbody>
              {rows.map((w) => (
                <tr key={w.worker_id} className="border-t border-border">
                  <td className="py-2 pr-4 font-mono text-text-primary">
                    {w.worker_id}
                    <span className="ml-2 font-sans text-xs text-text-muted">{w.class}</span>
                  </td>
                  <td className="py-2 pr-4 text-text-secondary">{w.kinds.join(", ")}</td>
                  <td className="py-2 pr-4 text-text-secondary">
                    {w.app_version ?? "—"}
                    {w.doc_version_max !== null && <span className="text-text-muted"> · o5/{w.doc_version_max}</span>}
                  </td>
                  <td className="py-2 pr-4 text-text-secondary">{timeAgo(w.last_heartbeat_at)}</td>
                  <td className="py-2 pr-4 text-text-secondary">
                    {w.revoked_at ? ADMIN_RENDER.workers.revoked : `${w.pool} · ${w.pool_state}`}
                  </td>
                  <td className="py-2 pr-4 font-mono text-xs text-text-muted">{w.job_id ? w.job_id.slice(0, 8) : "—"}</td>
                  <td className="py-2 text-right">
                    {!w.revoked_at && (
                      <button type="button" onClick={() => onRevoke(w)} className="text-xs text-red-300 hover:underline">
                        {ADMIN_RENDER.workers.revoke}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

export default function RenderAdminPage() {
  const user = useDashboardUser();
  const [data, setData] = useState<RenderOverview | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(
    () =>
      getRenderOverview()
        .then((overview) => {
          setData(overview);
          setError("");
        })
        .catch((err: unknown) => setError(err instanceof Error ? err.message : CLOUD.errors.generic)),
    []
  );

  useEffect(() => {
    if (!user.is_admin) return;
    void load();
    const t = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(t);
  }, [user.is_admin, load]);

  if (!user.is_admin) {
    return (
      <>
        <PageHeader title={ADMIN_RENDER.title} />
        <ErrorNote message={ADMIN_RENDER.adminsOnly} />
      </>
    );
  }

  const revoke = async (w: WorkerRow) => {
    if (!window.confirm(fill(ADMIN_RENDER.workers.confirm, { name: w.worker_id }))) return;
    try {
      await revokeWorker(w.worker_id);
      void load();
    } catch (err) {
      setError(err instanceof Error ? err.message : CLOUD.errors.generic);
    }
  };

  const cost = Object.entries(data?.cost_by_kind ?? {}).sort((a, b) => b[1] - a[1]);

  return (
    <>
      <PageHeader title={ADMIN_RENDER.title} description={ADMIN_RENDER.description} />
      {error && (
        <div className="mb-6">
          <ErrorNote message={error} />
        </div>
      )}
      {data && (
        <>
          <div className="mb-6 grid gap-6 lg:grid-cols-2">
            <Panel>
              <h2 className="font-semibold">{ADMIN_RENDER.queue.title}</h2>
              {data.queue.every((q) => q.queued === 0 && q.running === 0) && (
                <p className="mt-4 text-sm text-text-muted">{ADMIN_RENDER.queue.empty}</p>
              )}
              <table className="mt-4 w-full text-sm">
                <thead className="text-left text-xs text-text-muted">
                  <tr>
                    <th className="pb-2 pr-4 font-medium">{ADMIN_RENDER.queue.kind}</th>
                    <th className="pb-2 pr-4 text-right font-medium">{ADMIN_RENDER.queue.queued}</th>
                    <th className="pb-2 pr-4 text-right font-medium">{ADMIN_RENDER.queue.running}</th>
                    <th className="pb-2 text-right font-medium">{ADMIN_RENDER.queue.oldest}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.queue.map((q) => (
                    <tr key={q.kind} className="border-t border-border">
                      <td className="py-2 pr-4 text-text-secondary">{kindLabel(q.kind)}</td>
                      <td className="py-2 pr-4 text-right tabular-nums text-text-primary">{q.queued}</td>
                      <td className="py-2 pr-4 text-right tabular-nums text-text-primary">{q.running}</td>
                      <td className="py-2 text-right tabular-nums text-text-secondary">{wait(q.oldest_wait_s)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
            <Panel>
              <h2 className="font-semibold">{ADMIN_RENDER.pool.title}</h2>
              <table className="mt-4 w-full text-sm">
                <thead className="text-left text-xs text-text-muted">
                  <tr>
                    <th className="pb-2 pr-4 font-medium">{ADMIN_RENDER.pool.cls}</th>
                    <th className="pb-2 pr-4 text-right font-medium">{ADMIN_RENDER.pool.desired}</th>
                    <th className="pb-2 text-right font-medium">{ADMIN_RENDER.pool.running}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.pool.classes.map((c) => (
                    <tr key={c.class} className="border-t border-border">
                      <td className="py-2 pr-4 text-text-secondary">
                        {c.class} <span className="text-xs text-text-muted">({data.pool.name})</span>
                      </td>
                      <td className="py-2 pr-4 text-right tabular-nums text-text-primary">{c.desired ?? "—"}</td>
                      <td className="py-2 text-right tabular-nums text-text-primary">{c.machines}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <h2 className="mt-8 font-semibold">{ADMIN_RENDER.cost.title}</h2>
              {cost.length === 0 ? (
                <p className="mt-4 text-sm text-text-muted">{ADMIN_RENDER.cost.empty}</p>
              ) : (
                <table className="mt-4 w-full text-sm">
                  <tbody>
                    {cost.map(([kind, cu]) => (
                      <tr key={kind} className="border-t border-border first:border-t-0">
                        <td className="py-2 pr-4 text-text-secondary">{kindLabel(kind)}</td>
                        <td className="py-2 text-right tabular-nums text-text-primary">
                          {formatCu(cu)} <span className="text-xs text-text-muted">{ADMIN_RENDER.cost.unit}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Panel>
          </div>
          <Workers rows={data.workers} onRevoke={revoke} />
          <IssueForm onIssued={() => void load()} />
          <Panel>
            <h2 className="font-semibold">{ADMIN_RENDER.failures.title}</h2>
            {data.recent_failures.length === 0 ? (
              <p className="mt-4 text-sm text-text-muted">{ADMIN_RENDER.failures.empty}</p>
            ) : (
              <ul className="mt-4 space-y-2 text-sm">
                {data.recent_failures.map((f) => (
                  <li key={f.job_id} className="flex flex-wrap gap-x-3 text-text-secondary">
                    <span className="font-mono text-xs text-text-muted">{f.job_id.slice(0, 8)}</span>
                    <span>{kindLabel(f.kind)}</span>
                    <span className="text-red-300">{f.error?.code}</span>
                    <span>{f.error?.message}</span>
                    <span className="text-text-muted">{timeAgo(f.finished_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </>
      )}
      <AiAdmin className="mt-10" />
    </>
  );
}
