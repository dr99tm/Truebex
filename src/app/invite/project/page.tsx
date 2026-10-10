"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Check, FolderOpen } from "lucide-react";
import { ErrorNote } from "@/components/dashboard/DashboardShell";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api";
import { logout } from "@/lib/auth";
import { fill } from "@/lib/catalogue";
import { PROJECT_INVITE, PROJECTS } from "@/lib/constants";
import { acceptInvite, projectError, type ProjectRecord } from "@/lib/projects";
import { useCurrentUser } from "@/lib/useAuth";

// The link in a project invitation (contract project-log 5.14): the person
// signs in or signs up (coming back here through ?next=), then accepts. The
// token attaches the invitation to whichever account accepts it.
function InviteInner() {
  const params = useSearchParams();
  const token = params.get("t") ?? "";
  const { user, loading } = useCurrentUser();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [joined, setJoined] = useState<ProjectRecord | null>(null);

  const here = `/invite/project/?t=${encodeURIComponent(token)}`;
  const next = encodeURIComponent(here);

  async function accept() {
    setBusy(true);
    setError("");
    try {
      const res = await acceptInvite(token);
      setJoined(res.project);
    } catch (err) {
      if (err instanceof ApiError && err.code === "not_found") setError(PROJECT_INVITE.unknown);
      else if (err instanceof ApiError && err.code === "already_member") setError(PROJECT_INVITE.already);
      else setError(projectError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {!token ? (
        <div className="mt-6">
          <ErrorNote message={PROJECT_INVITE.noToken} />
        </div>
      ) : joined ? (
        <div className="mt-6 space-y-4" role="status">
          <p className="flex items-start gap-2 text-text-primary">
            <Check size={18} className="mt-0.5 shrink-0 text-emerald-400" aria-hidden />
            {fill(PROJECT_INVITE.accepted, { name: joined.name, role: PROJECTS.roles[joined.role].toLowerCase() })}
          </p>
          <Button href={`/dashboard/projects/view/?id=${joined.project_id}`}>{PROJECT_INVITE.open}</Button>
        </div>
      ) : loading ? (
        <p className="mt-6 text-sm text-text-muted" role="status">
          {PROJECTS.loading}
        </p>
      ) : !user ? (
        <div className="mt-6 flex flex-wrap gap-3">
          <Button href={`/login/?next=${next}`}>{PROJECT_INVITE.signIn}</Button>
          <Button href={`/signup/?next=${next}`} variant="secondary">
            {PROJECT_INVITE.signUp}
          </Button>
        </div>
      ) : (
        <div className="mt-6 space-y-4">
          <p className="text-sm text-text-secondary">
            {fill(PROJECT_INVITE.signedInAs, { email: user.email })}{" "}
            <Link
              href={`/login/?next=${next}`}
              onClick={() => logout()}
              className="text-accent hover:underline"
            >
              {PROJECT_INVITE.otherAccount}
            </Link>
          </p>
          <Button onClick={accept} disabled={busy}>
            {busy ? PROJECT_INVITE.accepting : PROJECT_INVITE.accept}
          </Button>
          {error && <ErrorNote message={error} />}
        </div>
      )}
    </>
  );
}

// The heading and the words are static (in the exported HTML); the part that
// reads ?t= renders on the client inside Suspense.
export default function InviteProjectPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-24">
      <div className="w-full max-w-md rounded-[var(--radius-card)] border border-border bg-surface p-6 md:p-8">
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10 text-accent">
          <FolderOpen size={20} aria-hidden />
        </span>
        <h1 className="mt-4 text-2xl font-bold tracking-tight">{PROJECT_INVITE.title}</h1>
        <p className="mt-2 text-text-secondary">{PROJECT_INVITE.intro}</p>
        <Suspense fallback={null}>
          <InviteInner />
        </Suspense>
        <p className="mt-6 text-xs text-text-muted">{PROJECT_INVITE.privacy}</p>
      </div>
    </main>
  );
}
