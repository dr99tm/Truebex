"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { GoogleButton } from "@/components/auth/GoogleButton";
import { LogoMark } from "@/components/brand/Logo";
import { ApiError } from "@/lib/api";
import { login, register, safeNext } from "@/lib/auth";
import { SSO_LOGIN } from "@/lib/constants";
import { ssoStart } from "@/lib/orgs";

type Mode = "login" | "signup";

const inputClass =
  "w-full rounded-[var(--radius-button)] border border-border bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-accent/50";

function AuthFormInner({ mode }: { mode: Mode }) {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  // PF3: single sign-on, and the break-glass field once SSO is required.
  const [sso, setSso] = useState(false);
  const [ssoRequired, setSsoRequired] = useState(false);
  const [breakGlass, setBreakGlass] = useState("");

  const isSignup = mode === "signup";
  const done = () => router.push(next);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (isSignup) {
        await register(email, password);
      } else {
        await login(email, password, breakGlass.trim() || undefined);
      }
      done();
    } catch (err) {
      if (err instanceof ApiError && err.code === "sso_required") setSsoRequired(true);
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  const other = isSignup ? "/login/" : "/signup/";
  const otherHref = params.get("next") ? `${other}?next=${encodeURIComponent(next)}` : other;

  return (
    <div className="mx-auto w-full max-w-md">
      <LogoMark className="mx-auto mb-6 h-6 text-brand-fg" />
      <h1 className="text-center text-2xl font-bold tracking-tight sm:text-3xl">
        {isSignup ? (
          <>
            Create your <span className="gradient-text">Truebex</span> account
          </>
        ) : (
          <>
            Welcome <span className="gradient-text">back</span>
          </>
        )}
      </h1>
      <p className="mt-3 text-center text-text-secondary">
        {isSignup
          ? "Free to start. Get your dashboard and API keys in seconds."
          : "Sign in to your dashboard."}
      </p>

      {sso ? (
        <SsoPanel next={next} initialEmail={email} onBack={() => setSso(false)} />
      ) : (
      <div className="mt-8">
        <GoogleButton mode={mode} onSuccess={done} onError={setError} />

        <form className="space-y-4" onSubmit={handleSubmit}>
          <input
            type="email"
            placeholder="Email address"
            aria-label="Email address"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputClass}
          />
          <input
            type="password"
            placeholder="Password"
            aria-label="Password"
            autoComplete={isSignup ? "new-password" : "current-password"}
            required
            minLength={isSignup ? 8 : undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
          />
          {isSignup && (
            <p className="text-xs text-text-muted">At least 8 characters.</p>
          )}
          {ssoRequired && !isSignup && (
            <div className="space-y-2">
              <p className="text-xs text-text-muted">{SSO_LOGIN.breakGlassHelp}</p>
              <input
                type="text"
                placeholder={SSO_LOGIN.breakGlassLabel}
                aria-label={SSO_LOGIN.breakGlassLabel}
                autoComplete="off"
                value={breakGlass}
                onChange={(e) => setBreakGlass(e.target.value)}
                className={inputClass}
              />
            </div>
          )}
          {error && (
            <p role="alert" className="text-sm text-red-400">
              {error}
            </p>
          )}
          <Button type="submit" size="lg" className="w-full" disabled={loading}>
            {loading ? "Please wait…" : isSignup ? "Create account" : "Log in"}
          </Button>
        </form>
        <Button
          type="button"
          variant={ssoRequired ? "primary" : "ghost"}
          size="lg"
          className="mt-3 w-full"
          onClick={() => setSso(true)}
        >
          {SSO_LOGIN.button}
        </Button>
      </div>
      )}

      <p className="mt-6 text-center text-xs text-text-muted">
        By continuing you agree to the{" "}
        <Link href="/terms/" className="underline hover:text-text-secondary">Terms</Link> and{" "}
        <Link href="/privacy/" className="underline hover:text-text-secondary">Privacy Policy</Link>.
      </p>

      <p className="mt-4 text-center text-sm text-text-secondary">
        {isSignup ? "Already have an account? " : "Don't have an account? "}
        <a href={otherHref} className="text-accent hover:underline">
          {isSignup ? "Log in" : "Sign up"}
        </a>
      </p>
    </div>
  );
}

/** "Continue with SSO": a work e-mail, then the organisation's identity provider. */
function SsoPanel({ next, initialEmail, onBack }: { next: string; initialEmail: string; onBack: () => void }) {
  const [email, setEmail] = useState(initialEmail);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { url } = await ssoStart(email.trim(), next);
      window.location.href = url;
    } catch (err) {
      setError(
        err instanceof ApiError && err.code === "sso_not_found"
          ? SSO_LOGIN.notFound
          : err instanceof Error
            ? err.message
            : "Something went wrong."
      );
      setBusy(false);
    }
  }

  return (
    <div className="mt-8">
      <h2 className="text-center font-semibold">{SSO_LOGIN.title}</h2>
      <p className="mt-2 text-center text-sm text-text-secondary">{SSO_LOGIN.help}</p>
      <form className="mt-6 space-y-4" onSubmit={submit}>
        <input
          type="email"
          placeholder={SSO_LOGIN.emailPlaceholder}
          aria-label={SSO_LOGIN.emailLabel}
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
          {busy ? SSO_LOGIN.busy : SSO_LOGIN.submit}
        </Button>
      </form>
      <button type="button" onClick={onBack} className="mt-4 w-full text-center text-sm text-accent hover:underline">
        {SSO_LOGIN.back}
      </button>
    </div>
  );
}

export function AuthForm({ mode }: { mode: Mode }) {
  // useSearchParams needs a Suspense boundary in a static export.
  return (
    <Suspense fallback={null}>
      <AuthFormInner mode={mode} />
    </Suspense>
  );
}
