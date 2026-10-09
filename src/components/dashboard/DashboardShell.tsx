"use client";

import { createContext, useContext, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { CreditCard, Gauge, KeyRound, LayoutGrid, BookOpen, TrendingUp } from "lucide-react";
import { useCurrentUser } from "@/lib/useAuth";
import { getToken } from "@/lib/auth";
import type { User } from "@/lib/auth";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard/", label: "Overview", icon: LayoutGrid },
  { href: "/dashboard/keys/", label: "API keys", icon: KeyRound },
  { href: "/dashboard/usage/", label: "Usage", icon: Gauge },
  { href: "/dashboard/billing/", label: "Billing", icon: CreditCard },
] as const;

// Shown to admins only (users.is_admin); the API enforces it either way.
const ADMIN_NAV = [{ href: "/dashboard/admin/growth/", label: "Growth", icon: TrendingUp }] as const;

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
      router.replace(`/login/?next=${encodeURIComponent(pathname)}`);
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

  const nav: readonly { href: string; label: string; icon: typeof LayoutGrid }[] = user.is_admin
    ? [...NAV, ...ADMIN_NAV]
    : NAV;

  const isActive = (href: string) =>
    href === "/dashboard/"
      ? pathname === "/dashboard" || pathname === "/dashboard/"
      : pathname.startsWith(href.replace(/\/$/, ""));

  return (
    <UserContext.Provider value={user}>
      <div className="mx-auto flex min-h-screen max-w-7xl gap-8 px-4 pb-24 pt-24 md:px-8">
        <aside className="hidden w-56 shrink-0 md:block">
          <nav aria-label="Dashboard" className="sticky top-24 space-y-1">
            {nav.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
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
            ))}
            <div className="my-3 h-px bg-border" />
            <Link
              href="/developers/"
              className="flex items-center gap-3 rounded-[var(--radius-button)] px-3 py-2 text-sm text-text-secondary transition-colors hover:bg-white/5 hover:text-text-primary"
            >
              <BookOpen size={16} aria-hidden />
              API docs
            </Link>
          </nav>
        </aside>

        <div className="min-w-0 flex-1">
          {/* Mobile tabs */}
          <nav
            aria-label="Dashboard"
            className="-mx-4 mb-6 flex gap-1 overflow-x-auto border-b border-border px-4 md:hidden"
          >
            {nav.map(({ href, label }) => (
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
