"use client";

import { useCallback, useEffect, useState } from "react";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { UsageChart } from "@/components/dashboard/UsageChart";
import { UsageMeter } from "@/components/dashboard/UsageMeter";
import { TilePreview } from "@/components/cloud/TilePreview";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/lib/api";
import { fill } from "@/lib/catalogue";
import { CLOUD } from "@/lib/constants";
import {
  cancelJob,
  formatCu,
  formatMoney,
  getCloudUsage,
  jobError,
  listJobs,
  setOverageCap,
  type CloudUsage,
  type JobRecord,
} from "@/lib/jobs";
import { timeAgo } from "@/lib/time";
import { cn } from "@/lib/utils";

const LIVE = new Set(["queued", "claimed", "running"]);
const REFRESH_MS = 10_000;
const inputClass =
  "w-32 rounded-[var(--radius-button)] border border-border bg-background px-3 py-2 text-text-primary outline-none focus:border-accent/50";

function stateClass(state: JobRecord["state"]): string {
  if (state === "succeeded") return "text-text-primary";
  if (state === "failed" || state === "expired") return "text-red-300";
  if (LIVE.has(state)) return "text-accent";
  return "text-text-muted";
}

function Allowance({ usage }: { usage: CloudUsage }) {
  if (usage.limit_cu === 0) {
    return (
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-text-secondary">{CLOUD.meter.none}</p>
        <Button href="/pricing/" variant="secondary" size="sm">
          {CLOUD.meter.planCta}
        </Button>
      </div>
    );
  }
  return (
    <>
      {usage.limit_cu === null ? (
        <p className="text-sm text-text-secondary">{fill(CLOUD.meter.unlimited, { used: formatCu(usage.used_cu) })}</p>
      ) : (
        <UsageMeter
          used={usage.used_cu}
          limit={usage.limit_cu}
          unit={CLOUD.meter.unit}
          label={CLOUD.meter.label}
          digits={1}
        />
      )}
      {usage.reserved_cu > 0 && (
        <p className="mt-2 text-xs text-text-muted">{fill(CLOUD.meter.reserved, { n: formatCu(usage.reserved_cu) })}</p>
      )}
      <p className="mt-4 text-xs text-text-muted">{CLOUD.meter.help}</p>
    </>
  );
}

function ByKind({ rows }: { rows: Record<string, number> }) {
  const entries = Object.entries(rows).sort((a, b) => b[1] - a[1]);
  return (
    <Panel>
      <h2 className="font-semibold">{CLOUD.byKind.title}</h2>
      {entries.length === 0 ? (
        <p className="mt-4 text-sm text-text-muted">{CLOUD.byKind.empty}</p>
      ) : (
        <table className="mt-4 w-full text-sm">
          <tbody>
            {entries.map(([kind, cu]) => (
              <tr key={kind} className="border-t border-border first:border-t-0">
                <td className="py-2 pr-4 text-text-secondary">{CLOUD.kinds[kind as keyof typeof CLOUD.kinds] ?? kind}</td>
                <td className="py-2 text-right tabular-nums text-text-primary">{formatCu(cu)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}

function Overage({ usage, onSaved }: { usage: CloudUsage; onSaved: (u: CloudUsage) => void }) {
  const [cap, setCap] = useState(String(usage.overage.cap_cu));
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setNote("");
    try {
      onSaved(await setOverageCap(Number(cap)));
      setNote(CLOUD.overage.saved);
    } catch (err) {
      setNote(jobError(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Panel className="mb-6">
      <h2 className="font-semibold">{CLOUD.overage.title}</h2>
      <p className="mt-2 text-sm text-text-secondary">
        {fill(CLOUD.overage.text, { price: formatMoney(usage.overage.price_minor, usage.overage.currency) })}
      </p>
      {usage.overage.used_cu > 0 && (
        <p className="mt-2 text-sm text-warn">{fill(CLOUD.overage.used, { n: formatCu(usage.overage.used_cu) })}</p>
      )}
      <form onSubmit={save} className="mt-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-text-muted">
          {CLOUD.overage.label}
          <input
            type="number"
            min={0}
            max={100000}
            step={1}
            value={cap}
            onChange={(e) => setCap(e.target.value)}
            className={inputClass}
          />
        </label>
        <Button type="submit" size="sm" disabled={busy}>
          {busy ? CLOUD.overage.saving : CLOUD.overage.save}
        </Button>
        {note && (
          <p role="status" className="text-sm text-text-secondary">
            {note}
          </p>
        )}
      </form>
    </Panel>
  );
}

function JobRow({
  job,
  previewing,
  onCancel,
  onPreview,
}: {
  job: JobRecord;
  previewing: boolean;
  onCancel: (job: JobRecord) => void;
  onPreview: (job: JobRecord) => void;
}) {
  const live = LIVE.has(job.state);
  const following = job.state === "succeeded" && job.follow;
  const canPreview = job.state === "succeeded" && job.output_ready && (job.kind === "panorama" || job.kind === "tiles");
  return (
    <tr className="border-t border-border align-top">
      <td className="py-3 pr-4">
        <p className="text-text-primary">{CLOUD.kinds[job.kind] ?? job.kind}</p>
        <p className="font-mono text-xs text-text-muted">
          {job.job_id.slice(0, 8)}
          {following && <span className="ml-2 font-sans text-accent">{CLOUD.jobs.following}</span>}
        </p>
      </td>
      <td className="py-3 pr-4">
        <p className={stateClass(job.state)}>
          {CLOUD.states[job.state]}
          {job.state === "running" && job.progress > 0 && ` · ${Math.round(job.progress * 100)}%`}
        </p>
        {(job.error?.message || job.message) && (
          <p className="max-w-xs text-xs text-text-muted">{job.error?.message || job.message}</p>
        )}
      </td>
      <td className="py-3 pr-4 text-text-secondary">{timeAgo(job.created_at)}</td>
      <td className="py-3 pr-4 text-right tabular-nums">
        {job.cost_units !== null ? (
          <span className="text-text-primary">{formatCu(job.cost_units)}</span>
        ) : (
          <span className="text-text-muted">{fill(CLOUD.jobs.estimate, { n: formatCu(job.cost_units_estimate) })}</span>
        )}
      </td>
      <td className="py-3 text-right">
        <div className="flex justify-end gap-3 text-xs">
          {canPreview && (
            <button type="button" onClick={() => onPreview(job)} className="text-accent hover:underline">
              {previewing ? CLOUD.jobs.hide : CLOUD.jobs.preview}
            </button>
          )}
          {(live || following) && (
            <button type="button" onClick={() => onCancel(job)} className="text-text-secondary hover:text-text-primary">
              {following ? CLOUD.jobs.stopFollowing : CLOUD.jobs.cancel}
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

export default function CloudPage() {
  const [usage, setUsage] = useState<CloudUsage | null>(null);
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [preview, setPreview] = useState<JobRecord | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [u, page] = await Promise.all([getCloudUsage(), listJobs()]);
      setUsage(u);
      setJobs(page.jobs);
      setCursor(page.next_cursor);
      setError("");
    } catch (err) {
      setError(jobError(err));
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // While a job is queued or rendering, or a set follows edits (each edit
  // queues an update), refresh the list every 10 s.
  const anyLive = jobs.some((j) => LIVE.has(j.state) || (j.state === "succeeded" && j.follow));
  useEffect(() => {
    if (!anyLive) return;
    const t = setInterval(() => void refresh(), REFRESH_MS);
    return () => clearInterval(t);
  }, [anyLive, refresh]);

  const more = async () => {
    if (!cursor) return;
    try {
      const page = await listJobs(cursor);
      setJobs((old) => [...old, ...page.jobs]);
      setCursor(page.next_cursor);
    } catch (err) {
      setError(jobError(err));
    }
  };

  const cancel = async (job: JobRecord) => {
    try {
      const updated = await cancelJob(job.job_id);
      setJobs((old) => old.map((j) => (j.job_id === updated.job_id ? updated : j)));
      if (preview?.job_id === updated.job_id) setPreview(updated);
      void refresh();
    } catch (err) {
      setError(jobError(err));
    }
  };

  return (
    <>
      <PageHeader
        title={CLOUD.title}
        description={
          usage
            ? `${CLOUD.description} ${formatDate(usage.period_start)} – ${formatDate(usage.period_end)} (UTC).`
            : CLOUD.description
        }
      />
      {error && (
        <div className="mb-6">
          <ErrorNote message={error} />
        </div>
      )}
      {!loaded ? (
        <p className="text-sm text-text-muted">{CLOUD.loading}</p>
      ) : (
        usage && (
          <>
            <Panel className="mb-6">
              <Allowance usage={usage} />
            </Panel>
            {usage.overage.allowed && <Overage usage={usage} onSaved={setUsage} />}
            <div className="mb-6 grid gap-6 lg:grid-cols-[2fr_1fr]">
              <Panel>
                <h2 className="mb-6 font-semibold">{CLOUD.chart.title}</h2>
                <UsageChart
                  data={usage.daily.map((d) => ({ day: d.day, count: d.cu }))}
                  label={CLOUD.chart.label}
                  unit={CLOUD.chart.unit}
                />
              </Panel>
              <ByKind rows={usage.by_kind} />
            </div>
          </>
        )
      )}
      {preview && (
        <Panel className="mb-6">
          <h2 className="mb-4 font-semibold">{CLOUD.preview.title}</h2>
          <TilePreview key={preview.job_id} jobId={preview.job_id} following={preview.follow} />
        </Panel>
      )}
      {loaded && (
        <Panel>
          <h2 className="font-semibold">{CLOUD.jobs.title}</h2>
          {jobs.length === 0 ? (
            <p className="mt-4 text-sm text-text-muted">{CLOUD.jobs.empty}</p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[36rem] text-sm">
                <thead className="text-left text-xs text-text-muted">
                  <tr>
                    <th className="pb-2 pr-4 font-medium">{CLOUD.jobs.columns.job}</th>
                    <th className="pb-2 pr-4 font-medium">{CLOUD.jobs.columns.state}</th>
                    <th className="pb-2 pr-4 font-medium">{CLOUD.jobs.columns.submitted}</th>
                    <th className="pb-2 pr-4 text-right font-medium">{CLOUD.jobs.columns.cost}</th>
                    <th className="pb-2 text-right font-medium">
                      <span className="sr-only">{CLOUD.jobs.columns.actions}</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <JobRow
                      key={job.job_id}
                      job={job}
                      previewing={preview?.job_id === job.job_id}
                      onCancel={cancel}
                      onPreview={(j) => setPreview((p) => (p?.job_id === j.job_id ? null : j))}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {cursor && (
            <button type="button" onClick={more} className={cn("mt-4 text-sm text-accent hover:underline")}>
              {CLOUD.jobs.more}
            </button>
          )}
        </Panel>
      )}
    </>
  );
}
