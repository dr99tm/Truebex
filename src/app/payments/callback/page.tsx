"use client";

// Gammal Tech card-payment callback page.
//
// The card flow is in-page (popup → onDeliver), so most successful payments
// never load this route. We still need it because Gammal Tech's whitelisted
// callback redirects here in the redirect-fallback path (e.g. 3D Secure on
// browsers that block the popup), and because the dashboard links here as
// "view payment status".

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  confirmDelivery,
  verifyPayment,
  type GammalPayment,
} from "@/lib/gammalPay";

type State =
  | { kind: "loading" }
  | { kind: "missing" }
  | { kind: "success"; payment: GammalPayment }
  | { kind: "error"; message: string };

function CallbackInner() {
  const params = useSearchParams();
  const paymentId = params.get("payment_id") ?? params.get("id");
  const [state, setState] = useState<State>(
    paymentId ? { kind: "loading" } : { kind: "missing" }
  );

  useEffect(() => {
    if (!paymentId) return;
    let cancelled = false;
    (async () => {
      try {
        const payment = await verifyPayment(paymentId);
        if (cancelled) return;
        if (payment.status === "completed") {
          try {
            await confirmDelivery(payment.id);
          } catch {
            // settlement job retries pending deliveries
          }
          if (!cancelled) setState({ kind: "success", payment });
        } else {
          setState({
            kind: "error",
            message: `Payment is ${payment.status}. Please try again.`,
          });
        }
      } catch (err) {
        if (cancelled) return;
        setState({
          kind: "error",
          message:
            err instanceof Error
              ? err.message
              : "Couldn't verify the payment.",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [paymentId]);

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-24">
      <div className="mx-auto w-full max-w-md text-center">
        {state.kind === "loading" && (
          <>
            <Loader2 className="mx-auto animate-spin text-accent" size={48} />
            <h1 className="mt-4 text-2xl font-bold tracking-tight sm:text-3xl">
              Verifying payment…
            </h1>
            <p className="mt-3 text-text-secondary">
              One moment while we confirm with the payment provider.
            </p>
          </>
        )}

        {state.kind === "missing" && (
          <>
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
              No payment to show
            </h1>
            <p className="mt-3 text-text-secondary">
              This page is the post-payment landing screen. Start a checkout
              from the pricing section to make a purchase.
            </p>
            <Button href="/#pricing" variant="secondary" size="lg" className="mt-8 w-full">
              See pricing
            </Button>
          </>
        )}

        {state.kind === "success" && (
          <>
            <CheckCircle2 className="mx-auto text-accent" size={48} />
            <h1 className="mt-4 text-2xl font-bold tracking-tight sm:text-3xl">
              Payment <span className="gradient-text">received</span>
            </h1>
            <p className="mt-3 text-text-secondary">
              Card ending {state.payment.card_last4 ?? "••••"} charged{" "}
              ${state.payment.amount.toFixed(2)} {state.payment.currency}.
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Receipt ID: {state.payment.id}
            </p>
            <Button href="/account" variant="primary" size="lg" className="mt-8 w-full">
              Go to dashboard
            </Button>
          </>
        )}

        {state.kind === "error" && (
          <>
            <XCircle className="mx-auto text-red-400" size={48} />
            <h1 className="mt-4 text-2xl font-bold tracking-tight sm:text-3xl">
              Payment problem
            </h1>
            <p className="mt-3 text-text-secondary">{state.message}</p>
            <Button href="/#pricing" variant="secondary" size="lg" className="mt-8 w-full">
              Back to pricing
            </Button>
          </>
        )}
      </div>
    </main>
  );
}

export default function PaymentCallbackPage() {
  return (
    <Suspense fallback={null}>
      <CallbackInner />
    </Suspense>
  );
}
