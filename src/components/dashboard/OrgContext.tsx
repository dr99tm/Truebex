"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Building2 } from "lucide-react";
import {
  isAdmin,
  listOrgs,
  readSelectedOrg,
  writeSelectedOrg,
  type OrgSummary,
  type Role,
} from "@/lib/orgs";

interface OrgState {
  orgs: OrgSummary[];
  /** The organisation chosen in the switcher; null = the personal workspace. */
  current: OrgSummary | null;
  loading: boolean;
  error: string | null;
  select: (id: string | null) => void;
  reload: () => Promise<void>;
}

const OrgContext = createContext<OrgState | null>(null);

/** The signed-in user's organisations and the selected workspace. Mounted by
 *  DashboardShell once the user is known (so only ever in the browser). */
export function OrgProvider({ children }: { children: React.ReactNode }) {
  const [orgs, setOrgs] = useState<OrgSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(readSelectedOrg);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setOrgs(await listOrgs());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load your organisations.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const select = useCallback((id: string | null) => {
    writeSelectedOrg(id);
    setSelected(id);
  }, []);

  const current = orgs.find((o) => o.id === selected) ?? null;
  return (
    <OrgContext.Provider value={{ orgs, current, loading, error, select, reload }}>
      {children}
    </OrgContext.Provider>
  );
}

export function useOrgs(): OrgState {
  const state = useContext(OrgContext);
  if (!state) throw new Error("useOrgs outside OrgProvider");
  return state;
}

/** Personal or an organisation, above the dashboard navigation. */
export function OrgSwitcher({ className }: { className?: string }) {
  const { orgs, current, select } = useOrgs();
  const router = useRouter();
  const pathname = usePathname();
  if (orgs.length === 0) return null;

  function change(id: string) {
    select(id || null);
    const inConsole = pathname.startsWith("/dashboard/organisation");
    if (id && !inConsole) router.push("/dashboard/organisation/");
    if (!id && inConsole) router.push("/dashboard/");
  }

  return (
    <div className={className}>
      <label htmlFor="workspace" className="mb-1 block px-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
        Workspace
      </label>
      <select
        id="workspace"
        value={current?.id ?? ""}
        onChange={(e) => change(e.target.value)}
        className="w-full rounded-[var(--radius-button)] border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent/50"
      >
        <option value="">Personal</option>
        {orgs.map((o) => (
          <option key={o.id} value={o.id}>
            {o.name}
          </option>
        ))}
      </select>
    </div>
  );
}

const LEVEL: Record<"member" | "admin" | "owner", (role: Role) => boolean> = {
  member: () => true,
  admin: isAdmin,
  owner: (role) => role === "owner",
};

/** Renders `children(org)` for the selected organisation when the caller's
 *  role allows the page; otherwise says what to do instead. */
export function OrgGate({
  level = "member",
  children,
}: {
  level?: "member" | "admin" | "owner";
  children: (org: OrgSummary) => React.ReactNode;
}) {
  const { current, orgs, loading, error } = useOrgs();
  if (loading) return <p className="text-sm text-text-muted" role="status">Loading your organisations…</p>;
  if (error) return <p role="alert" className="text-sm text-red-300">{error}</p>;
  if (!current) {
    return (
      <div className="rounded-[var(--radius-card)] border border-border bg-surface p-6">
        <p className="flex items-center gap-2 font-semibold">
          <Building2 size={18} aria-hidden /> No organisation selected
        </p>
        <p className="mt-2 text-sm text-text-secondary">
          {orgs.length > 0
            ? "Choose one in the Workspace menu, or create another."
            : "Create an organisation to share seats with your team."}
        </p>
        <Link href="/dashboard/organisation/" className="mt-4 inline-block text-sm text-accent hover:underline">
          Go to Organisation
        </Link>
      </div>
    );
  }
  if (!LEVEL[level](current.role)) {
    return (
      <p className="rounded-[var(--radius-card)] border border-border bg-surface p-6 text-sm text-text-secondary">
        Only {level === "owner" ? "an owner" : "an owner or admin"} of {current.name} can open this page.
      </p>
    );
  }
  return <>{children(current)}</>;
}
