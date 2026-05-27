"use client";

import { useState } from "react";
import { Section } from "@/components/layout/Section";
import { Button } from "@/components/ui/Button";
import { FadeInWhenVisible } from "@/components/animations/FadeInWhenVisible";

// Google Apps Script Web App URL — set NEXT_PUBLIC_SHEETS_URL in .env.local
const SHEETS_URL = process.env.NEXT_PUBLIC_SHEETS_URL ?? "";

type FormStatus = "idle" | "loading" | "success" | "error";

export function CTAContact() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [status, setStatus] = useState<FormStatus>("idle");
  const [errorMessage, setErrorMessage] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    setErrorMessage("");

    if (!SHEETS_URL) {
      setStatus("error");
      setErrorMessage("Form is not configured. Please try again later.");
      return;
    }

    try {
      // Google Apps Script Web Apps reject JSON POSTs with a CORS preflight,
      // so we send URL-encoded form data with no-cors. The response is opaque,
      // meaning we can't read the body — absence of a network error is success.
      const body = new URLSearchParams({
        name,
        email,
        company,
        project_description: projectDescription,
      });

      await fetch(SHEETS_URL, {
        method: "POST",
        mode: "no-cors",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });

      setStatus("success");
      setName("");
      setEmail("");
      setCompany("");
      setProjectDescription("");
    } catch (err: unknown) {
      setStatus("error");
      setErrorMessage(
        err instanceof Error ? err.message : "Something went wrong."
      );
    }
  }

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
            {status === "success" ? (
              <div className="mt-10 rounded-[var(--radius-button)] border border-accent/40 bg-surface p-6 text-center">
                <p className="text-lg font-medium text-accent">
                  Request received!
                </p>
                <p className="mt-2 text-text-secondary">
                  We&apos;ll be in touch soon.
                </p>
              </div>
            ) : (
              <form
                className="mx-auto mt-10 max-w-md space-y-4"
                onSubmit={handleSubmit}
              >
                <input
                  type="text"
                  placeholder="Your Name"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-[var(--radius-button)] border border-border bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-accent/50"
                />
                <input
                  type="email"
                  placeholder="Email Address"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-[var(--radius-button)] border border-border bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-accent/50"
                />
                <input
                  type="text"
                  placeholder="Company (optional)"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  className="w-full rounded-[var(--radius-button)] border border-border bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-accent/50"
                />
                <textarea
                  placeholder="Tell us about your project (optional)"
                  rows={3}
                  value={projectDescription}
                  onChange={(e) => setProjectDescription(e.target.value)}
                  className="w-full resize-none rounded-[var(--radius-button)] border border-border bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-accent/50"
                />
                {status === "error" && (
                  <p className="text-sm text-red-400">{errorMessage}</p>
                )}
                <Button
                  type="submit"
                  size="lg"
                  className="w-full"
                  disabled={status === "loading"}
                >
                  {status === "loading" ? "Sending..." : "Request a Demo"}
                </Button>
              </form>
            )}
          </FadeInWhenVisible>
        </div>
      </Section>
    </section>
  );
}
