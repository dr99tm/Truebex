"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { Button } from "@/components/ui/Button";
import { Badge, can, Field, inputClass, OkNote, useMember } from "@/components/supplier/SupplierShell";
import { formatDate } from "@/lib/api";
import { SUPPLIER } from "@/lib/constants";
import {
  countsLine,
  downloadTemplate,
  fill,
  supplierApi,
  type DryRun,
  type FeedReport,
  type FeedSource,
  type ImportItem,
} from "@/lib/supplier";
import { cn } from "@/lib/utils";

const I = SUPPLIER.imports;

function ErrorTable({ errors, warnings }: { errors: FeedReport["errors"]; warnings?: FeedReport["warnings"] }) {
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold">{I.errors}</h3>
        {errors.length === 0 ? (
          <p className="mt-1 text-sm text-text-muted">{I.noErrors}</p>
        ) : (
          <div className="mt-2 max-h-80 overflow-auto rounded-md border border-border">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface-elevated text-left text-xs text-text-muted">
                <tr>
                  <th className="px-3 py-2 font-medium">{I.row}</th>
                  <th className="px-3 py-2 font-medium">{I.column}</th>
                  <th className="px-3 py-2 font-medium">{I.code}</th>
                  <th className="px-3 py-2 font-medium">{I.value}</th>
                </tr>
              </thead>
              <tbody>
                {errors.map((e, n) => (
                  <tr key={`${e.row}-${e.column}-${n}`} className="border-t border-border align-top">
                    <td className="px-3 py-1.5 tabular-nums">{e.row}</td>
                    <td className="px-3 py-1.5 font-mono text-xs">{e.column}</td>
                    <td className="px-3 py-1.5">
                      <span className="font-mono text-xs text-red-300">{e.code}</span>
                      <span className="block text-xs text-text-muted">{I.codes[e.code] ?? ""}</span>
                    </td>
                    <td className="max-w-[12rem] truncate px-3 py-1.5 font-mono text-xs" title={e.value}>
                      {e.value || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {warnings && warnings.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">{I.warnings}</h3>
          <ul className="mt-1 space-y-1 text-xs text-warn">
            {warnings.slice(0, 50).map((w, n) => (
              <li key={n}>
                {w.row ? `${I.row} ${w.row} · ` : ""}
                <span className="font-mono">{w.column}</span> {w.value ? `(${w.value})` : ""} — {I.codes[w.code] ?? w.code}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Counts({ r }: { r: DryRun | FeedReport }) {
  return (
    <div className="space-y-1 text-sm">
      <p className={cn("font-medium tabular-nums", r.rejected ? "text-warn" : "text-text-primary")}>{countsLine(I.summary, r)}</p>
      {"new_products" in r && (
        <p className="text-text-muted">{fill(I.newItems, { products: r.new_products, variants: r.new_variants })}</p>
      )}
      {r.hidden > 0 && <p className="text-text-muted">{fill(I.hidden, { n: r.hidden })}</p>}
    </div>
  );
}

function FeedPanel({ source, editable, onChange }: { source: FeedSource | null; editable: boolean; onChange: () => void }) {
  const [form, setForm] = useState({ url: source?.url ?? "", format: source?.format ?? "csv", mode: source?.mode ?? "replace" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel>
      <h2 className="font-semibold">{I.feedTitle}</h2>
      <p className="mt-1 text-sm text-text-muted">{I.feedHelp}</p>
      {source && (
        <dl className="mt-3 grid gap-1 text-sm sm:grid-cols-2">
          <div>
            <dt className="inline text-text-muted">{I.nextPull}: </dt>
            <dd className="inline">{formatDate(source.next_pull_at)}</dd>
          </div>
          <div>
            <dt className="inline text-text-muted">{I.lastPull}: </dt>
            <dd className="inline">
              {source.last_pull_at ? formatDate(source.last_pull_at) : "—"}
              {source.last_status && ` · ${I.feedStatuses[source.last_status] ?? source.last_status}`}
            </dd>
          </div>
          {source.last_error && <p className="text-xs text-red-300 sm:col-span-2">{source.last_error}</p>}
        </dl>
      )}
      {editable && (
        <form
          className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto_auto]"
          onSubmit={(e) => {
            e.preventDefault();
            void act(() => supplierApi.setSource(form));
          }}
        >
          <Field label={I.feedUrl}>
            <input type="url" required value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} className={inputClass} placeholder="https://" />
          </Field>
          <Field label={I.feedFormat}>
            <select value={form.format} onChange={(e) => setForm({ ...form, format: e.target.value })} className={inputClass}>
              <option value="csv">CSV</option>
              <option value="json">JSON</option>
            </select>
          </Field>
          <Field label={I.mode}>
            <select value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value })} className={inputClass}>
              <option value="replace">{I.modes.replace.split(":")[0]}</option>
              <option value="upsert">{I.modes.upsert.split(":")[0]}</option>
            </select>
          </Field>
          <div className="flex flex-wrap gap-2 sm:col-span-3">
            <Button type="submit" size="sm" disabled={busy}>
              {I.saveFeed}
            </Button>
            {source && (
              <>
                <Button type="button" size="sm" variant="secondary" disabled={busy} onClick={() => void act(() => supplierApi.pullSource())}>
                  {I.pullNow}
                </Button>
                <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => void act(() => supplierApi.removeSource())}>
                  {I.removeFeed}
                </Button>
              </>
            )}
          </div>
        </form>
      )}
      {error && <div className="mt-3"><ErrorNote message={error} /></div>}
      <p className="mt-3 text-xs text-text-muted">{I.keysHint}</p>
    </Panel>
  );
}

function ImportsInner() {
  const { role } = useMember();
  const editable = can(role, "catalogue");
  const params = useSearchParams();
  const [history, setHistory] = useState<{ imports: ImportItem[]; runs: FeedReport[]; source: FeedSource | null } | null>(null);
  const [error, setError] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState("upsert");
  const [current, setCurrent] = useState<ImportItem | null>(null);
  const [busy, setBusy] = useState(false);
  const [applying, setApplying] = useState(false);
  const [open, setOpen] = useState<string | null>(params.get("run"));

  const load = useCallback(async () => {
    try {
      setHistory(await supplierApi.imports());
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    supplierApi
      .imports()
      .then((h) => {
        if (!cancelled) setHistory(h);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function check(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError("");
    setCurrent(null);
    try {
      setCurrent(await supplierApi.uploadImport(file, mode));
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
    } finally {
      setBusy(false);
    }
  }

  async function apply() {
    if (!current) return;
    setApplying(true);
    setError("");
    try {
      let item = await supplierApi.applyImport(current.import_id);
      setCurrent(item);
      // The run starts at once; wait for its report (up to about 3 minutes).
      for (let i = 0; i < 90 && (!item.run || item.run.state === "queued" || item.run.state === "running"); i++) {
        await new Promise((r) => setTimeout(r, 2000));
        item = await supplierApi.importItem(current.import_id);
        setCurrent(item);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
    } finally {
      setApplying(false);
    }
  }

  async function template() {
    setError("");
    try {
      await downloadTemplate();
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
    }
  }

  const run = current?.run;
  return (
    <>
      <PageHeader
        title={I.title}
        description={I.description}
        actions={
          <Button size="sm" variant="secondary" onClick={() => void template()}>
            {I.template}
          </Button>
        }
      />
      <div className="space-y-6">
        <p className="-mt-4 text-xs text-text-muted">{I.templateHelp}</p>
        {error && <ErrorNote message={error} />}

        {editable && (
          <Panel>
            <h2 className="font-semibold">{I.upload}</h2>
            <form onSubmit={check} className="mt-3 space-y-4">
              <Field label={I.file}>
                <input
                  type="file"
                  accept=".xlsx,.csv,.json,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv,application/json"
                  onChange={(e) => {
                    setFile(e.target.files?.[0] ?? null);
                    setCurrent(null);
                  }}
                  className="text-sm text-text-secondary file:mr-3 file:rounded-[var(--radius-button)] file:border file:border-border file:bg-surface file:px-3 file:py-2 file:text-text-primary"
                />
              </Field>
              <fieldset>
                <legend className="text-sm text-text-secondary">{I.mode}</legend>
                <div className="mt-1 space-y-1">
                  {(["upsert", "replace"] as const).map((m) => (
                    <label key={m} className="flex items-start gap-2 text-sm">
                      <input type="radio" name="mode" value={m} checked={mode === m} onChange={() => setMode(m)} className="mt-1" />
                      {I.modes[m]}
                    </label>
                  ))}
                </div>
              </fieldset>
              <Button type="submit" size="sm" disabled={!file || busy}>
                {busy ? I.checking : I.check}
              </Button>
            </form>

            {current && (
              <div className="mt-6 space-y-4 border-t border-border pt-4">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-semibold">{run ? I.report : I.dryRun}</h3>
                  <span className="text-sm text-text-muted">{current.filename}</span>
                  {run && <Badge tone={run.state === "done" ? "good" : run.state === "failed" ? "bad" : "warn"}>{I.runStates[run.state]}</Badge>}
                </div>
                <Counts r={run && run.state !== "queued" && run.state !== "running" ? run : current.dry_run} />
                {run?.detail && <p className="text-sm text-red-300">{run.detail}</p>}
                <ErrorTable
                  errors={run && run.state === "done" ? run.errors : current.dry_run.errors}
                  warnings={run && run.state === "done" ? run.warnings : current.dry_run.warnings}
                />
                {!current.feed_id && !current.expired && (
                  <Button disabled={applying} onClick={() => void apply()}>
                    {applying ? I.applying : I.apply}
                  </Button>
                )}
                {current.expired && <p className="text-sm text-warn">{I.expired}</p>}
                {run?.state === "done" && <OkNote message={I.applied} />}
              </div>
            )}
          </Panel>
        )}

        {history && (
          <FeedPanel key={history.source?.url ?? "none"} source={history.source} editable={editable} onChange={() => void load()} />
        )}

        <Panel>
          <h2 className="font-semibold">{I.runs}</h2>
          {history && history.runs.length === 0 && <p className="mt-2 text-sm text-text-muted">{I.noRuns}</p>}
          <ul className="mt-3 divide-y divide-border">
            {history?.runs.map((r) => (
              <li key={r.feed_id} className="py-3">
                <button
                  type="button"
                  onClick={() => setOpen(open === r.feed_id ? null : r.feed_id)}
                  aria-expanded={open === r.feed_id}
                  className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 text-left text-sm"
                >
                  <Badge tone={r.state === "done" ? (r.rejected ? "warn" : "good") : r.state === "failed" ? "bad" : "neutral"}>
                    {I.runStates[r.state] ?? r.state}
                  </Badge>
                  <span className="text-text-secondary">
                    {I.sources[r.source] ?? r.source} · {r.format.toUpperCase()} · {r.mode}
                  </span>
                  <span className="text-text-muted">{formatDate(r.finished_at ?? r.created_at)}</span>
                  <span className="tabular-nums text-text-primary">{countsLine(I.summary, r)}</span>
                </button>
                {open === r.feed_id && (
                  <div className="mt-3">
                    {r.detail && <p className="mb-2 text-sm text-red-300">{r.detail}</p>}
                    <ErrorTable errors={r.errors} warnings={r.warnings} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </>
  );
}

export default function ImportsPage() {
  return (
    <Suspense fallback={<p className="text-text-muted">…</p>}>
      <ImportsInner />
    </Suspense>
  );
}
