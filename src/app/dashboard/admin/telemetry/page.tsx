"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import { Download, RefreshCw } from "lucide-react";
import {
  ErrorNote,
  PageHeader,
  Panel,
  useDashboardUser,
} from "@/components/dashboard/DashboardShell";
import { UsageChart } from "@/components/dashboard/UsageChart";
import { Button } from "@/components/ui/Button";
import { formatDate, parseServerDate } from "@/lib/api";
import { ADMIN_TELEMETRY } from "@/lib/constants";
import {
  crashFileLink,
  downloadCsv,
  feedbackFileLink,
  getCrashGroup,
  getSummary,
  listCrashGroups,
  listFeedback,
  replyToFeedback,
  updateCrashGroup,
  updateFeedback,
  type CrashGroup,
  type CrashGroupDetail,
  type CrashStatus,
  type FeedbackItem,
  type FeedbackStatus,
  type TelemetryTab,
} from "@/lib/telemetryAdmin";
import { cn } from "@/lib/utils";

const nf = new Intl.NumberFormat("en-US");
const pct = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 });
const CRASH_STATUSES: CrashStatus[] = ["new", "investigating", "fixed", "ignored"];
const FEEDBACK_STATUSES: FeedbackStatus[] = ["new", "replied", "closed"];

function message(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

/** Load whenever `load` changes; keeps the previous data while refetching. */
function useLoad<T>(load: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    load().then(
      (value) => {
        if (live) {
          setData(value);
          setError(null);
        }
      },
      (err) => {
        if (live) setError(message(err, "Something went wrong."));
      }
    );
    return () => {
      live = false;
    };
  }, [load, tick]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, reload, setData };
}

function when(value: string | null | undefined): string {
  if (!value) return "—";
  return parseServerDate(value).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function Badge({ children, tone = "muted" }: { children: React.ReactNode; tone?: "muted" | "accent" | "warn" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs",
        tone === "accent" && "border-accent/40 text-accent",
        tone === "warn" && "border-warn/40 text-warn",
        tone === "muted" && "border-border text-text-secondary"
      )}
    >
      {children}
    </span>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Panel>
      <p className="text-xs uppercase tracking-wider text-text-muted">{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
    </Panel>
  );
}

function Table({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-text-muted">
          <tr>
            {head.map((h, i) => (
              <th key={h} className={cn("py-2 pr-4 font-medium", i > 0 && "text-right")}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={String(row[0])} className="border-t border-border">
              {row.map((cell, i) => (
                <td
                  key={i}
                  className={cn(
                    "py-2 pr-4",
                    i === 0 ? "font-mono text-text-secondary" : "text-right tabular-nums text-text-primary"
                  )}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Overview ------------------------------------------------------------------

function Overview({ days }: { days: number }) {
  const load = useCallback(() => getSummary(days), [days]);
  const { data, error } = useLoad(load);
  if (error) return <ErrorNote message={error} />;
  if (!data) return <p className="text-sm text-text-muted">Loading…</p>;

  const latest = data.installs_per_day[data.installs_per_day.length - 1]?.count ?? 0;
  const totalInstalls = data.versions.reduce((s, v) => s + v.installs, 0);
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Installations today" value={nf.format(latest)} />
        <Stat label="Sessions" value={nf.format(data.sessions)} />
        <Stat label="Crashes" value={nf.format(data.crashes)} />
        <Stat
          label="Crash-free sessions"
          value={data.crash_free_sessions === null ? "—" : pct.format(data.crash_free_sessions)}
        />
      </div>
      <Panel>
        <h2 className="mb-6 font-semibold">{ADMIN_TELEMETRY.installsChart}</h2>
        <UsageChart
          data={data.installs_per_day}
          unit={ADMIN_TELEMETRY.installsUnit}
          label={ADMIN_TELEMETRY.installsChart}
        />
      </Panel>
      {data.top_events.length === 0 ? (
        <p className="text-sm text-text-muted">{ADMIN_TELEMETRY.emptyOverview}</p>
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          <Panel>
            <h2 className="mb-2 font-semibold">Versions</h2>
            <Table
              head={["Version", "Installations", "Share"]}
              rows={data.versions.map((v) => [
                v.version,
                nf.format(v.installs),
                totalInstalls ? pct.format(v.installs / totalInstalls) : "—",
              ])}
            />
          </Panel>
          <Panel>
            <h2 className="mb-2 font-semibold">Top events</h2>
            <Table head={["Event", "Count"]} rows={data.top_events.map((e) => [e.name, nf.format(e.events)])} />
          </Panel>
          <Panel className="md:col-span-2">
            <h2 className="mb-2 font-semibold">Timings</h2>
            <Table
              head={["Event", "p50 (ms)", "p95 (ms)", "Samples"]}
              rows={data.timings.map((t) => [
                t.name,
                t.p50_ms === null ? "—" : nf.format(t.p50_ms),
                t.p95_ms === null ? "—" : nf.format(t.p95_ms),
                nf.format(t.samples),
              ])}
            />
          </Panel>
        </div>
      )}
    </div>
  );
}

// --- Crashes ---------------------------------------------------------------------

function CrashDetail({ signature, onSaved }: { signature: string; onSaved: (g: CrashGroup) => void }) {
  const load = useCallback(() => getCrashGroup(signature), [signature]);
  const { data, error } = useLoad<CrashGroupDetail>(load);
  const [form, setForm] = useState<{ status: CrashStatus; title: string; fixed_in: string; note: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  if (error) return <ErrorNote message={error} />;
  if (!data) return <p className="text-sm text-text-muted">Loading…</p>;
  const values = form ?? {
    status: data.status,
    title: data.title,
    fixed_in: data.fixed_in ?? "",
    note: data.note ?? "",
  };
  const set = (patch: Partial<typeof values>) => setForm({ ...values, ...patch });

  async function save() {
    setBusy(true);
    setNote("");
    try {
      const saved = await updateCrashGroup(signature, {
        status: values.status,
        title: values.title.trim() || data!.title,
        fixed_in: values.fixed_in.trim() || null,
        note: values.note.trim() || null,
      });
      onSaved(saved);
      setNote("Saved. The app shows this as a known issue when Fixed in is set.");
    } catch (err) {
      setNote(message(err, "Couldn't save."));
    } finally {
      setBusy(false);
    }
  }

  async function open(crashId: string, file: "minidump" | "log") {
    try {
      const link = await crashFileLink(crashId, file);
      window.location.assign(link.url);
    } catch (err) {
      setNote(message(err, "Couldn't get the file."));
    }
  }

  const input =
    "w-full rounded-[var(--radius-button)] border border-border bg-background px-3 py-2 text-sm text-text-primary";
  return (
    <div className="mt-4 space-y-4 border-t border-border pt-4">
      <div className="grid gap-3 md:grid-cols-[1fr_10rem_10rem]">
        <label className="text-sm">
          <span className="text-text-muted">Title</span>
          <input className={cn(input, "mt-1")} value={values.title} onChange={(e) => set({ title: e.target.value })} />
        </label>
        <label className="text-sm">
          <span className="text-text-muted">Status</span>
          <select
            className={cn(input, "mt-1")}
            value={values.status}
            onChange={(e) => set({ status: e.target.value as CrashStatus })}
          >
            {CRASH_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="text-text-muted">Fixed in</span>
          <input
            className={cn(input, "mt-1 font-mono")}
            placeholder="1.1.2"
            value={values.fixed_in}
            onChange={(e) => set({ fixed_in: e.target.value })}
          />
        </label>
      </div>
      <label className="block text-sm">
        <span className="text-text-muted">Note</span>
        <textarea className={cn(input, "mt-1")} rows={2} value={values.note} onChange={(e) => set({ note: e.target.value })} />
      </label>
      <div className="flex items-center gap-3">
        <Button size="sm" onClick={save} disabled={busy}>
          Save
        </Button>
        {note && (
          <p className="text-sm text-text-secondary" role="status">
            {note}
          </p>
        )}
      </div>
      {data.reports.map((r) => (
        <div key={r.crash_id} className="rounded-[var(--radius-button)] border border-border p-3">
          <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
            <span>{when(r.received_at)}</span>
            <Badge>{r.kind}</Badge>
            <span>{r.app_version}</span>
            {r.os && <span>{r.os}</span>}
            {r.gpu_driver && <span>driver {r.gpu_driver}</span>}
            <Badge tone={r.symbolicated ? "accent" : "muted"}>{r.symbolicated ? "symbolicated" : "raw frames"}</Badge>
            <span className="ml-auto flex gap-3">
              {r.has_minidump && (
                <button type="button" className="text-accent hover:underline" onClick={() => open(r.crash_id, "minidump")}>
                  Minidump
                </button>
              )}
              {r.has_log && (
                <button type="button" className="text-accent hover:underline" onClick={() => open(r.crash_id, "log")}>
                  Log
                </button>
              )}
            </span>
          </div>
          <ol className="mt-2 space-y-0.5 font-mono text-xs text-text-secondary">
            {r.frames.slice(0, 12).map((f, i) => (
              <li key={i} className="break-all">
                {i}. {f}
              </li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  );
}

function Crashes() {
  const { data, error, setData } = useLoad(listCrashGroups);
  const [openSig, setOpenSig] = useState<string | null>(null);
  if (error) return <ErrorNote message={error} />;
  if (!data) return <p className="text-sm text-text-muted">Loading…</p>;
  if (data.length === 0) return <p className="text-sm text-text-muted">{ADMIN_TELEMETRY.emptyCrashes}</p>;
  return (
    <div className="space-y-3">
      {data.map((g) => (
        <Panel key={g.signature}>
          <button
            type="button"
            className="flex w-full flex-wrap items-center gap-3 text-left"
            aria-expanded={openSig === g.signature}
            onClick={() => setOpenSig(openSig === g.signature ? null : g.signature)}
          >
            <span className="min-w-0 flex-1 break-all font-mono text-sm text-text-primary">{g.title}</span>
            <Badge tone={g.status === "fixed" ? "accent" : g.status === "new" ? "warn" : "muted"}>{g.status}</Badge>
            {g.fixed_in && <Badge tone="accent">fixed in {g.fixed_in}</Badge>}
            <span className="text-sm tabular-nums text-text-secondary">{nf.format(g.count)}×</span>
          </button>
          <p className="mt-1 text-xs text-text-muted">
            {g.kind} · {g.signature} · {g.versions.join(", ")} · last {when(g.last_seen)}
          </p>
          {openSig === g.signature && (
            <CrashDetail
              signature={g.signature}
              onSaved={(saved) => setData(data.map((x) => (x.signature === saved.signature ? saved : x)))}
            />
          )}
        </Panel>
      ))}
    </div>
  );
}

// --- Feedback -----------------------------------------------------------------------

function FeedbackCard({ item, onChange }: { item: FeedbackItem; onChange: (f: FeedbackItem) => void }) {
  const [shot, setShot] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  async function showShot() {
    try {
      setShot((await feedbackFileLink(item.feedback_id, "screenshot")).url);
    } catch (err) {
      setNote(message(err, "Couldn't load the screenshot."));
    }
  }

  async function openLog() {
    try {
      window.location.assign((await feedbackFileLink(item.feedback_id, "log")).url);
    } catch (err) {
      setNote(message(err, "Couldn't get the log."));
    }
  }

  async function send(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setNote("");
    try {
      onChange(await replyToFeedback(item.feedback_id, reply.trim()));
      setReply("");
      setNote("Reply sent.");
    } catch (err) {
      setNote(message(err, "Couldn't send the reply."));
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(status: FeedbackStatus) {
    try {
      onChange(await updateFeedback(item.feedback_id, status));
    } catch (err) {
      setNote(message(err, "Couldn't update the status."));
    }
  }

  return (
    <Panel>
      <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
        <Badge tone={item.kind === "bug" ? "warn" : "accent"}>{item.kind}</Badge>
        <span>{when(item.received_at)}</span>
        <span>{item.app_version}</span>
        {item.os && <span>{item.os}</span>}
        <select
          aria-label="Status"
          className="ml-auto rounded-[var(--radius-button)] border border-border bg-background px-2 py-1 text-xs text-text-primary"
          value={item.status}
          onChange={(e) => setStatus(e.target.value as FeedbackStatus)}
        >
          {FEEDBACK_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>
      <p className="mt-3 whitespace-pre-wrap text-sm text-text-primary">{item.text}</p>
      <div className="mt-3 flex flex-wrap gap-4 text-sm">
        {item.has_screenshot && !shot && (
          <button type="button" className="text-accent hover:underline" onClick={showShot}>
            Show screenshot
          </button>
        )}
        {item.has_log && (
          <button type="button" className="text-accent hover:underline" onClick={openLog}>
            Download log
          </button>
        )}
      </div>
      {shot && (
        <Image
          src={shot}
          alt={`Screenshot sent with ${item.kind} feedback on ${formatDate(item.received_at)}`}
          width={1280}
          height={800}
          unoptimized
          className="mt-3 h-auto max-h-[480px] w-auto max-w-full rounded-[var(--radius-button)] border border-border"
        />
      )}
      {item.email ? (
        <form onSubmit={send} className="mt-4 space-y-2">
          <p className="text-xs text-text-muted">
            Reply to {item.email}
            {item.replied_at ? ` · last replied ${when(item.replied_at)}` : ""}
          </p>
          <textarea
            className="w-full rounded-[var(--radius-button)] border border-border bg-background px-3 py-2 text-sm text-text-primary"
            rows={3}
            maxLength={5000}
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            aria-label={`Reply to ${item.email}`}
          />
          <Button size="sm" type="submit" disabled={busy || !reply.trim()}>
            Send reply
          </Button>
        </form>
      ) : (
        <p className="mt-4 text-xs text-text-muted">No reply asked for, so no address is stored.</p>
      )}
      {note && (
        <p className="mt-2 text-sm text-text-secondary" role="status">
          {note}
        </p>
      )}
    </Panel>
  );
}

function FeedbackInbox() {
  const { data, error, setData } = useLoad(listFeedback);
  if (error) return <ErrorNote message={error} />;
  if (!data) return <p className="text-sm text-text-muted">Loading…</p>;
  if (data.length === 0) return <p className="text-sm text-text-muted">{ADMIN_TELEMETRY.emptyFeedback}</p>;
  return (
    <div className="space-y-3">
      {data.map((f) => (
        <FeedbackCard
          key={f.feedback_id}
          item={f}
          onChange={(next) => setData(data.map((x) => (x.feedback_id === next.feedback_id ? next : x)))}
        />
      ))}
    </div>
  );
}

// --- Page ------------------------------------------------------------------------------

export default function TelemetryAdminPage() {
  const user = useDashboardUser();
  const [tab, setTab] = useState<TelemetryTab>("overview");
  const [days, setDays] = useState<number>(ADMIN_TELEMETRY.windows[1]);
  const [round, setRound] = useState(0);
  const [exportError, setExportError] = useState("");

  if (!user.is_admin) {
    return (
      <>
        <PageHeader title={ADMIN_TELEMETRY.title} />
        <ErrorNote message={ADMIN_TELEMETRY.adminsOnly} />
      </>
    );
  }

  async function exportTab() {
    setExportError("");
    try {
      await downloadCsv(tab, days);
    } catch (err) {
      setExportError(message(err, "Export failed."));
    }
  }

  return (
    <>
      <PageHeader
        title={ADMIN_TELEMETRY.title}
        description={ADMIN_TELEMETRY.description}
        actions={
          <div className="flex items-center gap-2">
            <select
              aria-label="Period"
              className="h-9 rounded-[var(--radius-button)] border border-border bg-background px-2 text-sm text-text-primary"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
            >
              {ADMIN_TELEMETRY.windows.map((d) => (
                <option key={d} value={d}>
                  Last {d} days
                </option>
              ))}
            </select>
            <Button size="sm" variant="ghost" onClick={() => setRound((r) => r + 1)} aria-label="Refresh">
              <RefreshCw size={16} aria-hidden />
            </Button>
            <Button size="sm" variant="secondary" onClick={exportTab}>
              <Download size={16} aria-hidden />
              <span className="ml-2">{ADMIN_TELEMETRY.exportCsv}</span>
            </Button>
          </div>
        }
      />
      {exportError && (
        <div className="mb-6">
          <ErrorNote message={exportError} />
        </div>
      )}
      <div role="tablist" aria-label={ADMIN_TELEMETRY.title} className="mb-6 flex gap-1 border-b border-border">
        {(Object.keys(ADMIN_TELEMETRY.tabs) as TelemetryTab[]).map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={cn(
              "border-b-2 px-3 py-2 text-sm",
              tab === key ? "border-accent text-accent" : "border-transparent text-text-secondary hover:text-text-primary"
            )}
          >
            {ADMIN_TELEMETRY.tabs[key]}
          </button>
        ))}
      </div>
      <div role="tabpanel" key={`${tab}-${round}`}>
        {tab === "overview" && <Overview days={days} />}
        {tab === "crashes" && <Crashes />}
        {tab === "feedback" && <FeedbackInbox />}
      </div>
    </>
  );
}
