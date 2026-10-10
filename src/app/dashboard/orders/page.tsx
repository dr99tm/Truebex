"use client";

import { useState } from "react";
import Link from "next/link";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { useApiData } from "@/components/dashboard/useApiData";
import { OrderSummary, StateChip } from "@/components/market/OrderSummary";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/lib/api";
import { MARKET } from "@/lib/constants";
import { acceptQuote, cancelOrder, listOrders, type MarketOrder } from "@/lib/market";

const O = MARKET.orders;

// The buyer's orders and requests for quote (contract marketplace-api 5.8),
// each with its suppliers' states; pay, accept a quote or cancel.
export default function OrdersPage() {
  const { data, error, loading, reload } = useApiData(listOrders);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");

  async function act(order: MarketOrder, action: "accept" | "cancel") {
    if (action === "cancel" && !window.confirm(O.confirmCancel)) return;
    setBusy(order.order_id);
    setActionError("");
    try {
      if (action === "accept") {
        const made = await acceptQuote(order.order_id);
        if (made.state === "awaiting_payment") {
          window.location.href = `/market/checkout/?order=${made.order_id}`;
          return;
        }
      } else {
        await cancelOrder(order.order_id);
      }
      await reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  const orders = data?.orders ?? [];
  return (
    <>
      <PageHeader title={O.title} description={O.description} />
      {(error || actionError) && (
        <div className="mb-6">
          <ErrorNote message={actionError || error || ""} />
        </div>
      )}
      {loading && !data && <p className="text-sm text-text-muted" role="status">…</p>}
      {data && orders.length === 0 && (
        <Panel>
          <p className="text-text-secondary">{O.empty}</p>
        </Panel>
      )}
      <div className="space-y-6">
        {orders.map((order) => {
          const cancellable =
            (order.kind === "quote" && (order.state === "submitted" || order.state === "quoted")) ||
            (order.kind === "order" &&
              (order.state === "awaiting_payment" || order.state === "paid") &&
              order.suppliers.every((s) => s.state === "pending"));
          return (
            <Panel key={order.order_id}>
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
                  <Button onClick={() => act(order, "accept")} disabled={busy === order.order_id}>
                    {O.accept}
                  </Button>
                )}
                {cancellable && (
                  <Button variant="secondary" onClick={() => act(order, "cancel")} disabled={busy === order.order_id}>
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
          );
        })}
      </div>
    </>
  );
}
