"use client";

// Gammal Tech payment callback page.
//
// The Gammal Tech Web SDK integration is NOT live yet: payments require
// pre-approval from Gammal Tech (email dev@gammal.tech) and a confirmed SDK
// script URL before the card flow can run. Until that's in place, this page
// shows a clear "not yet implemented" notice instead of a blank background.

import { Construction } from "lucide-react";
import { Button } from "@/components/ui/Button";

export default function PaymentCallbackPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-24">
      <div className="mx-auto w-full max-w-md text-center">
        <Construction className="mx-auto text-accent" size={48} />
        <h1 className="mt-4 text-2xl font-bold tracking-tight sm:text-3xl">
          Payments <span className="gradient-text">coming soon</span>
        </h1>
        <p className="mt-3 text-text-secondary">
          The Gammal Tech payment API is not yet implemented. Online checkout
          will be available once the integration is approved and live.
        </p>
        <Button href="/" variant="secondary" size="lg" className="mt-8 w-full">
          Back to home
        </Button>
      </div>
    </main>
  );
}
