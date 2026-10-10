import type { Metadata } from "next";
import { Suspense } from "react";
import { JoinPanel } from "@/components/supplier/JoinPanel";
import { SUPPLIER } from "@/lib/constants";

// noindex comes from the supplier layout. ?token= is read on the client.
export const metadata: Metadata = { title: SUPPLIER.join.metaTitle };

export default function SupplierJoinPage() {
  return (
    <>
      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{SUPPLIER.join.h1}</h1>
      <p className="mt-4 text-text-secondary">{SUPPLIER.join.intro}</p>
      <section className="mt-8 rounded-[var(--radius-card)] border border-border bg-surface p-5 md:p-8">
        <Suspense fallback={<p className="text-text-muted">…</p>}>
          <JoinPanel />
        </Suspense>
      </section>
    </>
  );
}
