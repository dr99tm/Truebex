"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import Script from "next/script";
import { useSearchParams } from "next/navigation";
import { fetchPublicConfig, getToken } from "@/lib/auth";
import { CHECKOUT } from "@/lib/constants";
import { getPayment } from "@/lib/developer";

// Paddle.js v2 (https://developer.paddle.com/paddlejs/overview). With
// `_ptxn` in the URL it opens the checkout for that transaction by itself;
// the button below opens it again if the person closed it by accident.
const PADDLE_JS = "https://cdn.paddle.com/paddle/v2/paddle.js";

// PF2b: once the GD5 wording is approved the checkout's key information is
// stored with it; it is shown here, beside Paddle's inline checkout frame.
const FRAME = "paddle-checkout-frame";

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
  // PF3a: an organisation's checkout returns to that organisation's billing page.
  const org = /^[0-9a-f]{32}$/.test(params.get("org") ?? "") ? params.get("org") : null;
  const billing = org ? `/dashboard/billing/?org=${org}` : "/dashboard/billing/";
  const [scriptReady, setScriptReady] = useState(false);
  const [state, setState] = useState<State>(txn ? "loading" : "missing");
  const [summary, setSummary] = useState<string | null>(null);
  const started = useRef(false);
  const completed = useRef(false);

  // The key information acknowledged at checkout, read back from the API.
  useEffect(() => {
    if (!ref || !getToken()) return;
    getPayment(ref)
      .then((p) => setSummary(p.key_info ?? null))
      .catch(() => setSummary(null));
  }, [ref]);

  useEffect(() => {
    if (!txn || !scriptReady || started.current) return;
    started.current = true;
    const back = (outcome: "success" | "canceled") =>
      `/dashboard/billing/?checkout=${outcome}&ref=${encodeURIComponent(ref)}${org ? `&org=${org}` : ""}`;
    const keyInfo = ref && getToken() ? getPayment(ref).then((p) => p.key_info ?? null, () => null) : null;
    Promise.all([fetchPublicConfig(), keyInfo])
      .then(([cfg, info]) => {
        const paddle = window.Paddle;
        if (!paddle || !cfg.paddle_client_token) {
          setState("unavailable");
          return;
        }
        if (cfg.paddle_env !== "production") paddle.Environment.set("sandbox");
        // With key information the checkout renders inline, beside it;
        // otherwise as an overlay (PF2).
        const display = info
          ? {
              displayMode: "inline",
              frameTarget: FRAME,
              frameInitialHeight: 450,
              frameStyle: "width: 100%; min-width: 312px; background-color: transparent; border: none;",
            }
          : { displayMode: "overlay" };
        paddle.Initialize({
          token: cfg.paddle_client_token,
          // Codes go through the billing page (one discount per checkout,
          // never on top of the founding price).
          checkout: {
            settings: { ...display, theme: "dark", locale: "en", showAddDiscounts: false },
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
  }, [txn, ref, org, scriptReady]);

  const status = (
    <p role="status" className="max-w-md text-text-secondary">
      {state === "missing"
        ? CHECKOUT.missing
        : state === "unavailable"
          ? CHECKOUT.unavailable
          : state === "done"
            ? CHECKOUT.done
            : CHECKOUT.opening}
    </p>
  );

  return (
    <>
      <Script src={PADDLE_JS} strategy="afterInteractive" onReady={() => setScriptReady(true)} />
      {summary ? (
        <div className="grid w-full max-w-4xl items-start gap-6 text-left md:grid-cols-2">
          <section
            aria-label={CHECKOUT.summary}
            className="rounded-[var(--radius-card)] border border-accent/30 bg-accent/5 p-5"
          >
            <h2 className="text-sm font-semibold text-text-primary">{CHECKOUT.summary}</h2>
            <p className="mt-2 text-sm text-text-secondary">{summary}</p>
          </section>
          <div>
            {status}
            <div className={`${FRAME} mt-3 w-full`} />
          </div>
        </div>
      ) : (
        <>
          {status}
          <div className={FRAME} />
          {state === "open" && txn && (
            <button
              type="button"
              onClick={() => window.Paddle?.Checkout.open({ transactionId: txn })}
              className="text-sm text-accent hover:underline"
            >
              {CHECKOUT.open}
            </button>
          )}
        </>
      )}
      <Link href={billing} className="text-sm text-text-muted hover:text-text-primary">
        {CHECKOUT.back}
      </Link>
    </>
  );
}
