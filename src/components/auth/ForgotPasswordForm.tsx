"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { LogoMark } from "@/components/brand/Logo";
import { inputClass } from "@/components/auth/AuthForm";
import { requestPasswordReset } from "@/lib/auth";
import { fill } from "@/lib/catalogue";
import { PASSWORD_RESET } from "@/lib/constants";

const COPY = PASSWORD_RESET.forgot;

/** Ask for a reset link. The answer reads the same whether or not the address
 *  has an account (the API never says). */
export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await requestPasswordReset(email.trim());
      setSentTo(email.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-md">
      <LogoMark className="mx-auto mb-6 h-6 text-brand-fg" />
      <h1 className="text-center text-2xl font-bold tracking-tight sm:text-3xl">{COPY.h1}</h1>
      {sentTo ? (
        <div className="mt-8 space-y-3 text-center" role="status">
          <h2 className="font-semibold">{COPY.sentTitle}</h2>
          <p className="text-text-secondary">{fill(COPY.sent, { email: sentTo })}</p>
          <p className="text-sm text-text-muted">{COPY.sentHelp}</p>
        </div>
      ) : (
        <>
          <p className="mt-3 text-center text-text-secondary">{COPY.intro}</p>
          <form className="mt-8 space-y-4" onSubmit={submit}>
            <input
              type="email"
              placeholder={COPY.emailLabel}
              aria-label={COPY.emailLabel}
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
            />
            {error && (
              <p role="alert" className="text-sm text-red-400">
                {error}
              </p>
            )}
            <Button type="submit" size="lg" className="w-full" disabled={busy}>
              {busy ? COPY.busy : COPY.submit}
            </Button>
          </form>
          <p className="mt-4 text-center text-xs text-text-muted">{COPY.sso}</p>
        </>
      )}
      <p className="mt-6 text-center text-sm">
        <a href="/login/" className="text-accent hover:underline">
          {COPY.back}
        </a>
      </p>
    </div>
  );
}
