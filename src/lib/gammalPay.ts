"use client";

// Thin wrapper around the Gammal Tech Web SDK v3.0.1 (client-side payments).
// Card details never touch our servers; the SDK handles everything in-browser.
//
// IMPORTANT — before this works in production:
//   1. Get pre-approved: email dev@gammal.tech (payments are inert until then).
//   2. Gammal Tech manually configures the approved callback page
//      (we use /payments/callback) and whitelists the domain.
//   3. Confirm the exact SDK script URL below — it was NOT in the docs we have.
const SDK_SRC =
  process.env.NEXT_PUBLIC_GAMMAL_SDK_URL ??
  "https://sdk.gammal.tech/v3/gammaltech.js"; // TODO: confirm with Gammal Tech

/** Shape of the payment object passed to the onDeliver callback / verify. */
export interface GammalPayment {
  id: string;
  amount: number;
  currency: string;
  description: string;
  status: string;
}

// Minimal typing for the global the SDK installs on window.
interface GammalTechSDK {
  payCard: (
    amount: number,
    currency: string,
    description: string,
    onDeliver: (payment: GammalPayment) => void
  ) => void;
  pay: (
    amount: number,
    description: string,
    onDeliver: (payment: GammalPayment) => void
  ) => void;
  payment: {
    verifyPayment: (paymentId: string) => Promise<GammalPayment>;
    confirmDelivery: (paymentId: string) => Promise<void>;
    settlePending: () => Promise<void>;
  };
}

declare global {
  interface Window {
    GammalTech?: GammalTechSDK;
  }
}

let loadPromise: Promise<GammalTechSDK> | null = null;

/** Inject the SDK script once and resolve when window.GammalTech is ready. */
export function loadGammalSDK(): Promise<GammalTechSDK> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Gammal SDK can only load in the browser."));
  }
  if (window.GammalTech) return Promise.resolve(window.GammalTech);
  if (loadPromise) return loadPromise;

  loadPromise = new Promise<GammalTechSDK>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      `script[src="${SDK_SRC}"]`
    );
    const onReady = () => {
      if (window.GammalTech) resolve(window.GammalTech);
      else reject(new Error("Gammal SDK loaded but window.GammalTech is missing."));
    };

    if (existing) {
      existing.addEventListener("load", onReady, { once: true });
      existing.addEventListener("error", () =>
        reject(new Error("Failed to load Gammal Tech SDK.")), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.src = SDK_SRC;
    script.async = true;
    script.onload = onReady;
    script.onerror = () => {
      loadPromise = null; // allow retry
      reject(new Error("Failed to load Gammal Tech SDK."));
    };
    document.head.appendChild(script);
  });

  return loadPromise;
}
