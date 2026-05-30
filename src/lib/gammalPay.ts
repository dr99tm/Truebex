"use client";

// Thin wrapper around the Gammal Tech Web SDK (client-side payments).
// Card details never touch our servers; the SDK handles everything in-browser.
//
// IMPORTANT — before this works in production:
//   1. Get pre-approved: email dev@gammal.tech (payments are inert until then).
//   2. Gammal Tech manually configures the approved callback page
//      (we use /payments/callback) and whitelists the domain.
const SDK_SRC =
  process.env.NEXT_PUBLIC_GAMMAL_SDK_URL ??
  "https://api.gammal.tech/sdk-web.js";

/** Shape of the payment object passed to the onDeliver callback / verify. */
export interface GammalPayment {
  id: string;
  amount: number;
  currency: string;
  description?: string;
  status: string;
  user_id?: string;
  card_last4?: string;
  card_brand?: string;
}

export type GammalCurrency =
  | "USD"
  | "EUR"
  | "GBP"
  | "AED"
  | "SAR"
  | "CAD";

/** Error codes the SDK can surface via the rejected promise from payWithCard. */
export type GammalErrorCode =
  | "CARD_DECLINED"
  | "INSUFFICIENT_FUNDS"
  | "3DS_FAILED"
  | "USER_CANCELLED"
  | "INVALID_CARD"
  | "SDK_LOAD_FAILED"
  | "UNKNOWN";

export class GammalPayError extends Error {
  readonly code: GammalErrorCode;
  constructor(code: GammalErrorCode, message?: string) {
    super(message ?? code);
    this.code = code;
    this.name = "GammalPayError";
  }
}

// Minimal typing for the global the SDK installs on window.
interface GammalTechSDK {
  isLoggedIn: () => boolean;
  login: () => Promise<void>;
  payCard: (
    amount: number,
    currency: string,
    description: string,
    onDeliver: (payment: GammalPayment) => void,
    onError?: (error: { code: GammalErrorCode; message?: string }) => void
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

/**
 * Open the Gammal Tech card popup and resolve when the payment is delivered.
 * Rejects with a {@link GammalPayError} carrying the SDK's error code.
 *
 * The SDK's `onDeliver` fires only on success. We treat the `onError` callback
 * (if the SDK invokes it) as the failure path, and otherwise leave the promise
 * pending — the popup itself owns the UX while the user is interacting.
 */
export async function payWithCard(args: {
  amount: number;
  currency: GammalCurrency;
  description: string;
}): Promise<GammalPayment> {
  let sdk: GammalTechSDK;
  try {
    sdk = await loadGammalSDK();
  } catch (err) {
    throw new GammalPayError(
      "SDK_LOAD_FAILED",
      err instanceof Error ? err.message : undefined
    );
  }

  if (!sdk.isLoggedIn()) {
    await sdk.login();
    if (!sdk.isLoggedIn()) {
      throw new GammalPayError("USER_CANCELLED", "Login was not completed.");
    }
  }

  return new Promise<GammalPayment>((resolve, reject) => {
    try {
      sdk.payCard(
        args.amount,
        args.currency,
        args.description,
        (payment) => resolve(payment),
        (error) =>
          reject(new GammalPayError(error?.code ?? "UNKNOWN", error?.message))
      );
    } catch (err) {
      reject(
        new GammalPayError(
          "UNKNOWN",
          err instanceof Error ? err.message : undefined
        )
      );
    }
  });
}

/** Confirm to Gammal Tech that the purchased product has been delivered. */
export async function confirmDelivery(paymentId: string): Promise<void> {
  const sdk = await loadGammalSDK();
  await sdk.payment.confirmDelivery(paymentId);
}

/** Re-fetch a payment by id (used by the callback page after a redirect). */
export async function verifyPayment(paymentId: string): Promise<GammalPayment> {
  const sdk = await loadGammalSDK();
  return sdk.payment.verifyPayment(paymentId);
}
