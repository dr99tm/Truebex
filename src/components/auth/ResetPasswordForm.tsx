"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { LogoMark } from "@/components/brand/Logo";
import { inputClass } from "@/components/auth/AuthForm";
import { ApiError } from "@/lib/api";
import { resetPassword } from "@/lib/auth";
import { PASSWORD_RESET } from "@/lib/constants";

const COPY = PASSWORD_RESET.reset;

type State = "reading" | "ready" | "missing" | "expired" | "sso" | "done";

/**
 * The page a reset e-mail links to: `/reset-password/#token=…`. The token is
 * read from the fragment (never a query string, so it reaches no server, log
 * or analytics), kept in memory only, and wiped from the address bar and the
 * history at once.
 */
export function ResetPasswordForm() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [state, setState] = useState<State>("reading");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const found = new URLSearchParams(window.location.hash.slice(1)).get("token");
    if (window.location.hash) window.history.replaceState(null, "", window.location.pathname);
    // Read once, after the first render (the static page has no fragment).
    setToken(found);
    setState(found ? "ready" : "missing");
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    if (password !== confirm) {
      setError(COPY.mismatch);
      return;
    }
    setBusy(true);
    setError("");
    try {
      await resetPassword(token, password);
      setToken(null);
      setState("done");
      router.push("/dashboard/");
    } catch (err) {
      if (err instanceof ApiError && err.code === "reset_link_invalid") setState("expired");
      else if (err instanceof ApiError && err.code === "sso_required") setState("sso");
      else setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-md">
      <LogoMark className="mx-auto mb-6 h-6 text-brand-fg" />
      <h1 className="text-center text-2xl font-bold tracking-tight sm:text-3xl">{COPY.h1}</h1>

      {state === "ready" && (
        <>
          <p className="mt-3 text-center text-text-secondary">{COPY.intro}</p>
          <form className="mt-8 space-y-4" onSubmit={submit}>
            <input
              type="password"
              placeholder={COPY.password}
              aria-label={COPY.password}
              autoComplete="new-password"
              required
              minLength={8}
              maxLength={128}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
            />
            <input
              type="password"
              placeholder={COPY.confirm}
              aria-label={COPY.confirm}
              autoComplete="new-password"
              required
              minLength={8}
              maxLength={128}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className={inputClass}
            />
            <p className="text-xs text-text-muted">{COPY.rule}</p>
            {error && (
              <p role="alert" className="text-sm text-red-400">
                {error}
              </p>
            )}
            <Button type="submit" size="lg" className="w-full" disabled={busy}>
              {busy ? COPY.busy : COPY.submit}
            </Button>
          </form>
        </>
      )}

      {state === "done" && (
        <p role="status" className="mt-8 text-center text-text-secondary">
          {COPY.done}
        </p>
      )}

      {(state === "missing" || state === "expired") && (
        <div className="mt-8 space-y-4 text-center">
          <p className="text-text-secondary">{state === "expired" ? COPY.expired : COPY.missing}</p>
          <a href="/forgot-password/" className="text-accent hover:underline">
            {COPY.again}
          </a>
        </div>
      )}

      {state === "sso" && (
        <div className="mt-8 space-y-4 text-center">
          <p className="text-text-secondary">{COPY.ssoRequired}</p>
          <a href="/login/" className="text-accent hover:underline">
            {COPY.toLogin}
          </a>
        </div>
      )}
    </div>
  );
}
