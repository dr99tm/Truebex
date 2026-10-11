"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, Copy, RefreshCw, Send, Webhook } from "lucide-react";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { useApiData } from "@/components/dashboard/useApiData";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/lib/api";
import { DEVELOPER_DOCS } from "@/lib/constants";
import { timeAgo } from "@/lib/time";
import { cn } from "@/lib/utils";
import {
  createWebhook,
  deleteWebhook,
  listDeliveries,
  listWebhooks,
  resendDelivery,
  revealSecret,
  rotateSecret,
  sendTest,
  updateWebhook,
  type WebhookDelivery,
  type WebhookEndpoint,
} from "@/lib/webhooks";

const T = DEVELOPER_DOCS.webhooksDashboard;

export default function WebhooksPage() {
  const hooks = useApiData(listWebhooks);
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [events, setEvents] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fresh, setFresh] = useState<WebhookEndpoint | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setFresh(await createWebhook(url.trim(), events, description.trim()));
      setUrl("");
      setDescription("");
      setEvents([]);
      await hooks.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const all = hooks.data?.events ?? [];
  const descriptions = hooks.data?.descriptions ?? {};
  return (
    <>
      <PageHeader title={T.title} description={T.description} />
      {fresh?.secret && <SecretPanel title={`${T.secretTitle}: ${fresh.url}`} secret={fresh.secret} note={T.secretShownOnce} />}

      <Panel className="mb-6">
        <form onSubmit={handleCreate} className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row">
            <label className="sr-only" htmlFor="hook-url">
              {T.urlLabel}
            </label>
            <input
              id="hook-url"
              type="url"
              required
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder={T.urlPlaceholder}
              className="min-w-0 flex-1 rounded-[var(--radius-button)] border border-border bg-background px-4 py-2.5 text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50"
            />
            <label className="sr-only" htmlFor="hook-description">
              {T.descriptionLabel}
            </label>
            <input
              id="hook-description"
              value={description}
              maxLength={200}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={T.descriptionLabel}
              className="min-w-0 rounded-[var(--radius-button)] border border-border bg-background px-4 py-2.5 text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50 sm:w-56"
            />
          </div>
          <fieldset>
            <legend className="text-sm font-medium text-text-primary">{T.eventsLabel}</legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {all.map((ev) => (
                <label key={ev} className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="mt-1 accent-[var(--color-accent)]"
                    checked={events.includes(ev)}
                    onChange={() => setEvents(events.includes(ev) ? events.filter((x) => x !== ev) : [...events, ev])}
                  />
                  <span>
                    <code className="font-mono text-text-primary">{ev}</code>
                    <span className="block text-xs text-text-muted">{descriptions[ev]}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          <Button type="submit" disabled={busy || events.length === 0 || !url.trim()}>
            <Webhook size={16} aria-hidden />
            <span className="ml-2">{busy ? T.creating : T.create}</span>
          </Button>
        </form>
        {(error || hooks.error) && (
          <div className="mt-4">
            <ErrorNote message={error || hooks.error || ""} />
          </div>
        )}
        <p className="mt-4 text-sm">
          <Link className="text-accent hover:underline" href="/developers/webhooks/#verify">
            {T.docs}
          </Link>
        </p>
      </Panel>

      {hooks.loading && !hooks.data ? (
        <p className="text-sm text-text-muted">Loading…</p>
      ) : (hooks.data?.endpoints.length ?? 0) === 0 ? (
        <Panel>
          <p className="text-sm text-text-muted">{T.empty}</p>
        </Panel>
      ) : (
        <ul className="space-y-4">
          {hooks.data!.endpoints.map((ep) => (
            <li key={ep.endpoint_id}>
              <EndpointCard endpoint={ep} onChange={hooks.reload} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function SecretPanel({ title, secret, note }: { title: string; secret: string; note: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Panel className="mb-6 border-accent/40">
      <p className="break-all font-semibold">{title}</p>
      <p className="mt-1 text-sm text-warn">{note}</p>
      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <code className="min-w-0 flex-1 break-all rounded-[var(--radius-button)] border border-border bg-background px-3 py-2.5 font-mono text-sm text-text-primary">
          {secret}
        </code>
        <Button
          size="md"
          variant="secondary"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(secret);
              setCopied(true);
            } catch {
              setCopied(false);
            }
          }}
        >
          {copied ? <Check size={16} aria-hidden /> : <Copy size={16} aria-hidden />}
          <span className="ml-2">{copied ? T.copied : T.copy}</span>
        </Button>
      </div>
    </Panel>
  );
}

function EndpointCard({ endpoint: ep, onChange }: { endpoint: WebhookEndpoint; onChange: () => Promise<void> }) {
  const [secret, setSecret] = useState<string | null>(null);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[] | null>(null);
  const [confirm, setConfirm] = useState<"rotate" | "remove" | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  async function act(fn: () => Promise<unknown>, after?: string) {
    setBusy(true);
    setError("");
    setNote("");
    try {
      await fn();
      setConfirm(null);
      if (after) setNote(after);
      await onChange();
      if (deliveries) setDeliveries((await listDeliveries(ep.endpoint_id)).deliveries);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleDeliveries() {
    if (deliveries) return setDeliveries(null);
    try {
      setDeliveries((await listDeliveries(ep.endpoint_id)).deliveries);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  const state = ep.active ? T.active : ep.disabled_reason === "failing" ? T.disabledFailing : T.disabledOwner;
  const link = "text-text-secondary hover:text-text-primary disabled:opacity-50";
  return (
    <Panel className={cn(!ep.active && "opacity-80")}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="break-all font-mono text-sm font-semibold text-text-primary">{ep.url}</h2>
          <p className="mt-1 text-sm text-text-muted">
            <span
              className={cn(
                "mr-2 inline-block rounded-full px-2 py-0.5 text-xs",
                ep.active ? "bg-accent/10 text-accent" : "bg-white/5 text-text-secondary",
              )}
            >
              {state}
            </span>
            {ep.description}
            {ep.failing_since ? ` · ${T.failingSince} ${formatDate(ep.failing_since)}` : ""}
          </p>
          <p className="mt-2 flex flex-wrap gap-1">
            {ep.events.map((ev) => (
              <code key={ev} className="rounded bg-surface-elevated px-1.5 py-0.5 font-mono text-xs text-text-secondary">
                {ev}
              </code>
            ))}
          </p>
        </div>
      </div>

      {secret && <SecretPanel title={T.secretTitle} secret={secret} note={T.secretShownOnce} />}
      {note && <p className="mt-3 text-sm text-accent">{note}</p>}
      {error && (
        <div className="mt-3">
          <ErrorNote message={error} />
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        <button type="button" className="text-accent hover:underline" onClick={toggleDeliveries} aria-expanded={!!deliveries}>
          {T.deliveries}
        </button>
        {secret ? (
          <button type="button" className={link} onClick={() => setSecret(null)}>
            {T.hide}
          </button>
        ) : (
          <button type="button" className={link} disabled={busy} onClick={() => act(async () => setSecret((await revealSecret(ep.endpoint_id)).secret))}>
            {T.reveal}
          </button>
        )}
        {ep.active && (
          <button type="button" className={cn(link, "inline-flex items-center gap-1")} disabled={busy} onClick={() => act(() => sendTest(ep.endpoint_id), T.testQueued)}>
            <Send size={14} aria-hidden />
            {T.test}
          </button>
        )}
        <button
          type="button"
          className={link}
          disabled={busy}
          onClick={() => act(() => updateWebhook(ep.endpoint_id, { active: !ep.active }))}
        >
          {ep.active ? T.off : T.on}
        </button>
        {confirm === "rotate" ? (
          <span className="inline-flex flex-wrap gap-3">
            <span className="text-text-muted">{T.confirmRotate}</span>
            <button
              type="button"
              className="text-red-400 hover:underline"
              disabled={busy}
              onClick={() => act(async () => setSecret((await rotateSecret(ep.endpoint_id)).secret))}
            >
              {T.rotate}
            </button>
            <button type="button" className="text-text-muted hover:underline" onClick={() => setConfirm(null)}>
              {T.cancel}
            </button>
          </span>
        ) : (
          <button type="button" className={cn(link, "inline-flex items-center gap-1")} onClick={() => setConfirm("rotate")}>
            <RefreshCw size={14} aria-hidden />
            {T.rotate}
          </button>
        )}
        {confirm === "remove" ? (
          <span className="inline-flex flex-wrap gap-3">
            <span className="text-text-muted">{T.confirmRemove}</span>
            <button type="button" className="text-red-400 hover:underline" disabled={busy} onClick={() => act(() => deleteWebhook(ep.endpoint_id))}>
              {T.remove}
            </button>
            <button type="button" className="text-text-muted hover:underline" onClick={() => setConfirm(null)}>
              {T.cancel}
            </button>
          </span>
        ) : (
          <button type="button" className="text-text-muted hover:text-red-400" onClick={() => setConfirm("remove")}>
            {T.remove}
          </button>
        )}
      </div>

      {deliveries && (
        <div className="mt-5 overflow-x-auto">
          {deliveries.length === 0 ? (
            <p className="text-sm text-text-muted">{T.noDeliveries}</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-left text-text-muted">
                <tr>
                  <th className="py-2 pr-4 font-medium">{T.event}</th>
                  <th className="py-2 pr-4 font-medium">{T.attempt}</th>
                  <th className="py-2 pr-4 font-medium">{T.status}</th>
                  <th className="py-2 pr-4 font-medium">{T.code}</th>
                  <th className="py-2 pr-4 font-medium">{T.time}</th>
                  <th className="py-2 font-medium">
                    <span className="sr-only">{T.resend}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {deliveries.map((d) => (
                  <tr key={d.delivery_id} className="border-t border-border">
                    <td className="py-2 pr-4 font-mono text-xs text-text-primary">{d.event_type}</td>
                    <td className="py-2 pr-4 text-text-secondary">{d.attempt}</td>
                    <td
                      className={cn(
                        "py-2 pr-4",
                        d.status === "succeeded" ? "text-accent" : d.status === "failed" ? "text-red-400" : "text-text-secondary",
                      )}
                      title={d.error ?? undefined}
                    >
                      {d.status}
                    </td>
                    <td className="py-2 pr-4 text-text-secondary">{d.response_code ?? "—"}</td>
                    <td className="py-2 pr-4 text-text-secondary">{timeAgo(d.created_at)}</td>
                    <td className="py-2 text-right">
                      {d.status !== "pending" && ep.active && (
                        <button
                          type="button"
                          className="text-text-muted hover:text-text-primary"
                          disabled={busy}
                          onClick={() => act(() => resendDelivery(ep.endpoint_id, d.delivery_id))}
                        >
                          {T.resend}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </Panel>
  );
}
