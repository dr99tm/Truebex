import type { Metadata } from "next";
import { SignupForm } from "@/components/supplier/SignupForm";
import { SUPPLIER } from "@/lib/constants";

// noindex comes from the supplier layout; the heading and help are rendered
// here so they read before the form loads.
export const metadata: Metadata = { title: SUPPLIER.signup.metaTitle };

export default function SupplierSignupPage() {
  return (
    <>
      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{SUPPLIER.signup.h1}</h1>
      <p className="mt-4 text-text-secondary">{SUPPLIER.signup.intro}</p>
      <section className="mt-8 rounded-[var(--radius-card)] border border-border bg-surface p-5 md:p-8">
        <SignupForm />
      </section>
    </>
  );
}
