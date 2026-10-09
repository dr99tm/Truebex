"use client";

import { createContext, useContext, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { CreditCard, Gauge, KeyRound, LayoutGrid, BookOpen, Package, Store } from "lucide-react";
import { useCurrentUser } from "@/lib/useAuth";
import { getToken } from "@/lib/auth";
import type { User } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: typeof LayoutGrid;
}

// The developer pages keep their URLs (/dashboard/keys/, /dashboard/usage/):
// links to them live in the API, the docs and old emails.
const NAV_GROUPS: { label: string | null; items: NavItem[] }[] = [
  {
    label: null,
    items: [
      { href: "/dashboard/", label: "Overview", icon: LayoutGrid },
      { href: "/dashboard/billing/", label: "Billing", icon: CreditCard },
      // PF7: orders and requests for quote sent from the app.
      { href: "/dashboard/orders/", label: "Orders", icon: Package },
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
// PF7: shown to admins only (users.is_admin); the API enforces it either way.
const ADMIN_GROUP = { label: "Admin", items: [{ href: "/dashboard/admin/market/", label: "Market", icon: Store }] };

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

  const groups = user.is_admin ? [...NAV_GROUPS, ADMIN_GROUP] : NAV_GROUPS;
  const NAV = groups.flatMap((g) => g.items);

  const isActive = (href: string) =>
    href === "/dashboard/"
      ? pathname === "/dashboard" || pathname === "/dashboard/"
      : pathname.startsWith(href.replace(/\/$/, ""));

  return (
    <UserContext.Provider value={user}>
      <div className="mx-auto flex min-h-screen max-w-7xl gap-8 px-4 pb-24 pt-24 md:px-8">
        <aside className="hidden w-56 shrink-0 md:block">
          <nav aria-label="Dashboard" className="sticky top-24">
            {groups.map((group) => (
              <div key={group.label ?? "main"} className={group.label ? "mt-6" : undefined}>
                {group.label && (
                  <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
                    {group.label}
                  </p>
                )}
                <ul className="space-y-1">
                  {group.items.map(({ href, label, icon: Icon }) => (
                    <li key={href}>
                      <Link
                        href={href}
                        aria-current={isActive(href) ? "page" : undefined}
                        className={cn(
                          "flex items-center gap-3 rounded-[var(--radius-button)] px-3 py-2 text-sm transition-colors",
                          isActive(href)
                            ? "bg-accent/10 text-accent"
                            : "text-text-secondary hover:bg-white/5 hover:text-text-primary"
                        )}
                      >
                        <Icon size={16} aria-hidden />
                        {label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>
        </aside>

        <div className="min-w-0 flex-1">
          {/* Mobile tabs */}
          <nav
            aria-label="Dashboard"
            className="-mx-4 mb-6 flex gap-1 overflow-x-auto border-b border-border px-4 md:hidden"
          >
            {NAV.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                aria-current={isActive(href) ? "page" : undefined}
                className={cn(
                  "whitespace-nowrap border-b-2 px-3 py-2 text-sm",
                  isActive(href)
                    ? "border-accent text-accent"
                    : "border-transparent text-text-secondary"
                )}
              >
                {label}
              </Link>
            ))}
          </nav>
          <main>{children}</main>
        </div>
      </div>
    </UserContext.Provider>
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
