"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { useApiData } from "@/components/dashboard/useApiData";
import { OrderList, type OrderAction } from "@/components/market/OrderList";
import { ApiError } from "@/lib/api";
import { MARKET } from "@/lib/constants";
import { acceptQuote, cancelOrder, getOrder, listOrders, type MarketOrder } from "@/lib/market";
import { linkedOrderToFetch, orderLinkView } from "@/lib/order-link";

const O = MARKET.orders;

// The buyer's orders and requests for quote (contract marketplace-api 5.8),
// each with its suppliers' states; pay, accept a quote or cancel. PF7e: an
// order's `web_url` opens this page with ?order=<id>, which shows that order
// first and highlighted (read on the client: the static export has one page).
export default function OrdersPage() {
  return (
    <Suspense fallback={null}>
      <LinkedOrders />
    </Suspense>
  );
}

// A new link starts afresh (its own 5.9 answer).
function LinkedOrders() {
  const link = useSearchParams().get("order");
  return <Orders key={link ?? ""} link={link} />;
}

function Orders({ link }: { link: string | null }) {
  const { data, error, loading, reload } = useApiData(listOrders);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");
  // 5.9's answer for a linked order that is not on 5.8's first page: undefined
  // while not asked, null when it is not this account's (404 / 403).
  const [fetched, setFetched] = useState<MarketOrder | null | undefined>(undefined);
  const toFetch = data ? linkedOrderToFetch(data.orders, link) : null;

  useEffect(() => {
    if (!toFetch) return;
    let cancelled = false;
    getOrder(toFetch).then(
      (order) => {
        if (!cancelled) setFetched(order);
      },
      (err) => {
        if (cancelled) return;
        if (err instanceof ApiError && (err.status === 404 || err.status === 403)) setFetched(null);
        else setActionError(err instanceof Error ? err.message : "Something went wrong.");
      }
    );
    return () => {
      cancelled = true;
    };
  }, [toFetch]);

  const view = orderLinkView(data?.orders ?? [], link, fetched);

  useEffect(() => {
    if (view.focused) document.getElementById(`order-${view.focused}`)?.scrollIntoView({ block: "start" });
  }, [view.focused]);

  async function act(order: MarketOrder, action: OrderAction) {
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
      // The linked order shown from 5.9 is not in the reloaded list: read it again.
      if (fetched && fetched.order_id === order.order_id) setFetched(await getOrder(order.order_id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <PageHeader title={O.title} description={O.description} />
      {(error || actionError) && (
        <div className="mb-6">
          <ErrorNote message={actionError || error || ""} />
        </div>
      )}
      {loading && !data && <p className="text-sm text-text-muted" role="status">…</p>}
      {data && view.orders.length === 0 && !view.note && (
        <Panel>
          <p className="text-text-secondary">{O.empty}</p>
        </Panel>
      )}
      <OrderList view={view} busy={busy} onAct={act} />
    </>
  );
}
