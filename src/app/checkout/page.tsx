import type { Metadata } from "next";
import { Suspense } from "react";
import { CheckoutClient } from "./CheckoutClient";
import { CHECKOUT } from "@/lib/constants";

// The page Paddle's checkout links open (`/checkout/?_ptxn=txn_…&ref=…`).
// Paddle.js is loaded here only. Never indexed.
export const metadata: Metadata = {
  title: CHECKOUT.title,
  robots: { index: false, follow: false },
};

export default function CheckoutPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-4 pt-20 text-center">
      <h1 className="text-2xl font-bold tracking-tight">{CHECKOUT.title}</h1>
      <Suspense fallback={<p className="text-text-secondary">{CHECKOUT.opening}</p>}>
        <CheckoutClient />
      </Suspense>
    </main>
  );
}
