"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronRight, Download, Share, WifiOff } from "lucide-react";
import { useApp } from "@/components/app/AppShell";
import { SignInPrompt } from "@/components/app/ProjectScreen";
import { Lockup } from "@/components/brand/Logo";
import { ApiError } from "@/lib/api";
import { getMe, type Me } from "@/lib/app";
import { logout } from "@/lib/auth";
import { fill } from "@/lib/catalogue";
import { APP } from "@/lib/constants";
import { listProjects, type ProjectRecord, type ProjectRole } from "@/lib/projects";
import { timeAgo } from "@/lib/time";
import { useIsAuthenticated } from "@/lib/useAuth";
import { clearAppData, kv } from "@/viewer/outbox";

/** /app/: the projects this person owns or that are shared with them (5.2), role shown. */
export function AppHome() {
  const authed = useIsAuthenticated();
  const app = useApp();
  const [projects, setProjects] = useState<ProjectRecord[] | null>(null);
  const [offline, setOffline] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!authed) return;
    let live = true;
    (async () => {
      const cached = await kv.get<ProjectRecord[]>("projects");
      if (live && cached) setProjects(cached);
      try {
        const [me, page] = await Promise.all([getMe(), listProjects()]);
        const known = await kv.get<Me>("me");
        if (known && known.id !== me.id) await clearAppData(); // another account on this device
        await kv.set("me", me);
        await kv.set("projects", page.projects);
        if (!live) return;
        setProjects(page.projects);
        setOffline(false);
      } catch (err) {
        if (!live) return;
        if (err instanceof ApiError && err.status === 0) setOffline(true);
        else setError(err instanceof Error ? err.message : APP.errors.generic);
        setProjects((p) => p ?? []);
      }
    })();
    return () => {
      live = false;
    };
  }, [authed]);

  if (authed === false) return <SignInPrompt next="/app/" />;
  const roles = APP.roles as Record<ProjectRole, string>;

  return (
    <main className="mx-auto max-w-xl px-4 pb-16 pt-[max(1rem,env(safe-area-inset-top))]">
      <header className="flex items-center justify-between gap-3 py-3">
        <div className="flex items-center gap-3">
          <Lockup className="text-xl" />
          <span className="rounded-full border border-accent/50 px-2 py-0.5 text-[11px] font-medium text-accent">{APP.badge}</span>
        </div>
        <div className="flex items-center gap-2">
          {app.canInstall && (
            <button
              type="button"
              onClick={() => void app.install()}
              className="flex h-9 items-center gap-1.5 rounded-[var(--radius-button)] bg-accent px-3 text-sm font-medium text-background"
            >
              <Download className="h-4 w-4" aria-hidden="true" />
              {APP.install.button}
            </button>
          )}
          {authed && (
            <button
              type="button"
              onClick={() => {
                logout();
                void clearAppData();
              }}
              className="h-9 rounded-[var(--radius-button)] px-3 text-sm text-text-secondary hover:text-text-primary"
            >
              {APP.list.signOut}
            </button>
          )}
        </div>
      </header>
      {app.iosHint && (
        <p className="mb-4 flex items-center gap-2 rounded-[var(--radius-button)] border border-border bg-surface p-3 text-sm text-text-secondary">
          <Share className="h-4 w-4 shrink-0" aria-hidden="true" />
          {APP.install.ios}
        </p>
      )}

      <h1 className="mt-4 text-2xl font-semibold">{APP.list.title}</h1>
      <p className="mt-1 text-sm text-text-secondary">{APP.list.intro}</p>
      {(offline || !app.online) && (
        <p role="status" className="mt-4 flex items-center gap-2 rounded-[var(--radius-button)] border border-warn/50 px-3 py-2 text-sm text-warn">
          <WifiOff className="h-4 w-4 shrink-0" aria-hidden="true" />
          {APP.list.offline}
        </p>
      )}
      {error && <p className="mt-4 text-sm text-warn">{error}</p>}

      {projects === null ? (
        <p className="mt-6 text-sm text-text-secondary">{APP.list.loading}</p>
      ) : projects.length === 0 ? (
        <p className="mt-6 rounded-[var(--radius-card)] border border-border bg-surface p-4 text-sm text-text-secondary">{APP.list.empty}</p>
      ) : (
        <ul className="mt-6 space-y-3">
          {projects.map((p) => (
            <li key={p.project_id}>
              <Link
                href={`/app/project/?id=${p.project_id}`}
                className="flex items-center justify-between gap-3 rounded-[var(--radius-card)] border border-border bg-surface p-4 transition-colors hover:border-accent/50"
              >
                <span className="min-w-0">
                  <span className="block truncate font-medium">
                    {p.name} <span className="text-sm font-normal text-text-secondary">({roles[p.role]})</span>
                  </span>
                  <span className="block text-xs text-text-muted">
                    {p.owner?.name ? `${p.owner.name} · ` : ""}
                    {fill(APP.list.changed, { when: timeAgo(p.updated_at) })}
                  </span>
                </span>
                <ChevronRight className="h-5 w-5 shrink-0 text-text-muted" aria-label={APP.list.open} />
              </Link>
            </li>
          ))}
        </ul>
      )}
      {app.installed && <p className="mt-8 text-center text-xs text-text-muted">{APP.install.done}</p>}
    </main>
  );
}
