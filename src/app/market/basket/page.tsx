import type { Metadata } from "next";
import { Suspense } from "react";
import { Footer } from "@/components/layout/Footer";
import { BasketPanel } from "@/components/market/BasketPanel";
import { MARKET_BASKET } from "@/lib/constants";

// PF7b: the "Buy this look" basket the app's room themes open. A per-person
// page: never indexed, never in the sitemap, and no canonical (the root
// layout's "/" would point a crawler at the home page).
export const metadata: Metadata = {
  title: MARKET_BASKET.metaTitle,
  robots: { index: false, follow: false },
  alternates: { canonical: null },
};

export default function BasketPage() {
  return (
    <>
      <main className="mx-auto max-w-3xl px-4 pb-24 pt-28 md:px-8">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{MARKET_BASKET.h1}</h1>
        <p className="mt-4 text-text-secondary">{MARKET_BASKET.intro}</p>
        <section className="mt-8 rounded-[var(--radius-card)] border border-border bg-surface p-5 md:p-8">
          {/* ?region= and ?items= are read in the browser (static export). */}
          <Suspense fallback={<p className="text-text-muted">{MARKET_BASKET.loading}</p>}>
            <BasketPanel />
          </Suspense>
        </section>
      </main>
      <Footer />
    </>
  );
}
