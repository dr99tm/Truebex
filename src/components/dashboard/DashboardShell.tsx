"use client";

import { createContext, useContext, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { CreditCard, Gauge, KeyRound, LayoutGrid, BookOpen, TrendingUp } from "lucide-react";
import {
  Activity,
  Building2,
  Fingerprint,
  ScrollText,
  Armchair,
  UserPlus,
  Users,
} from "lucide-react";
import { OrgProvider, OrgSwitcher, useOrgs } from "@/components/dashboard/OrgContext";
import { useCurrentUser } from "@/lib/useAuth";
import { getToken } from "@/lib/auth";
import type { User } from "@/lib/auth";
import { isAdmin, type Role } from "@/lib/orgs";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: typeof LayoutGrid;
  /** Active only on this exact path (a section's overview). */
  exact?: boolean;
}

// The developer pages keep their URLs (/dashboard/keys/, /dashboard/usage/):
// links to them live in the API, the docs and old emails.
const NAV_GROUPS: { label: string | null; items: NavItem[] }[] = [
  {
    label: null,
    items: [
      { href: "/dashboard/", label: "Overview", icon: LayoutGrid },
      { href: "/dashboard/billing/", label: "Billing", icon: CreditCard },
    ],
  },
  {
    label: "Developer",
    items: [
      { href: "/dashboard/keys/", label: "API keys", icon: KeyRound },
      { href: "/dashboard/usage/", label: "Usage", icon: Gauge },
      { href: "/developers/", label: "API docs", icon: BookOpen },
    ],
  },
];

// PF3: the Organisation group. Everyone reaches the overview (to create or
// pick one); the console pages follow the role in the selected organisation.
function orgGroup(role: Role | null): { label: string; items: NavItem[] } {
  const items: NavItem[] = [
    { href: "/dashboard/organisation/", label: "Organisation", icon: Building2, exact: true },
  ];
  if (role) items.push({ href: "/dashboard/organisation/members/", label: "Members", icon: Users });
  if (isAdmin(role)) {
    items.push(
      { href: "/dashboard/organisation/invites/", label: "Invites", icon: UserPlus },
      { href: "/dashboard/organisation/seats/", label: "Seats", icon: Armchair },
      { href: "/dashboard/organisation/usage/", label: "Member usage", icon: Activity },
      { href: "/dashboard/organisation/audit/", label: "Audit log", icon: ScrollText }
    );
  }
  if (role === "owner") items.push({ href: "/dashboard/organisation/sso/", label: "SSO", icon: Fingerprint });
  return { label: "Organisation", items };
}

// Shown to admins only (users.is_admin); the API enforces it either way.
const ADMIN_GROUP: { label: string; items: NavItem[] } = {
  label: "Admin",
  items: [
    { href: "/dashboard/admin/growth/", label: "Growth", icon: TrendingUp },
    { href: "/dashboard/admin/telemetry/", label: "Telemetry", icon: Activity },
  ],
};

const UserContext = createContext<User | null>(null);

/** The signed-in user. Only valid inside the dashboard. */
export function useDashboardUser(): User {
  const user = useContext(UserContext);
  if (!user) throw new Error("useDashboardUser outside DashboardShell");
  return user;
}

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useCurrentUser();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user && !getToken()) {
      // Keep the query: /dashboard/link/?code=… must survive signing in.
      const next = pathname + window.location.search;
      router.replace(`/login/?next=${encodeURIComponent(next)}`);
    }
  }, [loading, user, router, pathname]);

  if (!user) {
    // Signed in (token present) but /auth/me failed for a non-auth reason:
    // the API is unreachable. Say so instead of spinning forever.
    const unreachable = !loading && !!getToken();
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-4 text-center">
        <p className="text-text-secondary" role="status">
          {loading
            ? "Loading your dashboard…"
            : unreachable
              ? "We can't reach the Truebex server right now."
              : "Redirecting to sign in…"}
        </p>
        {unreachable && (
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="text-sm text-accent hover:underline"
          >
            Try again
          </button>
        )}
      </main>
    );
  }

  return (
    <UserContext.Provider value={user}>
      <OrgProvider>
        <ShellLayout pathname={pathname}>{children}</ShellLayout>
      </OrgProvider>
    </UserContext.Provider>
  );
}

function ShellLayout({ pathname, children }: { pathname: string; children: React.ReactNode }) {
  const user = useDashboardUser();
  const { current } = useOrgs();
  const groups = [
    NAV_GROUPS[0],
    orgGroup(current?.role ?? null),
    ...NAV_GROUPS.slice(1),
    ...(user.is_admin ? [ADMIN_GROUP] : []),
  ];
  const NAV = groups.flatMap((g) => g.items);
  const trimmed = pathname.replace(/\/$/, "");
  const isActive = (item: NavItem) =>
    item.href === "/dashboard/" || item.exact
      ? trimmed === item.href.replace(/\/$/, "")
      : pathname.startsWith(item.href.replace(/\/$/, ""));

  return (
      <div className="mx-auto flex min-h-screen max-w-7xl gap-8 px-4 pb-24 pt-24 md:px-8">
        <aside className="hidden w-56 shrink-0 md:block">
          <nav aria-label="Dashboard" className="sticky top-24">
            <OrgSwitcher className="mb-6" />
            {groups.map((group) => (
              <div key={group.label ?? "main"} className={group.label ? "mt-6" : undefined}>
                {group.label && (
                  <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
                    {group.label}
                  </p>
                )}
                <ul className="space-y-1">
                  {group.items.map((item) => {
                    const { href, label, icon: Icon } = item;
                    return (
                    <li key={href}>
                      <Link
                        href={href}
                        aria-current={isActive(item) ? "page" : undefined}
                        className={cn(
                          "flex items-center gap-3 rounded-[var(--radius-button)] px-3 py-2 text-sm transition-colors",
                          isActive(item)
                            ? "bg-accent/10 text-accent"
                            : "text-text-secondary hover:bg-white/5 hover:text-text-primary"
                        )}
                      >
                        <Icon size={16} aria-hidden />
                        {label}
                      </Link>
                    </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </nav>
        </aside>

        <div className="min-w-0 flex-1">
          <OrgSwitcher className="mb-4 md:hidden" />
          {/* Mobile tabs */}
          <nav
            aria-label="Dashboard"
            className="-mx-4 mb-6 flex gap-1 overflow-x-auto border-b border-border px-4 md:hidden"
          >
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive(item) ? "page" : undefined}
                className={cn(
                  "whitespace-nowrap border-b-2 px-3 py-2 text-sm",
                  isActive(item)
                    ? "border-accent text-accent"
                    : "border-transparent text-text-secondary"
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <main>{children}</main>
        </div>
      </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{title}</h1>
        {description && <p className="mt-2 text-text-secondary">{description}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Panel({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      className={cn(
        "rounded-[var(--radius-card)] border border-border bg-surface p-5 md:p-6",
        className
      )}
    >
      {children}
    </section>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p role="alert" className="rounded-[var(--radius-button)] border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-300">
      {message}
    </p>
  );
}
