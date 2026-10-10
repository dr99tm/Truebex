"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, Lock } from "lucide-react";
import { OrderSummary, StateChip } from "@/components/market/OrderSummary";
import { Button } from "@/components/ui/Button";
import { ApiError, getToken } from "@/lib/api";
import { MARKET } from "@/lib/constants";
import { getOrder, refreshOrderCheckout, startOrderCheckout, type MarketOrder } from "@/lib/market";

const C = MARKET.checkout;
const ORDER_ID = /^[0-9a-f]{32}$/;

// The platform's checkout page (contract marketplace-api 5.7 `checkout_url`):
// the app opens it with ?order=<id>; the person signs in with the account
// that sent the order, reviews it and pays on the provider's page, which
// sends them back here with &paid=1.
export function CheckoutPanel() {
  const params = useSearchParams();
  const orderId = params.get("order") ?? "";
  const returned = params.get("paid") === "1";
  const [order, setOrder] = useState<MarketOrder | null>(null);
  // Known before anything loads: a link without an order, or nobody signed in.
  const [state, setState] = useState<"loading" | "ready" | "signin" | "missing" | "error">(() =>
    !ORDER_ID.test(orderId) ? "missing" : !getToken() ? "signin" : "loading"
  );
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!ORDER_ID.test(orderId) || !getToken()) return;
    let cancelled = false;
    async function load() {
      try {
        let current = await getOrder(orderId);
        if (cancelled) return;
        setOrder(current);
        setState("ready");
        if (!returned || current.state !== "awaiting_payment") return;
        // Back from the payment page: the server asks the provider itself,
        // a few times while the payment settles.
        setNotice(C.confirming);
        for (let attempt = 0; attempt < 5 && current.state === "awaiting_payment"; attempt++) {
          if (attempt) await new Promise((r) => setTimeout(r, 2000));
          current = await refreshOrderCheckout(orderId);
          if (cancelled) return;
          setOrder(current);
        }
        setNotice(current.state === "awaiting_payment" ? C.stillConfirming : "");
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) setState("signin");
        else if (err instanceof ApiError && (err.status === 404 || err.status === 403)) setState("missing");
        else {
          setError(err instanceof Error ? err.message : "Something went wrong.");
          setState("error");
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [orderId, returned]);

  async function pay() {
    setBusy(true);
    setError("");
    try {
      const { url } = await startOrderCheckout(orderId);
      window.location.href = url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't open the payment page.");
      setBusy(false);
    }
  }

  if (state === "missing") return <p className="text-text-secondary">{C.missing}</p>;
  if (state === "signin") {
    const next = `/market/checkout/?order=${orderId}${returned ? "&paid=1" : ""}`;
    return (
      <Button href={`/login/?next=${encodeURIComponent(next)}`} size="lg">
        {C.signIn}
      </Button>
    );
  }
  if (state === "loading" || !order) {
    return state === "error" ? (
      <p role="alert" className="text-red-300">{error}</p>
    ) : (
      <p className="text-text-muted" role="status">{C.loading}</p>
    );
  }

  const paid = order.kind === "order" && order.state !== "awaiting_payment" && order.state !== "cancelled";
  return (
    <div className="space-y-6" data-order-state={order.state}>
      {paid && returned && (
        <div className="flex gap-3 rounded-[var(--radius-card)] border border-emerald-500/30 bg-emerald-500/5 p-4" role="status">
          <CheckCircle2 className="mt-0.5 shrink-0 text-emerald-400" size={20} aria-hidden />
          <div>
            <p className="font-semibold text-text-primary">{C.placedTitle}</p>
            <p className="text-sm text-text-secondary">{C.placedText}</p>
          </div>
        </div>
      )}
      {notice && <p className="text-sm text-text-secondary" role="status">{notice}</p>}

      <div className="flex flex-wrap items-center gap-3">
        <StateChip state={order.state} />
        {order.project?.name && <span className="text-sm text-text-muted">{order.project.name}</span>}
      </div>

      <OrderSummary order={order} />

      <dl className="grid gap-4 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-text-muted">{C.deliveryTo}</dt>
          <dd className="mt-1 text-text-primary">
            {[order.delivery.address, order.delivery.city, order.delivery.postcode, order.delivery.country].filter(Boolean).join(", ")}
          </dd>
        </div>
        {order.contact && (
          <div>
            <dt className="text-text-muted">{C.contact}</dt>
            <dd className="mt-1 text-text-primary">
              {order.contact.name} · {order.contact.email}
            </dd>
          </div>
        )}
      </dl>

      {order.kind === "quote" ? (
        <p className="text-text-secondary">{C.quote}</p>
      ) : order.state === "awaiting_payment" ? (
        <div className="space-y-3">
          <Button size="lg" onClick={pay} disabled={busy}>
            <Lock size={16} aria-hidden />
            <span className="ml-2">{busy ? C.paying : C.pay}</span>
          </Button>
          <p className="text-xs text-text-muted">{C.secure}</p>
        </div>
      ) : (
        !returned && <p className="text-text-secondary">{C.notPayable}</p>
      )}
      {error && (
        <p role="alert" className="rounded-[var(--radius-button)] border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-300">
          {error}
        </p>
      )}
      <Link href="/dashboard/orders/" className="inline-block text-sm text-accent hover:underline">
        {C.ordersLink}
      </Link>
    </div>
  );
}
