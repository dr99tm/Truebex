"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FolderPlus } from "lucide-react";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { Button } from "@/components/ui/Button";
import { PROJECTS } from "@/lib/constants";
import { createProject, formatBytes, listProjects, projectError, type ProjectRecord } from "@/lib/projects";
import { timeAgo } from "@/lib/time";
import { cn } from "@/lib/utils";

type Filter = "all" | "shared";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectRecord[] | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    let live = true;
    listProjects()
      .then((page) => {
        if (!live) return;
        setProjects(page.projects);
        setCursor(page.next_cursor);
      })
      .catch((err) => live && setError(projectError(err)));
    return () => {
      live = false;
    };
  }, []);

  async function more() {
    if (!cursor) return;
    setLoadingMore(true);
    try {
      const page = await listProjects(cursor);
      setProjects((prev) => [...(prev ?? []), ...page.projects]);
      setCursor(page.next_cursor);
    } catch (err) {
      setError(projectError(err));
    } finally {
      setLoadingMore(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError("");
    try {
      const created = await createProject(name.trim());
      setProjects((prev) => [created, ...(prev ?? [])]);
      setName("");
    } catch (err) {
      setError(projectError(err));
    } finally {
      setBusy(false);
    }
  }

  const shown = (projects ?? []).filter((p) => filter === "all" || p.role !== "owner");

  return (
    <>
      <PageHeader title={PROJECTS.title} description={PROJECTS.description} />

      <Panel className="mb-6">
        <form onSubmit={handleCreate} className="flex flex-col gap-3 sm:flex-row">
          <label className="sr-only" htmlFor="project-name">
            {PROJECTS.create.label}
          </label>
          <input
            id="project-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={120}
            placeholder={PROJECTS.create.placeholder}
            className="min-w-0 flex-1 rounded-[var(--radius-button)] border border-border bg-background px-4 py-2.5 text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50"
          />
          <Button type="submit" disabled={busy || !name.trim()}>
            <FolderPlus size={16} aria-hidden />
            <span className="ml-2">{busy ? PROJECTS.create.busy : PROJECTS.create.submit}</span>
          </Button>
        </form>
        {error && (
          <div className="mt-4 space-y-2">
            <ErrorNote message={error} />
            {error === PROJECTS.errors.plan && (
              <Link href="/dashboard/billing/" className="text-sm text-accent hover:underline">
                {PROJECTS.errors.planCta}
              </Link>
            )}
          </div>
        )}
      </Panel>

      <Panel>
        <div role="tablist" aria-label={PROJECTS.title} className="flex gap-1 border-b border-border">
          {(["all", "shared"] as const).map((f) => (
            <button
              key={f}
              type="button"
              role="tab"
              aria-selected={filter === f}
              onClick={() => setFilter(f)}
              className={cn(
                "-mb-px border-b-2 px-3 py-2 text-sm",
                filter === f ? "border-accent text-accent" : "border-transparent text-text-secondary hover:text-text-primary"
              )}
            >
              {PROJECTS.filters[f]}
            </button>
          ))}
        </div>

        {projects === null && !error ? (
          <p className="mt-4 text-sm text-text-muted" role="status">
            {PROJECTS.loading}
          </p>
        ) : shown.length === 0 ? (
          <p className="mt-4 text-sm text-text-muted">{filter === "all" ? PROJECTS.empty : PROJECTS.emptyShared}</p>
        ) : (
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-text-muted">
                <tr>
                  <th className="py-2 pr-4 font-medium">{PROJECTS.columns.name}</th>
                  <th className="py-2 pr-4 font-medium">{PROJECTS.columns.role}</th>
                  <th className="py-2 pr-4 font-medium">{PROJECTS.columns.changed}</th>
                  <th className="py-2 pr-4 text-right font-medium">{PROJECTS.columns.operations}</th>
                  <th className="py-2 text-right font-medium">{PROJECTS.columns.size}</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((p) => (
                  <tr key={p.project_id} className="border-t border-border" data-project={p.project_id}>
                    <td className="py-3 pr-4">
                      <Link
                        href={`/dashboard/projects/view/?id=${p.project_id}`}
                        className="font-medium text-text-primary hover:text-accent"
                      >
                        {p.name}
                      </Link>
                      {p.role !== "owner" && p.owner && (
                        <span className="block text-xs text-text-muted">{p.owner.name}</span>
                      )}
                    </td>
                    <td className="py-3 pr-4 text-text-secondary">{PROJECTS.roles[p.role]}</td>
                    <td className="py-3 pr-4 text-text-secondary">{timeAgo(p.updated_at)}</td>
                    <td className="py-3 pr-4 text-right tabular-nums text-text-secondary">{p.head_seq}</td>
                    <td className="py-3 text-right tabular-nums text-text-secondary">{formatBytes(p.bytes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {cursor && (
          <div className="mt-4">
            <Button variant="ghost" size="sm" onClick={more} disabled={loadingMore}>
              {PROJECTS.more}
            </Button>
          </div>
        )}
      </Panel>
    </>
  );
}
