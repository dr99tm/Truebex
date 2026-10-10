"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Building2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api";
import { logout } from "@/lib/auth";
import { INVITE_PAGE } from "@/lib/constants";
import {
  acceptInvite,
  previewInvite,
  ROLE_NAMES,
  writeSelectedOrg,
  type InvitePreview,
} from "@/lib/orgs";
import { useCurrentUser } from "@/lib/useAuth";

type State = "loading" | "ready" | "missing" | "gone" | "joined";

// The link in an invitation e-mail: /invite/?t=<token>. Shows the
// organisation, asks the person to sign in with the invited address, then
// accepts (POST /invites/accept).
function InviteInner() {
  const token = useSearchParams().get("t") ?? "";
  const { user, loading: userLoading } = useCurrentUser();
  const [invite, setInvite] = useState<InvitePreview | null>(null);
  const [state, setState] = useState<State>("loading");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    previewInvite(token)
      .then((found) => {
        if (cancelled) return;
        setInvite(found);
        setState(found.status === "pending" ? "ready" : "gone");
      })
      .catch((err) => {
        if (cancelled) return;
        setState(err instanceof ApiError && err.status === 410 ? "gone" : "missing");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function accept() {
    setBusy(true);
    setError("");
    try {
      const res = await acceptInvite(token);
      writeSelectedOrg(res.org_id);
      setState("joined");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const here = `/invite/?t=${encodeURIComponent(token)}`;
  const next = encodeURIComponent(here);
  const matches = user && invite && user.email.toLowerCase() === invite.email;

  return (
    <div className="mx-auto w-full max-w-md text-center">
      <Building2 size={28} className="mx-auto mb-4 text-accent" aria-hidden />
      <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{INVITE_PAGE.h1}</h1>

      {state === "loading" && (
        <p className="mt-6 text-text-secondary" role="status">
          {INVITE_PAGE.loading}
        </p>
      )}
      {state === "missing" && <p className="mt-6 text-text-secondary">{INVITE_PAGE.missing}</p>}
      {state === "gone" && <p className="mt-6 text-text-secondary">{INVITE_PAGE.expired}</p>}

      {invite && state === "ready" && (
        <div className="mt-6 space-y-4">
          <p className="text-lg text-text-primary">
            {INVITE_PAGE.invited(invite.org_name, ROLE_NAMES[invite.role].toLowerCase())}
          </p>
          {invite.seat_kind === "named" && <p className="text-text-secondary">{INVITE_PAGE.seatNamed}</p>}
          {invite.seat_kind === "floating" && <p className="text-text-secondary">{INVITE_PAGE.seatFloating}</p>}

          {userLoading ? null : !user ? (
            <>
              <p className="text-sm text-text-secondary">{INVITE_PAGE.signInFirst(invite.email)}</p>
              <div className="flex justify-center gap-3">
                <Button href={`/login/?next=${next}`}>{INVITE_PAGE.signIn}</Button>
                <Button href={`/signup/?next=${next}`} variant="secondary">
                  {INVITE_PAGE.signUp}
                </Button>
              </div>
            </>
          ) : !matches ? (
            <>
              <p className="text-sm text-text-secondary">{INVITE_PAGE.wrongAccount(user.email, invite.email)}</p>
              <Button
                variant="secondary"
                onClick={() => {
                  logout();
                  window.location.href = `/login/?next=${next}`;
                }}
              >
                {INVITE_PAGE.signOut}
              </Button>
            </>
          ) : (
            <Button onClick={accept} disabled={busy}>
              {busy ? INVITE_PAGE.accepting : INVITE_PAGE.accept}
            </Button>
          )}
          {error && (
            <p role="alert" className="text-sm text-red-400">
              {error}
            </p>
          )}
        </div>
      )}

      {state === "joined" && invite && (
        <div className="mt-6 space-y-4">
          <p role="status" className="text-lg text-text-primary">
            {INVITE_PAGE.accepted(invite.org_name)}
          </p>
          <Link href="/dashboard/organisation/" className="text-accent hover:underline">
            {INVITE_PAGE.open}
          </Link>
        </div>
      )}
    </div>
  );
}

export default function InvitePage() {
  // useSearchParams needs a Suspense boundary in a static export.
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-24">
      <Suspense fallback={null}>
        <InviteInner />
      </Suspense>
    </main>
  );
}
