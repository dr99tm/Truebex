"use client";

import { MARKET } from "@/lib/constants";
import { formatMoney, type MarketOrder } from "@/lib/market";
import { cn } from "@/lib/utils";

const C = MARKET.checkout;

export function stateLabel(state: string): string {
  return MARKET.states[state] ?? state.replace(/_/g, " ");
}

export function StateChip({ state }: { state: string }) {
  const tone =
    state === "delivered" || state === "paid" || state === "accepted" || state === "quoted"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
      : state === "cancelled" || state === "rejected" || state === "declined" || state === "expired"
        ? "border-red-500/30 bg-red-500/10 text-red-300"
        : "border-warn/30 bg-warn/10 text-warn";
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium", tone)}>
      {stateLabel(state)}
    </span>
  );
}

/** An order (or a request for quote) per supplier: lines, delivery, tax and totals. */
export function OrderSummary({ order }: { order: MarketOrder }) {
  const inclusive = order.lines.every((l) => l.price.includes_tax);
  return (
    <div className="space-y-5">
      {order.suppliers.map((s) => {
        const lines = order.lines.filter((l) => l.supplier_id === s.supplier_id);
        const days =
          s.delivery_days.min != null && s.delivery_days.max != null
            ? C.deliveryDays.replace("{min}", String(s.delivery_days.min)).replace("{max}", String(s.delivery_days.max))
            : null;
        return (
          <section key={s.supplier_id} className="rounded-[var(--radius-card)] border border-border bg-background/40 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-semibold text-text-primary">{s.supplier_name ?? s.supplier_id}</h3>
              <StateChip state={s.state} />
            </div>
            <ul className="mt-3 divide-y divide-border">
              {lines.map((l) => {
                const unit = l.quoted_price ?? l.price;
                return (
                  <li key={`${l.sku}/${l.variant_id}`} className="flex flex-wrap justify-between gap-2 py-2 text-sm">
                    <span className="min-w-0 text-text-primary">
                      {l.name} <span className="text-text-muted">· {l.variant_id}</span>
                      <span className="block text-xs text-text-muted">
                        {C.qty} {l.qty} × {formatMoney(unit)} {C.each}
                        {l.quoted_price && l.quoted_price.amount !== l.price.amount && ` · ${C.quoted}`}
                      </span>
                    </span>
                    <span className="font-medium tabular-nums text-text-primary">{formatMoney(l.total)}</span>
                  </li>
                );
              })}
            </ul>
            <dl className="mt-2 space-y-1 border-t border-border pt-2 text-sm">
              <div className="flex justify-between text-text-secondary">
                <dt>
                  {C.delivery}
                  {days && <span className="ml-2 text-xs text-text-muted">{days}</span>}
                </dt>
                <dd className="tabular-nums">{formatMoney(s.delivery)}</dd>
              </div>
              <div className="flex justify-between text-text-muted">
                <dt>{inclusive ? C.taxIncluded : C.tax}</dt>
                <dd className="tabular-nums">{formatMoney(s.tax)}</dd>
              </div>
              <div className="flex justify-between font-medium text-text-primary">
                <dt>{C.total}</dt>
                <dd className="tabular-nums">{formatMoney(s.total)}</dd>
              </div>
            </dl>
            {s.quote?.message && <p className="mt-2 text-sm text-text-secondary">“{s.quote.message}”</p>}
          </section>
        );
      })}
      <div className="flex items-baseline justify-between border-t border-border pt-4">
        <span className="text-lg font-semibold text-text-primary">{C.total}</span>
        <span className="text-2xl font-bold tabular-nums text-text-primary" data-total={order.total.amount}>
          {formatMoney(order.total)}
        </span>
      </div>
    </div>
  );
}
