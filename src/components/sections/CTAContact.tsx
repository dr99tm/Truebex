"use client";

import { Section } from "@/components/layout/Section";
import { Button } from "@/components/ui/Button";
import { FadeInWhenVisible } from "@/components/animations/FadeInWhenVisible";

export function CTAContact() {
  return (
    <section id="contact" className="relative overflow-hidden">
      {/* Background glow */}
      <div className="pointer-events-none absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-[400px] w-[400px] rounded-full bg-accent/5 blur-[100px]" />

      <Section>
        <div className="relative z-10 mx-auto max-w-2xl text-center">
          <FadeInWhenVisible>
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl md:text-5xl">
              Ready to Design What{" "}
              <span className="gradient-text">Will Actually Exist?</span>
            </h2>
            <p className="mt-6 text-lg text-text-secondary">
              Experience the platform that unifies design, market, calculations,
              and VR into a single source of truth. Request a demo and see
              Truebex in action.
            </p>
          </FadeInWhenVisible>

          <FadeInWhenVisible delay={0.2}>
            <form
              className="mx-auto mt-10 max-w-md space-y-4"
              onSubmit={(e) => e.preventDefault()}
            >
              <input
                type="text"
                placeholder="Your Name"
                className="w-full rounded-[var(--radius-button)] border border-border bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-accent/50"
              />
              <input
                type="email"
                placeholder="Email Address"
                className="w-full rounded-[var(--radius-button)] border border-border bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-accent/50"
              />
              <input
                type="text"
                placeholder="Company (optional)"
                className="w-full rounded-[var(--radius-button)] border border-border bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-accent/50"
              />
              <textarea
                placeholder="Tell us about your project (optional)"
                rows={3}
                className="w-full resize-none rounded-[var(--radius-button)] border border-border bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-accent/50"
              />
              <Button type="submit" size="lg" className="w-full">
                Request a Demo
              </Button>
            </form>
          </FadeInWhenVisible>
        </div>
      </Section>
    </section>
  );
}
