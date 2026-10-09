"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Check, Monitor, ShieldAlert, X } from "lucide-react";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api";
import { decideLink, lookupLink, normaliseLinkCode, type LinkInfo } from "@/lib/licence";

type State = "enter" | "loading" | "ready" | "approved" | "denied" | "used" | "missing" | "error";

// The browser half of signing in from the app (contract licence-api 5.3): the
// app shows a code and opens this page; the signed-in person sees which
// computer is asking and approves or denies it.
function LinkInner() {
  const params = useSearchParams();
  const fromUrl = normaliseLinkCode(params.get("code"));
  const [code, setCode] = useState<string | null>(fromUrl);
  const [typed, setTyped] = useState(params.get("code") ?? "");
  const [info, setInfo] = useState<LinkInfo | null>(null);
  const [state, setState] = useState<State>(fromUrl ? "loading" : "enter");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!code) return;
    let cancelled = false;
    lookupLink(code)
      .then((found) => {
        if (cancelled) return;
        setInfo(found);
        setState(
          found.status === "pending"
            ? "ready"
            : found.status === "denied"
              ? "denied"
              : found.status === "approved"
                ? "approved"
                : "used"
        );
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setState("missing");
        } else {
          setError(err instanceof Error ? err.message : "Something went wrong.");
          setState("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [code]);

  function submitTyped(e: React.FormEvent) {
    e.preventDefault();
    const normal = normaliseLinkCode(typed);
    if (!normal) {
      setError("A code has 8 letters and digits, like QX7D-K9MP.");
      return;
    }
    setError("");
    setInfo(null);
    setState("loading");
    setCode(normal);
  }

  async function decide(approve: boolean) {
    if (!code) return;
    setBusy(true);
    setError("");
    try {
      await decideLink(code, approve);
      setState(approve ? "approved" : "denied");
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setState("missing");
      else setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Approve a sign-in"
        description="Truebex on a computer asked to sign in to your account."
      />
      <div className="max-w-xl">
        {state === "enter" && (
          <Panel>
            <form onSubmit={submitTyped} className="space-y-4">
              <label htmlFor="link-code" className="block text-sm font-medium text-text-primary">
                The code shown in Truebex
              </label>
              <input
                id="link-code"
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                placeholder="QX7D-K9MP"
                autoComplete="off"
                autoCapitalize="characters"
                spellCheck={false}
                maxLength={12}
                className="w-full rounded-[var(--radius-button)] border border-border bg-background px-4 py-2.5 font-mono text-lg tracking-widest text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50"
              />
              <Button type="submit">Continue</Button>
            </form>
            {error && (
              <div className="mt-4">
                <ErrorNote message={error} />
              </div>
            )}
          </Panel>
        )}

        {state === "loading" && <p className="text-sm text-text-muted" role="status">Checking the code…</p>}

        {(state === "ready" || state === "approved" || state === "denied" || state === "used") && info && (
          <Panel>
            <div className="flex items-start gap-4">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
                <Monitor size={20} aria-hidden />
              </span>
              <div className="min-w-0">
                <p className="text-lg font-semibold text-text-primary">
                  {info.device_name} · {info.app_version}
                </p>
                <p className="mt-1 font-mono text-sm tracking-widest text-text-muted">{info.link_code}</p>
              </div>
            </div>

            {state === "ready" && (
              <>
                <p className="mt-5 flex gap-2 rounded-[var(--radius-button)] border border-warn/30 bg-warn/5 px-4 py-3 text-sm text-text-primary">
                  <ShieldAlert size={18} className="mt-0.5 shrink-0 text-warn" aria-hidden />
                  Only approve a code shown on your own computer.
                </p>
                <div className="mt-5 flex flex-wrap gap-3">
                  <Button onClick={() => decide(true)} disabled={busy}>
                    <Check size={16} aria-hidden />
                    <span className="ml-2">{busy ? "Approving…" : "Approve"}</span>
                  </Button>
                  <Button variant="secondary" onClick={() => decide(false)} disabled={busy}>
                    <X size={16} aria-hidden />
                    <span className="ml-2">Deny</span>
                  </Button>
                </div>
              </>
            )}
            {state === "approved" && (
              <p role="status" className="mt-5 text-sm text-text-primary">
                <strong className="text-emerald-400">Approved.</strong> Return to Truebex: it finishes
                signing in within a few seconds.
              </p>
            )}
            {state === "denied" && (
              <p role="status" className="mt-5 text-sm text-text-primary">
                <strong className="text-red-400">Denied.</strong> That computer was not signed in.
              </p>
            )}
            {state === "used" && (
              <p role="status" className="mt-5 text-sm text-text-secondary">
                This code was already used. Start the sign-in again in Truebex if you need a new one.
              </p>
            )}
            {error && (
              <div className="mt-4">
                <ErrorNote message={error} />
              </div>
            )}
          </Panel>
        )}

        {state === "missing" && (
          <Panel>
            <p className="text-text-primary">This code is unknown or has expired.</p>
            <p className="mt-2 text-sm text-text-secondary">
              Codes last 10 minutes. Start the sign-in again in Truebex, or{" "}
              <button
                type="button"
                className="text-accent hover:underline"
                onClick={() => {
                  setState("enter");
                  setCode(null);
                }}
              >
                type a code
              </button>
              .
            </p>
          </Panel>
        )}

        {state === "error" && <ErrorNote message={error} />}

        <p className="mt-6 text-sm text-text-muted">
          Signed-in computers are listed on your{" "}
          <Link href="/dashboard/" className="text-accent hover:underline">
            dashboard
          </Link>
          , where you can remove any of them.
        </p>
      </div>
    </>
  );
}

export default function LinkPage() {
  return (
    <Suspense fallback={null}>
      <LinkInner />
    </Suspense>
  );
}
