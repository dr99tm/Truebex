import type { Metadata } from "next";
import { Suspense } from "react";
import { Footer } from "@/components/layout/Footer";
import { CheckoutPanel } from "@/components/market/CheckoutPanel";
import { MARKET } from "@/lib/constants";

// A per-order page: never indexed, never in the sitemap.
export const metadata: Metadata = {
  title: MARKET.checkout.metaTitle,
  robots: { index: false, follow: false },
};

export default function CheckoutPage() {
  return (
    <>
      <main className="mx-auto max-w-3xl px-4 pb-24 pt-28 md:px-8">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{MARKET.checkout.h1}</h1>
        <p className="mt-4 text-text-secondary">{MARKET.checkout.intro}</p>
        <section className="mt-8 rounded-[var(--radius-card)] border border-border bg-surface p-5 md:p-8">
          {/* ?order= is read on the client (static export). */}
          <Suspense fallback={<p className="text-text-muted">{MARKET.checkout.loading}</p>}>
            <CheckoutPanel />
          </Suspense>
        </section>
      </main>
      <Footer />
    </>
  );
}
