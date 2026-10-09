"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { Button } from "@/components/ui/Button";
import { Badge, Field, inputClass, useMember } from "@/components/supplier/SupplierShell";
import { formatDate } from "@/lib/api";
import { SUPPLIER } from "@/lib/constants";
import { formatMoney, supplierApi, toMajor, type InboxItem } from "@/lib/supplier";
import { cn } from "@/lib/utils";

const X = SUPPLIER.inbox;
const FILTERS = ["open", "quote", "order", "all"];

function stateTone(state: string): "good" | "warn" | "bad" | "neutral" {
  if (state === "submitted" || state === "pending") return "warn";
  if (state === "quoted" || state === "accepted" || state === "shipped" || state === "delivered") return "good";
  if (state === "declined" || state === "rejected" || state === "cancelled" || state === "expired") return "bad";
  return "neutral";
}

function QuoteForm({ item, onDone }: { item: InboxItem; onDone: (i: InboxItem) => void }) {
  const [prices, setPrices] = useState<Record<string, string>>(() =>
    Object.fromEntries(item.lines.map((l) => [`${l.sku}\u0000${l.variant_id}`, toMajor((l.quoted_unit ?? l.unit).amount, item.exponent)]))
  );
  const [fee, setFee] = useState(toMajor(item.delivery_fee.amount, item.exponent));
  const [days, setDays] = useState({ min: item.delivery_days.min?.toString() ?? "", max: item.delivery_days.max?.toString() ?? "" });
  const [valid, setValid] = useState("30");
  const [message, setMessage] = useState(item.quote?.message ?? "");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(fn: () => Promise<InboxItem>) {
    setBusy(true);
    setError("");
    try {
      onDone(await fn());
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
    } finally {
      setBusy(false);
    }
  }

  const int = (v: string) => (v.trim() === "" ? null : Number.parseInt(v, 10));
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        void run(() =>
          supplierApi.quote(item.order_id, {
            lines: item.lines.map((l) => ({ sku: l.sku, variant_id: l.variant_id, price: prices[`${l.sku}\u0000${l.variant_id}`] })),
            delivery_fee: fee,
            delivery_days_min: int(days.min),
            delivery_days_max: int(days.max),
            valid_days: int(valid) ?? 30,
            message: message || null,
          })
        );
      }}
    >
      <ul className="space-y-3">
        {item.lines.map((l) => {
          const k = `${l.sku}\u0000${l.variant_id}`;
          return (
            <li key={k} className="grid gap-2 sm:grid-cols-[1fr_10rem] sm:items-end">
              <div className="text-sm">
                <p className="text-text-primary">
                  {l.qty} × {l.name}
                </p>
                <p className="text-xs text-text-muted">
                  {l.sku} · {l.variant_id} · {X.listed} {formatMoney(l.unit)}
                </p>
              </div>
              <Field label={`${X.yourPrice} (${item.currency})`}>
                <input inputMode="decimal" required value={prices[k]} onChange={(e) => setPrices({ ...prices, [k]: e.target.value })} className={inputClass} />
              </Field>
            </li>
          );
        })}
      </ul>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label={`${X.deliveryFee} (${item.currency})`}>
          <input inputMode="decimal" value={fee} onChange={(e) => setFee(e.target.value)} className={inputClass} />
        </Field>
        <Field label={X.daysMin}>
          <input inputMode="numeric" value={days.min} onChange={(e) => setDays({ ...days, min: e.target.value })} className={inputClass} />
        </Field>
        <Field label={X.daysMax}>
          <input inputMode="numeric" value={days.max} onChange={(e) => setDays({ ...days, max: e.target.value })} className={inputClass} />
        </Field>
        <Field label={X.validDays}>
          <input inputMode="numeric" value={valid} onChange={(e) => setValid(e.target.value)} className={inputClass} />
        </Field>
      </div>
      <Field label={X.quoteMessage}>
        <textarea rows={3} maxLength={2000} value={message} onChange={(e) => setMessage(e.target.value)} className={inputClass} />
      </Field>
      {error && <ErrorNote message={error} />}
      <div className="flex flex-wrap items-end gap-3">
        <Button type="submit" disabled={busy}>
          {X.sendQuote}
        </Button>
        <input aria-label={X.reason} placeholder={X.reason} value={reason} onChange={(e) => setReason(e.target.value)} className={cn(inputClass, "w-full sm:w-64")} />
        <Button type="button" variant="ghost" disabled={busy} onClick={() => void run(() => supplierApi.inboxAction(item.order_id, "decline", reason || undefined))}>
          {X.decline}
        </Button>
      </div>
    </form>
  );
}

function OrderActions({ item, onDone }: { item: InboxItem; onDone: (i: InboxItem) => void }) {
  const [carrier, setCarrier] = useState("");
  const [reference, setReference] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(fn: () => Promise<InboxItem>) {
    setBusy(true);
    setError("");
    try {
      onDone(await fn());
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      {item.state === "pending" && (
        <div className="flex flex-wrap items-end gap-3">
          <Button disabled={busy} onClick={() => void run(() => supplierApi.inboxAction(item.order_id, "accept"))}>
            {X.accept}
          </Button>
          <input aria-label={X.reason} placeholder={X.reason} value={reason} onChange={(e) => setReason(e.target.value)} className={cn(inputClass, "w-full sm:w-64")} />
          <Button variant="ghost" disabled={busy} onClick={() => void run(() => supplierApi.inboxAction(item.order_id, "reject", reason || undefined))}>
            {X.reject}
          </Button>
        </div>
      )}
      {item.state === "accepted" && (
        <form
          className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
          onSubmit={(e) => {
            e.preventDefault();
            void run(() => supplierApi.ship(item.order_id, carrier, reference));
          }}
        >
          <Field label={X.carrier}>
            <input required maxLength={80} value={carrier} onChange={(e) => setCarrier(e.target.value)} className={inputClass} />
          </Field>
          <Field label={X.reference}>
            <input required maxLength={120} value={reference} onChange={(e) => setReference(e.target.value)} className={inputClass} />
          </Field>
          <Button type="submit" disabled={busy}>
            {X.ship}
          </Button>
        </form>
      )}
      {(item.state === "accepted" || item.state === "shipped") && (
        <Button variant={item.state === "shipped" ? "primary" : "secondary"} disabled={busy} onClick={() => void run(() => supplierApi.inboxAction(item.order_id, "deliver"))}>
          {X.deliver}
        </Button>
      )}
      {error && <ErrorNote message={error} />}
    </div>
  );
}

function Item({ item, expanded, onToggle, onChange }: { item: InboxItem; expanded: boolean; onToggle: () => void; onChange: (i: InboxItem) => void }) {
  const d = item.delivery;
  const where = [d.address, d.city, d.postcode, d.country].filter(Boolean).join(", ");
  return (
    <li className={cn("rounded-[var(--radius-card)] border bg-surface", item.open ? "border-accent/40" : "border-border")}>
      <button type="button" onClick={onToggle} aria-expanded={expanded} className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 p-4 text-left">
        <span className="font-mono text-xs text-text-muted">{item.ref}</span>
        <span className="font-semibold text-text-primary">{item.kind === "quote" ? X.request : X.order}</span>
        <Badge tone={stateTone(item.state)}>{X.states[item.state] ?? item.state}</Badge>
        <span className="w-full text-sm text-text-secondary sm:w-auto">
          {item.buyer.name ?? "—"} · {item.region} · {formatDate(item.created_at)}
        </span>
        <span className="ml-auto text-sm font-semibold tabular-nums text-text-primary">{formatMoney(item.total)}</span>
      </button>
      {expanded && (
        <div className="space-y-5 border-t border-border p-4">
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-text-muted">{X.buyer}</dt>
              <dd>
                {item.buyer.name}
                {item.buyer.email && (
                  <a href={`mailto:${item.buyer.email}`} className="block text-accent hover:underline">
                    {item.buyer.email}
                  </a>
                )}
                {item.buyer.phone && (
                  <a href={`tel:${item.buyer.phone}`} className="block text-accent hover:underline">
                    {item.buyer.phone}
                  </a>
                )}
              </dd>
            </div>
            <div>
              <dt className="text-text-muted">{X.deliveryTo}</dt>
              <dd>{where || item.region}</dd>
            </div>
            {item.project.name && (
              <div>
                <dt className="text-text-muted">{X.project}</dt>
                <dd>{item.project.name}</dd>
              </div>
            )}
            {item.buyer.message && (
              <div className="sm:col-span-2">
                <dt className="text-text-muted">{X.message}</dt>
                <dd className="whitespace-pre-wrap">{item.buyer.message}</dd>
              </div>
            )}
            <div>
              <dt className="text-text-muted">{X.total}</dt>
              <dd className="tabular-nums">
                {formatMoney(item.total)}
                {item.kind === "order" && <span className="ml-2 text-xs text-text-muted">{item.payment === "platform" ? X.paidOnTruebex : X.paidOffline}</span>}
              </dd>
            </div>
            {item.quote?.quoted_at && (
              <div>
                <dt className="text-text-muted">{X.quotedAt}</dt>
                <dd>
                  {formatDate(item.quote.quoted_at)}
                  {item.quote.valid_until && ` · ${X.validUntil} ${formatDate(item.quote.valid_until)}`}
                </dd>
              </div>
            )}
            {item.expires_at && (
              <div>
                <dt className="text-text-muted">{X.expires}</dt>
                <dd>{formatDate(item.expires_at)}</dd>
              </div>
            )}
            {item.shipment && (
              <div>
                <dt className="text-text-muted">{X.shippedWith}</dt>
                <dd>
                  {item.shipment.carrier} · {item.shipment.reference}
                </dd>
              </div>
            )}
          </dl>

          {!(item.kind === "quote" && item.state === "submitted") && (
            <ul className="space-y-1 text-sm">
              {item.lines.map((l) => (
                <li key={`${l.sku}-${l.variant_id}`} className="flex justify-between gap-3">
                  <span>
                    {l.qty} × {l.name} <span className="text-xs text-text-muted">({l.sku} · {l.variant_id})</span>
                  </span>
                  <span className="tabular-nums">{formatMoney(l.quoted_unit ?? l.unit)}</span>
                </li>
              ))}
            </ul>
          )}

          {item.kind === "quote" && (item.state === "submitted" || item.state === "quoted") && <QuoteForm item={item} onDone={onChange} />}
          {item.kind === "order" && <OrderActions item={item} onDone={onChange} />}
        </div>
      )}
    </li>
  );
}

function InboxInner() {
  useMember();
  const params = useSearchParams();
  const [filter, setFilter] = useState(params.get("order") ? "all" : "open");
  const [items, setItems] = useState<InboxItem[] | null>(null);
  const [counts, setCounts] = useState({ requests: 0, orders: 0 });
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<string | null>(params.get("order"));

  const load = useCallback(async (f: string) => {
    try {
      const res = await supplierApi.inbox(f);
      setItems(res.items);
      setCounts(res.open);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    supplierApi
      .inbox(filter)
      .then((res) => {
        if (cancelled) return;
        setItems(res.items);
        setCounts(res.open);
        setError("");
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
      });
    return () => {
      cancelled = true;
    };
  }, [filter]);

  return (
    <>
      <PageHeader title={X.title} description={X.description} />
      <div className="space-y-4">
        <div className="-mx-4 flex gap-2 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          {FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={cn(
                "whitespace-nowrap rounded-full border px-3 py-1 text-sm",
                f === filter ? "border-accent bg-accent/10 text-accent" : "border-border text-text-secondary"
              )}
            >
              {X.filters[f]}
              {f === "open" && counts.requests + counts.orders > 0 ? ` (${counts.requests + counts.orders})` : ""}
            </button>
          ))}
        </div>
        {error && <ErrorNote message={error} />}
        {items && items.length === 0 && (
          <Panel>
            <p className="text-text-secondary">{X.empty}</p>
          </Panel>
        )}
        <ul className="space-y-3">
          {items?.map((item) => (
            <Item
              key={item.order_id}
              item={item}
              expanded={expanded === item.order_id}
              onToggle={() => setExpanded(expanded === item.order_id ? null : item.order_id)}
              onChange={(next) => {
                setItems((all) => all?.map((i) => (i.order_id === next.order_id ? next : i)) ?? null);
                void load(filter);
              }}
            />
          ))}
        </ul>
      </div>
    </>
  );
}

export default function InboxPage() {
  return (
    <Suspense fallback={<p className="text-text-muted">…</p>}>
      <InboxInner />
    </Suspense>
  );
}
