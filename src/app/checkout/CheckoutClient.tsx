"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import Script from "next/script";
import { useSearchParams } from "next/navigation";
import { fetchPublicConfig } from "@/lib/auth";
import { CHECKOUT, CLOUD_AI } from "@/lib/constants";

// Paddle.js v2 (https://developer.paddle.com/paddlejs/overview). With
// `_ptxn` in the URL it opens the overlay for that transaction by itself;
// the button below opens it again if the person closed it by accident.
const PADDLE_JS = "https://cdn.paddle.com/paddle/v2/paddle.js";

interface PaddleEvent {
  name?: string;
}

interface PaddleJs {
  Environment: { set: (env: string) => void };
  Initialize: (opts: {
    token: string;
    eventCallback?: (event: PaddleEvent) => void;
    checkout?: { settings?: Record<string, unknown> };
  }) => void;
  Checkout: { open: (opts: { transactionId: string }) => void };
}

declare global {
  interface Window {
    Paddle?: PaddleJs;
  }
}

type State = "loading" | "open" | "done" | "missing" | "unavailable";

export function CheckoutClient() {
  const params = useSearchParams();
  const txn = params.get("_ptxn");
  const ref = params.get("ref") ?? "";
  // A credit pack bought on the Cloud page goes back there (PF11); every
  // other checkout goes back to billing.
  const toCloud = params.get("back") === "dashboard-cloud";
  const [scriptReady, setScriptReady] = useState(false);
  const [state, setState] = useState<State>(txn ? "loading" : "missing");
  const started = useRef(false);
  const completed = useRef(false);

  useEffect(() => {
    if (!txn || !scriptReady || started.current) return;
    started.current = true;
    const back = (outcome: "success" | "canceled") =>
      toCloud
        ? `/dashboard/cloud/?topup=${outcome}&ref=${encodeURIComponent(ref)}`
        : `/dashboard/billing/?checkout=${outcome}&ref=${encodeURIComponent(ref)}`;
    fetchPublicConfig()
      .then((cfg) => {
        const paddle = window.Paddle;
        if (!paddle || !cfg.paddle_client_token) {
          setState("unavailable");
          return;
        }
        if (cfg.paddle_env !== "production") paddle.Environment.set("sandbox");
        paddle.Initialize({
          token: cfg.paddle_client_token,
          // Codes go through the billing page (one discount per checkout,
          // never on top of the founding price).
          checkout: {
            settings: { displayMode: "overlay", theme: "dark", locale: "en", showAddDiscounts: false },
          },
          eventCallback: (event) => {
            if (event.name === "checkout.completed") {
              completed.current = true;
              setState("done");
              window.setTimeout(() => window.location.assign(back("success")), 1500);
            } else if (event.name === "checkout.closed" && !completed.current) {
              window.location.assign(back("canceled"));
            }
          },
        });
        setState("open");
      })
      .catch(() => setState("unavailable"));
  }, [txn, ref, toCloud, scriptReady]);

  return (
    <>
      <Script src={PADDLE_JS} strategy="afterInteractive" onReady={() => setScriptReady(true)} />
      <p role="status" className="max-w-md text-text-secondary">
        {state === "missing"
          ? CHECKOUT.missing
          : state === "unavailable"
            ? CHECKOUT.unavailable
            : state === "done"
              ? toCloud
                ? CLOUD_AI.checkout.done
                : CHECKOUT.done
              : CHECKOUT.opening}
      </p>
      {state === "open" && txn && (
        <button
          type="button"
          onClick={() => window.Paddle?.Checkout.open({ transactionId: txn })}
          className="text-sm text-accent hover:underline"
        >
          {CHECKOUT.open}
        </button>
      )}
      <Link
        href={toCloud ? "/dashboard/cloud/#ai-credits" : "/dashboard/billing/"}
        className="text-sm text-text-muted hover:text-text-primary"
      >
        {toCloud ? CLOUD_AI.checkout.back : CHECKOUT.back}
      </Link>
    </>
  );
}
