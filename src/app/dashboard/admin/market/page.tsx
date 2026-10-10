"use client";

import { useCallback, useEffect, useState } from "react";
import { ErrorNote, PageHeader, Panel, useDashboardUser } from "@/components/dashboard/DashboardShell";
import { OrderSummary, StateChip } from "@/components/market/OrderSummary";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/lib/api";
import { MARKET } from "@/lib/constants";
import {
  adminMarket,
  type SupplierApplication,
  formatMoney,
  type AdminProduct,
  type AdminReview,
  type AdminSupplier,
  type Commission,
  type FeedReport,
  type MarketOrder,
  type MarketSummary,
  type Statement,
} from "@/lib/market";
import { cn } from "@/lib/utils";

const A = MARKET.admin;
type Tab = keyof typeof A.tabs;

/** Load on mount and whenever `key` changes; `reload` re-runs it. */
function useLoad<T>(loader: () => Promise<T>, key: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const run = useCallback(async () => {
    try {
      setData(await loader());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
    // `key` stands for the loader's inputs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  useEffect(() => {
    void run();
  }, [run]);
  return { data, error, reload: run };
}

/** Run an admin action, then reload; errors show above the list. */
function useAction(reload: () => Promise<void>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };
  return { busy, error, act };
}

function Filter({ value, options, onChange }: { value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <div className="mb-4 flex flex-wrap gap-2">
      {options.map((o) => (
        <button
          key={o}
          type="button"
          onClick={() => onChange(o)}
          className={cn(
            "rounded-full border px-3 py-1 text-xs",
            o === value ? "border-accent bg-accent/10 text-accent" : "border-border text-text-secondary hover:text-text-primary"
          )}
        >
          {A.statuses[o] ?? MARKET.states[o] ?? o}
        </button>
      ))}
    </div>
  );
}

// --- Suppliers ---------------------------------------------------------------

/** PF8: what the supplier sent when it applied, and its documents. */
function ApplicationView({ app }: { app: SupplierApplication }) {
  const f = app.fields;
  if (!app.state) return <p className="mt-3 text-xs text-text-muted">{A.applicationNone}</p>;
  const address = f.address ? [f.address.line1, f.address.line2, f.address.city, f.address.postcode, f.address.country].filter(Boolean).join(", ") : "—";
  return (
    <div className="mt-3 space-y-2 rounded-[var(--radius-button)] border border-border p-3 text-xs text-text-secondary">
      <p>
        {f.legal_name} · {f.company_number}
        {f.vat_id ? ` · VAT ${f.vat_id}` : ""} · {address}
      </p>
      <p>
        {f.contact?.name} · {f.contact?.email}
        {f.contact?.phone ? ` · ${f.contact.phone}` : ""} · {(f.regions ?? []).join(", ")}
        {app.created_at ? ` · ${formatDate(app.created_at)}` : ""}
      </p>
      <p className="font-semibold text-text-primary">{A.documents}</p>
      {app.documents.length === 0 && <p>{A.noDocuments}</p>}
      <ul>
        {app.documents.map((d) => (
          <li key={d.sha256}>
            <a href={d.url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
              {d.name}
            </a>{" "}
            · {Math.ceil(d.bytes / 1024)} KB
          </li>
        ))}
      </ul>
    </div>
  );
}

function SupplierRow({ s, act, busy }: { s: AdminSupplier; act: (fn: () => Promise<unknown>) => Promise<void>; busy: boolean }) {
  const [bp, setBp] = useState(String(s.commission_bp));
  const [link, setLink] = useState("");
  const [app, setApp] = useState<SupplierApplication | null>(null);
  return (
    <Panel>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-text-primary">{s.name}</p>
          <p className="text-sm text-text-muted">
            {s.legal_name ?? "—"} · {s.country} · {s.regions.join(", ") || "—"} · {s.website ?? "—"}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {Object.entries(s.products).map(([k, v]) => `${A.statuses[k] ?? k}: ${v}`).join(" · ") || "0"} ·{" "}
            {s.members.map((m) => `${m.email} (${m.role})`).join(", ") || "—"}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {s.orderable ? "orders + quotes" : "quotes only"} · {s.connect_account_id ?? "no payout account"}
            {s.connect_account_id && !s.connect_ready ? " (onboarding)" : ""}
          </p>
        </div>
        <StateChip state={s.status === "verified" ? "accepted" : s.status === "suspended" ? "cancelled" : "pending"} />
      </div>
      <div className="mt-4 flex flex-wrap items-end gap-3">
        {s.status !== "verified" && (
          <Button size="sm" disabled={busy} onClick={() => act(() => adminMarket.editSupplier(s.supplier_id, { status: "verified" }))}>
            {s.status === "suspended" ? A.reinstate : A.verify}
          </Button>
        )}
        {s.status !== "suspended" && (
          <Button
            size="sm"
            variant="secondary"
            disabled={busy}
            onClick={() => {
              const reason = window.prompt(A.reason);
              if (reason) void act(() => adminMarket.editSupplier(s.supplier_id, { status: "suspended", reason }));
            }}
          >
            {A.suspend}
          </Button>
        )}
        <label className="text-xs text-text-muted">
          {A.commission}
          <input
            value={bp}
            onChange={(e) => setBp(e.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            className="ml-2 w-20 rounded border border-border bg-background px-2 py-1 text-sm text-text-primary"
          />
        </label>
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => act(() => adminMarket.editSupplier(s.supplier_id, { commission_bp: Number(bp) }))}>
          {A.save}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={busy}
          onClick={() => act(async () => setLink((await adminMarket.connectLink(s.supplier_id)).url))}
        >
          {A.connect}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={busy}
          onClick={() => act(async () => setApp(app ? null : await adminMarket.application(s.supplier_id)))}
        >
          {A.application}
        </Button>
      </div>
      {link && <p className="mt-2 break-all font-mono text-xs text-accent">{link}</p>}
      {app && <ApplicationView app={app} />}
    </Panel>
  );
}

function Suppliers() {
  const { data, error, reload } = useLoad(adminMarket.suppliers, "suppliers");
  const { busy, error: actError, act } = useAction(reload);
  return (
    <div className="space-y-4">
      {(error || actError) && <ErrorNote message={actError || error} />}
      {data?.suppliers.length === 0 && <p className="text-text-muted">{A.empty}</p>}
      {data?.suppliers.map((s) => <SupplierRow key={s.supplier_id} s={s} act={act} busy={busy} />)}
    </div>
  );
}

// --- Products (the review queue) ----------------------------------------------

function ProductCard({ p, act, busy }: { p: AdminProduct; act: (fn: () => Promise<unknown>) => Promise<void>; busy: boolean }) {
  const ask = (fn: (reason: string) => Promise<unknown>) => {
    const reason = window.prompt(A.reason);
    if (reason) void act(() => fn(reason));
  };
  return (
    <Panel>
      <div className="flex flex-wrap gap-4">
        {p.thumbnail_url && (
          // eslint-disable-next-line @next/next/no-img-element -- API-served thumbnail, static export
          <img src={p.thumbnail_url} alt={p.name} width={120} height={120} className="h-28 w-28 rounded object-cover" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold text-text-primary">
              {p.name} <span className="text-sm font-normal text-text-muted">· {p.sku}</span>
            </p>
            <span className="text-xs text-text-muted">{A.statuses[p.status] ?? p.status}</span>
          </div>
          <p className="text-sm text-text-muted">
            {p.supplier_name} ({p.supplier_status}) · {p.kind} · {p.category}
            {p.app_path ? ` → ${p.app_path}` : ""} {p.category_known ? "✓" : "✗"}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {p.variants
              .map((v) => `${v.variant_id}${v.dims_mm ? ` ${v.dims_mm.join("×")} mm` : ""}${v.geometry ? ` · ${v.geometry.format}` : ""}`)
              .join(" | ")}
          </p>
          {p.review_note && <p className="mt-1 text-xs text-warn">{p.review_note}</p>}
          <div className="mt-3 flex flex-wrap gap-2">
            {p.status !== "approved" && (
              <Button size="sm" disabled={busy} onClick={() => act(() => adminMarket.approve(p.product_id))}>
                {A.approve}
              </Button>
            )}
            {p.status === "pending_review" && (
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => ask((r) => adminMarket.reject(p.product_id, r))}>
                {A.reject}
              </Button>
            )}
            {p.status === "approved" && (
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => ask((r) => adminMarket.withdraw(p.product_id, r))}>
                {A.withdraw}
              </Button>
            )}
          </div>
        </div>
      </div>
    </Panel>
  );
}

function Products() {
  const [status, setStatus] = useState("pending_review");
  const { data, error, reload } = useLoad(() => adminMarket.products(status), status);
  const { busy, error: actError, act } = useAction(reload);
  return (
    <>
      <Filter value={status} options={["pending_review", "approved", "rejected", "withdrawn", "hidden", "all"]} onChange={setStatus} />
      <div className="space-y-4">
        {(error || actError) && <ErrorNote message={actError || error} />}
        {data?.products.length === 0 && <p className="text-text-muted">{A.empty}</p>}
        {data?.products.map((p) => <ProductCard key={p.product_id} p={p} act={act} busy={busy} />)}
      </div>
    </>
  );
}

// --- Reviews --------------------------------------------------------------------

function Reviews() {
  const [status, setStatus] = useState("pending");
  const { data, error, reload } = useLoad(() => adminMarket.reviews(status), status);
  const { busy, error: actError, act } = useAction(reload);
  return (
    <>
      <Filter value={status} options={["pending", "published", "hidden", "all"]} onChange={setStatus} />
      <div className="space-y-3">
        {(error || actError) && <ErrorNote message={actError || error} />}
        {data?.reviews.length === 0 && <p className="text-text-muted">{A.empty}</p>}
        {data?.reviews.map((r: AdminReview) => (
          <Panel key={r.review_id}>
            <p className="text-sm text-text-muted">
              {r.product_name} · {"★".repeat(r.rating)}
              {"☆".repeat(5 - r.rating)} · {r.author} · {formatDate(r.created_at)} · {r.status}
            </p>
            {r.text && <p className="mt-2 text-text-primary">{r.text}</p>}
            <div className="mt-3 flex gap-2">
              {r.status !== "published" && (
                <Button size="sm" disabled={busy} onClick={() => act(() => adminMarket.publishReview(r.review_id))}>
                  {A.publish}
                </Button>
              )}
              {r.status !== "hidden" && (
                <Button size="sm" variant="secondary" disabled={busy} onClick={() => act(() => adminMarket.hideReview(r.review_id))}>
                  {A.hide}
                </Button>
              )}
            </div>
          </Panel>
        ))}
      </div>
    </>
  );
}

// --- Orders (acting for a supplier until the supplier portal exists) --------------

function QuoteForm({ order, supplierId, act, busy }: { order: MarketOrder; supplierId: string; act: (fn: () => Promise<unknown>) => Promise<void>; busy: boolean }) {
  const lines = order.lines.filter((l) => l.supplier_id === supplierId);
  const group = order.suppliers.find((s) => s.supplier_id === supplierId);
  const [units, setUnits] = useState(lines.map((l) => String((l.quoted_price ?? l.price).amount)));
  const [fee, setFee] = useState(String(group?.delivery.amount ?? 0));
  const submit = () =>
    act(() =>
      adminMarket.quoteFor(order.order_id, supplierId, {
        lines: lines.map((l, i) => ({ sku: l.sku, variant_id: l.variant_id, unit_amount: Number(units[i] || 0) })),
        delivery_fee: Number(fee || 0),
      })
    );
  const input = "w-28 rounded border border-border bg-background px-2 py-1 text-sm text-text-primary";
  return (
    <div className="mt-2 space-y-2 rounded border border-border p-3 text-xs text-text-muted">
      {lines.map((l, i) => (
        <label key={l.sku + l.variant_id} className="flex flex-wrap items-center gap-2">
          {l.name} · {l.variant_id} — {A.unitPrice}
          <input className={input} inputMode="numeric" value={units[i]} onChange={(e) => setUnits(units.map((u, j) => (j === i ? e.target.value.replace(/\D/g, "") : u)))} />
        </label>
      ))}
      <label className="flex flex-wrap items-center gap-2">
        {A.deliveryFee}
        <input className={input} inputMode="numeric" value={fee} onChange={(e) => setFee(e.target.value.replace(/\D/g, ""))} />
      </label>
      <Button size="sm" disabled={busy} onClick={submit}>
        {A.quoteFor}
      </Button>
    </div>
  );
}

function Orders() {
  const { data, error, reload } = useLoad(adminMarket.orders, "orders");
  const { busy, error: actError, act } = useAction(reload);
  const [quoting, setQuoting] = useState<string | null>(null);
  const actions: Record<string, string[]> = {
    pending: ["accept", "reject"],
    accepted: ["ship", "deliver"],
    shipped: ["deliver"],
    submitted: ["decline"],
    quoted: ["decline"],
  };
  return (
    <div className="space-y-4">
      {(error || actError) && <ErrorNote message={actError || error} />}
      {data?.orders.length === 0 && <p className="text-text-muted">{A.empty}</p>}
      {data?.orders.map((o) => (
        <Panel key={o.order_id}>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-text-muted">
              {o.kind === "quote" ? MARKET.orders.quote : MARKET.orders.order} · {o.region} · {formatDate(o.created_at)} ·{" "}
              {o.contact?.name} ({o.contact?.email}) · <span className="font-mono">{o.order_id.slice(0, 8)}</span>
            </p>
            <StateChip state={o.state} />
          </div>
          <OrderSummary order={o} />
          {o.suppliers.map((s) => {
            const can = (o.kind === "order" && o.state === "awaiting_payment" ? [] : actions[s.state] ?? []).filter((a) =>
              o.kind === "quote" ? a === "decline" : a !== "decline"
            );
            const quotable = o.kind === "quote" && (s.state === "submitted" || s.state === "quoted");
            if (!can.length && !quotable) return null;
            return (
              <div key={s.supplier_id} className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                <span className="text-text-muted">{s.supplier_name}:</span>
                {quotable && (
                  <Button size="sm" variant="secondary" onClick={() => setQuoting(quoting === o.order_id + s.supplier_id ? null : o.order_id + s.supplier_id)}>
                    {A.quoteFor}
                  </Button>
                )}
                {can.map((a) => (
                  <Button
                    key={a}
                    size="sm"
                    variant="ghost"
                    disabled={busy}
                    onClick={() => {
                      const reason = a === "reject" || a === "decline" ? window.prompt(A.reason) ?? undefined : undefined;
                      if ((a === "reject" || a === "decline") && !reason) return;
                      void act(() => adminMarket.actFor(o.order_id, s.supplier_id, a, reason));
                    }}
                  >
                    {a}
                  </Button>
                ))}
                {quoting === o.order_id + s.supplier_id && <QuoteForm order={o} supplierId={s.supplier_id} act={act} busy={busy} />}
              </div>
            );
          })}
        </Panel>
      ))}
    </div>
  );
}

// --- Commissions and feeds -----------------------------------------------------------

function Commissions() {
  const { data, error, reload } = useLoad(adminMarket.commissions, "commissions");
  const { busy, error: actError, act } = useAction(reload);
  const cell = "px-2 py-1.5 text-left";
  return (
    <div className="space-y-6">
      {(error || actError) && <ErrorNote message={actError || error} />}
      <Button size="sm" disabled={busy} onClick={() => act(adminMarket.makeStatements)}>
        {A.makeStatements}
      </Button>
      <Panel>
        <table className="w-full text-sm">
          <tbody>
            {data?.statements.map((s: Statement) => (
              <tr key={s.statement_id} className="border-b border-border">
                <td className={cell}>{s.month}</td>
                <td className={cell}>{s.supplier_name}</td>
                <td className={cell}>{s.orders}</td>
                <td className={cell}>{formatMoney(s.commission)}</td>
                <td className={cell}>{formatMoney(s.listing_fee)}</td>
                <td className={cell}>{formatMoney(s.total)}</td>
                <td className={cell}>{s.state}{s.invoice_ref ? ` · ${s.invoice_ref}` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data?.statements.length === 0 && <p className="text-text-muted">{A.empty}</p>}
      </Panel>
      <Panel>
        <table className="w-full text-sm">
          <tbody>
            {data?.commissions.map((c: Commission) => (
              <tr key={c.order_id + c.supplier_name} className="border-b border-border">
                <td className={cell}>{formatDate(c.created_at)}</td>
                <td className={cell}>{c.supplier_name}</td>
                <td className={cell}>{(c.rate_bp / 100).toFixed(2)} %</td>
                <td className={cell}>{formatMoney(c.base)}</td>
                <td className={cell}>{formatMoney(c.amount)}</td>
                <td className={cell}>{c.state}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data?.commissions.length === 0 && <p className="text-text-muted">{A.empty}</p>}
      </Panel>
    </div>
  );
}

function Feeds() {
  const { data, error } = useLoad(adminMarket.feeds, "feeds");
  return (
    <div className="space-y-3">
      {error && <ErrorNote message={error} />}
      {data?.feeds.length === 0 && <p className="text-text-muted">{A.empty}</p>}
      {data?.feeds.map((f: FeedReport) => (
        <Panel key={f.feed_id}>
          <p className="text-sm text-text-primary">
            {f.supplier_name} · {f.format} {f.mode} · {f.source} · {formatDate(f.created_at)} · <strong>{f.state}</strong>
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {f.rows} rows · {f.created} created · {f.updated} updated · {f.unchanged} unchanged · {f.rejected} rejected · {f.hidden} hidden
            {f.detail ? ` · ${f.detail}` : ""}
          </p>
          {f.errors.length > 0 && (
            <ul className="mt-2 space-y-0.5 font-mono text-xs text-red-300">
              {f.errors.slice(0, 10).map((e, i) => (
                <li key={i}>
                  row {e.row} · {e.column} · {e.code} · {e.value}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      ))}
    </div>
  );
}

const PANELS: Record<Tab, () => React.ReactElement> = {
  suppliers: Suppliers,
  products: Products,
  reviews: Reviews,
  orders: Orders,
  commissions: Commissions,
  feeds: Feeds,
};

export default function AdminMarketPage() {
  const user = useDashboardUser();
  const [tab, setTab] = useState<Tab>("products");
  const summary = useLoad<MarketSummary | null>(async () => (user.is_admin ? adminMarket.summary() : null), "summary");
  if (!user.is_admin) {
    return (
      <>
        <PageHeader title={A.title} />
        <ErrorNote message="Admins only." />
      </>
    );
  }
  const Current = PANELS[tab];
  const pending = summary.data?.products?.pending_review ?? 0;
  const applied = summary.data?.suppliers?.applied ?? 0;
  return (
    <>
      <PageHeader title={A.title} description={A.description} />
      {summary.data && (
        <p className="mb-4 text-sm text-text-muted">
          {!summary.data.payments_enabled ? A.paymentsOff : summary.data.stripe_ready ? A.paymentsOn : A.paymentsNoStripe}
        </p>
      )}
      <nav aria-label={A.title} className="mb-6 flex flex-wrap gap-1 border-b border-border">
        {(Object.keys(A.tabs) as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            aria-current={tab === t ? "page" : undefined}
            className={cn(
              "border-b-2 px-3 py-2 text-sm",
              tab === t ? "border-accent text-accent" : "border-transparent text-text-secondary hover:text-text-primary"
            )}
          >
            {A.tabs[t]}
            {t === "products" && pending > 0 && <span className="ml-1 text-xs text-warn">({pending})</span>}
            {/* PF8: supplier applications waiting for a decision. */}
            {t === "suppliers" && applied > 0 && <span className="ml-1 text-xs text-warn">({applied})</span>}
          </button>
        ))}
      </nav>
      <Current />
    </>
  );
}
