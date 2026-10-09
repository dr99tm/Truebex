"use client";

import { useState } from "react";
import { Copy, ExternalLink, Link2 } from "lucide-react";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { UsageChart } from "@/components/dashboard/UsageChart";
import { useApiData } from "@/components/dashboard/useApiData";
import { formatDate } from "@/lib/api";
import { DASHBOARD_SHARES as T } from "@/lib/constants";
import { extendShare, fillDays, getShare, listShares, revokeShare, sortShares, type Share } from "@/lib/shares";
import { timeAgo } from "@/lib/time";
import { cn } from "@/lib/utils";

const nf = new Intl.NumberFormat("en-US");

export default function SharesPage() {
  const shares = useApiData(listShares);
  const rows = sortShares(shares.data?.shares ?? []);
  const limit = shares.data?.limits.share_links ?? null;
  const days = shares.data?.limits.share_days ?? 30;
  const live = rows.filter((s) => s.state === "live" || s.state === "uploading").length;

  return (
    <>
      <PageHeader
        title={T.title}
        description={T.description}
        actions={
          shares.data && limit !== null ? (
            <p className="text-sm text-text-muted">
              {live} of {limit} {T.limit}
            </p>
          ) : undefined
        }
      />
      {shares.error && (
        <div className="mb-6">
          <ErrorNote message={shares.error} />
        </div>
      )}
      {shares.loading && !shares.data ? (
        <p className="text-sm text-text-muted">Loading…</p>
      ) : rows.length === 0 && !shares.error ? (
        <Panel>
          <Link2 size={20} className="text-text-muted" aria-hidden />
          <p className="mt-3 font-medium text-text-primary">{T.emptyTitle}</p>
          <p className="mt-1 text-sm text-text-muted">{T.emptyText}</p>
        </Panel>
      ) : (
        <ul className="space-y-4">
          {rows.map((s) => (
            <li key={s.share_id}>
              <ShareCard share={s} days={days} onChange={shares.reload} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function ShareCard({ share, days, onChange }: { share: Share; days: number; onChange: () => Promise<void> }) {
  const [confirming, setConfirming] = useState(false);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<Share | null>(null);
  const [open, setOpen] = useState(false);
  const open_ = share.state === "live" || share.state === "uploading";

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      setConfirming(false);
      setDetail(null);
      setOpen(false);
      await onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!share.url) return;
    try {
      await navigator.clipboard.writeText(share.url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt(T.copy, share.url);
    }
  }

  async function toggleVisits() {
    const next = !open;
    setOpen(next);
    if (next && !detail) {
      try {
        setDetail(await getShare(share.share_id));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong.");
      }
    }
  }

  const ended = share.state === "expired" || share.state === "revoked";
  return (
    <Panel className={cn(ended && "opacity-80")}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate font-semibold text-text-primary">{share.title}</h2>
          <p className="mt-1 text-sm text-text-muted">
            <span
              className={cn(
                "mr-2 inline-block rounded-full px-2 py-0.5 text-xs",
                share.state === "live" ? "bg-accent/10 text-accent" : "bg-white/5 text-text-secondary"
              )}
            >
              {T.states[share.state]}
            </span>
            {share.state === "revoked"
              ? `${T.endedOn} ${formatDate(share.revoked_at)}`
              : share.expires_at
                ? `${share.state === "expired" ? T.endedOn : T.expires} ${formatDate(share.expires_at)}`
                : ""}
          </p>
        </div>
        {share.url && !ended && (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={copy}
              className="inline-flex items-center gap-1.5 rounded-[var(--radius-button)] border border-border px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary"
            >
              <Copy size={14} aria-hidden />
              {copied ? T.copied : T.copy}
            </button>
            <a
              href={share.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-[var(--radius-button)] border border-border px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary"
            >
              <ExternalLink size={14} aria-hidden />
              {T.open}
            </a>
          </div>
        )}
      </div>

      {share.url && !ended && <p className="mt-3 truncate font-mono text-xs text-text-muted">{share.url}</p>}
      {share.state === "uploading" && <p className="mt-3 text-sm text-text-muted">{T.uploadingNote}</p>}

      <dl className="mt-4 grid grid-cols-3 gap-4 text-sm sm:max-w-md">
        <div>
          <dt className="text-text-muted">{T.visits}</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">{nf.format(share.visits.total)}</dd>
        </div>
        <div>
          <dt className="text-text-muted">{T.unique}</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">{nf.format(share.visits.unique)}</dd>
        </div>
        <div>
          <dt className="text-text-muted">{T.lastVisit}</dt>
          <dd className="mt-0.5 text-text-secondary">{share.visits.last_at ? timeAgo(share.visits.last_at) : "—"}</dd>
        </div>
      </dl>

      {error && (
        <div className="mt-4">
          <ErrorNote message={error} />
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        {share.published_at && (
          <button type="button" className="text-accent hover:underline" onClick={toggleVisits} aria-expanded={open}>
            {open ? T.hideVisits : T.showVisits}
          </button>
        )}
        {share.state !== "revoked" && share.state !== "uploading" && (
          <button
            type="button"
            disabled={busy}
            className="text-text-secondary hover:text-text-primary disabled:opacity-50"
            title={T.extendNote}
            onClick={() => act(() => extendShare(share.share_id, days))}
          >
            {T.extend} ({days} days)
          </button>
        )}
        {open_ &&
          (confirming ? (
            <span className="inline-flex gap-3">
              <button
                type="button"
                disabled={busy}
                className="text-red-400 hover:underline disabled:opacity-50"
                onClick={() => act(() => revokeShare(share.share_id))}
              >
                {T.confirmRevoke}
              </button>
              <button type="button" className="text-text-muted hover:underline" onClick={() => setConfirming(false)}>
                {T.cancel}
              </button>
            </span>
          ) : (
            <button type="button" className="text-text-muted hover:text-red-400" onClick={() => setConfirming(true)}>
              {T.revoke}
            </button>
          ))}
      </div>

      {open && (
        <div className="mt-6">
          <h3 className="mb-4 text-sm font-semibold">{T.byDay}</h3>
          {!detail ? (
            <p className="text-sm text-text-muted">Loading…</p>
          ) : detail.visits.total === 0 ? (
            <p className="text-sm text-text-muted">{T.noVisits}</p>
          ) : (
            <UsageChart data={fillDays(detail.visits.by_day ?? [])} noun="visits" summary={T.byDay} />
          )}
        </div>
      )}
    </Panel>
  );
}
