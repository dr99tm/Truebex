"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  CreditCard,
  Inbox,
  LayoutGrid,
  Package,
  Tags,
  Upload,
  UserRound,
  Users,
} from "lucide-react";
import { getToken } from "@/lib/auth";
import { SUPPLIER } from "@/lib/constants";
import { getSupplierId, setSupplierId, supplierApi, type Me, type Role } from "@/lib/supplier";
import { useCurrentUser } from "@/lib/useAuth";
import { cn } from "@/lib/utils";

const N = SUPPLIER.nav;

interface NavItem {
  href: string;
  label: string;
  icon: typeof LayoutGrid;
  roles?: Role[];
}

// Mirrors DashboardShell: side nav on desktop, scrolling tabs on phones. What
// a role cannot open is not shown (the API enforces the roles either way).
const NAV: NavItem[] = [
  { href: "/supplier/", label: N.overview, icon: LayoutGrid },
  { href: "/supplier/catalogue/", label: N.catalogue, icon: Package },
  { href: "/supplier/prices/", label: N.prices, icon: Tags },
  { href: "/supplier/imports/", label: N.imports, icon: Upload },
  { href: "/supplier/inbox/", label: N.inbox, icon: Inbox, roles: ["owner", "orders"] },
  { href: "/supplier/analytics/", label: N.analytics, icon: BarChart3 },
  { href: "/supplier/billing/", label: N.billing, icon: CreditCard, roles: ["owner"] },
  { href: "/supplier/team/", label: N.team, icon: Users, roles: ["owner"] },
];

// Pages that work without a supplier (applying, accepting an invitation).
const OPEN_PATHS = ["/supplier/signup", "/supplier/join"];

interface SupplierContextValue {
  me: Me | null;
  reload: () => Promise<Me | null>;
}

const SupplierContext = createContext<SupplierContextValue>({ me: null, reload: async () => null });

/** The member, their supplier and role. `me` is null until loaded (and on open pages when signed out). */
export function useSupplier(): SupplierContextValue {
  return useContext(SupplierContext);
}

/** Inside the portal's member pages: the supplier and role are always there. */
export function useMember(): { me: Me; role: Role; reload: () => Promise<Me | null> } {
  const { me, reload } = useContext(SupplierContext);
  if (!me || !me.supplier || !me.role) throw new Error("useMember outside a supplier page");
  return { me, role: me.role, reload };
}

export function can(role: Role | null | undefined, area: "catalogue" | "orders" | "owner"): boolean {
  if (!role) return false;
  if (role === "owner") return true;
  return area === "catalogue" ? role === "catalogue" : area === "orders" ? role === "orders" : false;
}

/** /supplier/me, keeping the stored supplier choice valid. Null when the API is unreachable. */
async function loadMe(): Promise<Me | null> {
  try {
    let next = await supplierApi.me();
    const stored = getSupplierId();
    if (next.supplier && stored !== next.supplier.supplier_id) {
      // No choice yet, or one the person no longer belongs to: the server's pick.
      setSupplierId(next.supplier.supplier_id);
    } else if (!next.supplier && stored) {
      setSupplierId(null);
      next = await supplierApi.me();
    }
    return next;
  } catch {
    return null;
  }
}

function Centered({ children }: { children: React.ReactNode }) {
  return <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-4 text-center">{children}</main>;
}

export function SupplierShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useCurrentUser();
  const router = useRouter();
  const pathname = usePathname();
  const open = OPEN_PATHS.some((p) => pathname.startsWith(p));
  const [me, setMe] = useState<Me | null>(null);
  const [meError, setMeError] = useState(false);

  const reload = useCallback(async () => {
    const next = await loadMe();
    setMe(next);
    setMeError(next === null);
    return next;
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    loadMe().then((next) => {
      if (cancelled) return;
      setMe(next);
      setMeError(next === null);
    });
    return () => {
      cancelled = true;
    };
  }, [user]);

  useEffect(() => {
    if (!open && !loading && !user && !getToken()) {
      const next = pathname + window.location.search;
      router.replace(`/login/?next=${encodeURIComponent(next)}`);
    }
  }, [open, loading, user, router, pathname]);

  const value = { me, reload };

  if (open) {
    return (
      <SupplierContext.Provider value={value}>
        <div className="mx-auto min-h-screen max-w-3xl px-4 pb-24 pt-24 md:px-8">{children}</div>
      </SupplierContext.Provider>
    );
  }

  if (!user || (!me && !meError)) {
    const unreachable = !loading && !!getToken() && !user;
    return (
      <Centered>
        <p className="text-text-secondary" role="status">
          {loading || (user && !me)
            ? SUPPLIER.shell.loading
            : unreachable
              ? SUPPLIER.shell.unreachable
              : SUPPLIER.shell.redirecting}
        </p>
        {unreachable && (
          <button type="button" onClick={() => window.location.reload()} className="text-sm text-accent hover:underline">
            {SUPPLIER.shell.retry}
          </button>
        )}
      </Centered>
    );
  }

  if (meError || !me) {
    return (
      <Centered>
        <p className="text-text-secondary" role="status">
          {SUPPLIER.shell.unreachable}
        </p>
        <button type="button" onClick={() => void reload()} className="text-sm text-accent hover:underline">
          {SUPPLIER.shell.retry}
        </button>
      </Centered>
    );
  }

  if (!me.supplier) {
    return (
      <Centered>
        <h1 className="text-2xl font-bold tracking-tight">{SUPPLIER.shell.noSupplierTitle}</h1>
        <p className="max-w-md text-text-secondary">{SUPPLIER.shell.noSupplierText}</p>
        <Link href="/supplier/signup/" className="text-accent hover:underline">
          {SUPPLIER.shell.apply}
        </Link>
      </Centered>
    );
  }

  const role = me.role;
  const items = NAV.filter((i) => !i.roles || (role && i.roles.includes(role)));
  const isActive = (href: string) =>
    href === "/supplier/"
      ? pathname === "/supplier" || pathname === "/supplier/"
      : pathname.startsWith(href.replace(/\/$/, ""));

  const switcher =
    me.memberships.length > 1 ? (
      <label className="block text-xs text-text-muted">
        {N.switcher}
        <select
          value={me.supplier.supplier_id}
          onChange={(e) => {
            setSupplierId(e.target.value);
            window.location.reload();
          }}
          className="mt-1 block w-full rounded-[var(--radius-button)] border border-border bg-surface px-3 py-2 text-sm text-text-primary"
        >
          {me.memberships.map((m) => (
            <option key={m.supplier_id} value={m.supplier_id}>
              {m.name} · {SUPPLIER.roles[m.role] ?? m.role}
            </option>
          ))}
        </select>
      </label>
    ) : null;

  return (
    <SupplierContext.Provider value={value}>
      <div className="mx-auto flex min-h-screen max-w-7xl gap-8 px-4 pb-24 pt-24 md:px-8">
        <aside className="hidden w-56 shrink-0 md:block">
          <nav aria-label={SUPPLIER.meta.title} className="sticky top-24 space-y-4">
            <div>
              <p className="truncate px-3 text-sm font-semibold text-text-primary">{me.supplier.name}</p>
              <p className="px-3 text-xs text-text-muted">
                {SUPPLIER.status[me.supplier.status] ?? me.supplier.status} · {SUPPLIER.roles[role ?? ""] ?? role}
              </p>
            </div>
            {switcher && <div className="px-3">{switcher}</div>}
            <ul className="space-y-1">
              {items.map(({ href, label, icon: Icon }) => (
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
              <li className="pt-4">
                <Link
                  href="/dashboard/"
                  className="flex items-center gap-3 rounded-[var(--radius-button)] px-3 py-2 text-sm text-text-muted hover:bg-white/5 hover:text-text-primary"
                >
                  <UserRound size={16} aria-hidden />
                  {N.dashboard}
                </Link>
              </li>
            </ul>
          </nav>
        </aside>

        <div className="min-w-0 flex-1">
          {/* Phones: the supplier, the switcher and scrolling tabs. */}
          <div className="mb-4 md:hidden">
            <p className="text-sm font-semibold text-text-primary">{me.supplier.name}</p>
            {switcher && <div className="mt-2">{switcher}</div>}
          </div>
          <nav
            aria-label={SUPPLIER.meta.title}
            className="-mx-4 mb-6 flex gap-1 overflow-x-auto border-b border-border px-4 md:hidden"
          >
            {items.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                aria-current={isActive(href) ? "page" : undefined}
                className={cn(
                  "whitespace-nowrap border-b-2 px-3 py-2 text-sm",
                  isActive(href) ? "border-accent text-accent" : "border-transparent text-text-secondary"
                )}
              >
                {label}
              </Link>
            ))}
          </nav>
          <main>{children}</main>
        </div>
      </div>
    </SupplierContext.Provider>
  );
}

/** A labelled form field in the portal's style. */
export function Field({
  label,
  hint,
  className,
  children,
}: {
  label: string;
  hint?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <label className={cn("block text-sm", className)}>
      <span className="text-text-secondary">{label}</span>
      <span className="mt-1 block">{children}</span>
      {hint && <span className="mt-1 block text-xs text-text-muted">{hint}</span>}
    </label>
  );
}

export const inputClass =
  "w-full rounded-[var(--radius-button)] border border-border bg-background px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none";

/** A status pill (product, supplier, order states). */
export function Badge({ tone = "neutral", children }: { tone?: "good" | "warn" | "bad" | "neutral"; children: React.ReactNode }) {
  const tones = {
    good: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
    warn: "border-warn/30 bg-warn/10 text-warn",
    bad: "border-red-500/30 bg-red-500/10 text-red-300",
    neutral: "border-border bg-white/5 text-text-secondary",
  };
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium", tones[tone])}>
      {children}
    </span>
  );
}

export function productTone(status: string): "good" | "warn" | "bad" | "neutral" {
  if (status === "approved") return "good";
  if (status === "pending_review") return "warn";
  if (status === "rejected" || status === "withdrawn") return "bad";
  return "neutral";
}

export function OkNote({ message }: { message: string }) {
  return (
    <p role="status" className="rounded-[var(--radius-button)] border border-emerald-500/30 bg-emerald-500/5 px-4 py-3 text-sm text-emerald-300">
      {message}
    </p>
  );
}
