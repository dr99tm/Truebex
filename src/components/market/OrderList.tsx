"use client";

import Link from "next/link";
import { Panel } from "@/components/dashboard/DashboardShell";
import { OrderSummary, StateChip } from "@/components/market/OrderSummary";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/lib/api";
import { MARKET, MARKET_ORDER_LINK } from "@/lib/constants";
import type { MarketOrder } from "@/lib/market";
import type { OrderLinkView } from "@/lib/order-link";
import { cn } from "@/lib/utils";

const O = MARKET.orders;

export type OrderAction = "accept" | "cancel";

/** The buyer's orders and requests (5.8) as /dashboard/orders/ lists them;
 *  PF7e: the order a link names (?order=<id>) first and highlighted. */
export function OrderList({
  view,
  busy,
  onAct,
}: {
  view: OrderLinkView;
  busy: string | null;
  onAct: (order: MarketOrder, action: OrderAction) => void;
}) {
  return (
    <>
      {view.note && (
        <div className="mb-6">
          <Panel>
            <p className="text-sm text-text-secondary" role="status">
              {MARKET_ORDER_LINK.notFound}
            </p>
          </Panel>
        </div>
      )}
      <div className="space-y-6">
        {view.orders.map((order) => (
          <OrderCard
            key={order.order_id}
            order={order}
            focused={order.order_id === view.focused}
            busy={busy === order.order_id}
            onAct={onAct}
          />
        ))}
      </div>
    </>
  );
}

function OrderCard({
  order,
  focused,
  busy,
  onAct,
}: {
  order: MarketOrder;
  focused: boolean;
  busy: boolean;
  onAct: (order: MarketOrder, action: OrderAction) => void;
}) {
  const cancellable =
    (order.kind === "quote" && (order.state === "submitted" || order.state === "quoted")) ||
    (order.kind === "order" &&
      (order.state === "awaiting_payment" || order.state === "paid") &&
      order.suppliers.every((s) => s.state === "pending"));
  return (
    <div
      id={`order-${order.order_id}`}
      data-order={order.order_id}
      data-focused={focused ? "true" : undefined}
      aria-current={focused ? "true" : undefined}
      className={cn("scroll-mt-24", focused && "rounded-[var(--radius-card)] ring-2 ring-accent")}
    >
      <Panel>
        {focused && <p className="mb-2 text-xs font-medium text-accent">{MARKET_ORDER_LINK.linked}</p>}
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm text-text-muted">
              {order.kind === "quote" ? O.quote : O.order} · {formatDate(order.created_at)}
              {order.project?.name ? ` · ${O.project}: ${order.project.name}` : ""}
            </p>
            <p className="mt-1 font-mono text-xs text-text-muted">{order.order_id}</p>
          </div>
          <StateChip state={order.state} />
        </div>
        <OrderSummary order={order} />
        {order.kind === "quote" && order.expires_at && (order.state === "submitted" || order.state === "quoted") && (
          <p className="mt-3 text-xs text-text-muted">
            {O.expires} {formatDate(order.expires_at)}
          </p>
        )}
        {order.payment === "offline" && <p className="mt-3 text-sm text-text-secondary">{O.paidOffline}</p>}
        {order.quote_id && <p className="mt-1 text-xs text-text-muted">{O.fromQuote}</p>}
        <div className="mt-5 flex flex-wrap gap-3">
          {order.state === "awaiting_payment" && (
            <Button href={`/market/checkout/?order=${order.order_id}`}>{O.pay}</Button>
          )}
          {order.kind === "quote" && order.state === "quoted" && (
            <Button onClick={() => onAct(order, "accept")} disabled={busy}>
              {O.accept}
            </Button>
          )}
          {cancellable && (
            <Button variant="secondary" onClick={() => onAct(order, "cancel")} disabled={busy}>
              {O.cancel}
            </Button>
          )}
          {order.order_ref && (
            <Link href={`/market/checkout/?order=${order.order_ref}`} className="self-center text-sm text-accent hover:underline">
              {O.order} {order.order_ref.slice(0, 8)}
            </Link>
          )}
        </div>
      </Panel>
    </div>
  );
}
