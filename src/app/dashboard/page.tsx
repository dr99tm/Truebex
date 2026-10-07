"use client";

import Link from "next/link";
import { ArrowRight, KeyRound, CreditCard, BookOpen } from "lucide-react";
import {
  ErrorNote,
  PageHeader,
  Panel,
  useDashboardUser,
} from "@/components/dashboard/DashboardShell";
import { UsageMeter } from "@/components/dashboard/UsageMeter";
import { useApiData } from "@/components/dashboard/useApiData";
import { Button } from "@/components/ui/Button";
import { API_URL, formatDate } from "@/lib/api";
import { getUsage, listKeys } from "@/lib/developer";
import { logout } from "@/lib/auth";

export default function DashboardOverview() {
  const user = useDashboardUser();
  const usage = useApiData(getUsage);
  const keys = useApiData(listKeys);
  const activeKeys = keys.data?.filter((k) => !k.revoked_at).length ?? 0;
  const first = user.name?.split(" ")[0] ?? user.email.split("@")[0];

  function handleLogout() {
    logout();
    window.location.href = "/";
  }

  return (
    <>
      <PageHeader
        title={`Welcome, ${first}`}
        description={`Signed in as ${user.email} · member since ${formatDate(user.created_at)}`}
        actions={
          <Button variant="secondary" size="sm" onClick={handleLogout}>
            Log out
          </Button>
        }
      />

      {(usage.error || keys.error) && (
        <div className="mb-6">
          <ErrorNote message={usage.error ?? keys.error ?? ""} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Panel className="lg:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">API usage this month</h2>
            <Link href="/dashboard/usage/" className="text-sm text-accent hover:underline">
              Details
            </Link>
          </div>
          <div className="mt-5">
            {usage.data ? (
              <UsageMeter used={usage.data.used} limit={usage.data.limit} />
            ) : (
              <p className="text-sm text-text-muted">{usage.loading ? "Loading…" : "—"}</p>
            )}
          </div>
        </Panel>

        <Panel>
          <h2 className="font-semibold">Plan</h2>
          <p className="mt-4 text-3xl font-semibold capitalize">{user.plan}</p>
          <p className="mt-1 text-sm text-text-muted">
            {user.plan === "free" ? "Starter · free forever" : "Thanks for supporting Truebex"}
          </p>
          <Link
            href="/dashboard/billing/"
            className="mt-4 inline-flex items-center gap-1 text-sm text-accent hover:underline"
          >
            {user.plan === "free" ? "Upgrade to Pro" : "Manage billing"}
            <ArrowRight size={14} aria-hidden />
          </Link>
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 md:grid-cols-3">
        <QuickLink
          href="/dashboard/keys/"
          icon={<KeyRound size={18} aria-hidden />}
          title="API keys"
          text={keys.data ? `${activeKeys} active` : "Create a key to call the API"}
        />
        <QuickLink
          href="/dashboard/billing/"
          icon={<CreditCard size={18} aria-hidden />}
          title="Billing"
          text="Plans, payments and invoices"
        />
        <QuickLink
          href="/developers/"
          icon={<BookOpen size={18} aria-hidden />}
          title="API docs"
          text="Authentication, endpoints, limits"
        />
      </div>

      <Panel className="mt-6">
        <h2 className="font-semibold">Quick start</h2>
        <p className="mt-2 text-sm text-text-secondary">
          Create a key under <Link className="text-accent hover:underline" href="/dashboard/keys/">API keys</Link>, then:
        </p>
        <pre className="mt-4 overflow-x-auto rounded-[var(--radius-button)] border border-border bg-background p-4 font-mono text-sm text-text-primary">
          {`curl ${API_URL}/v1/ping \\\n  -H "Authorization: Bearer tbx_live_…"`}
        </pre>
      </Panel>
    </>
  );
}

function QuickLink({
  href,
  icon,
  title,
  text,
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  text: string;
}) {
  return (
    <Link
      href={href}
      className="group rounded-[var(--radius-card)] border border-border bg-surface p-5 transition-colors hover:border-accent/40"
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/10 text-accent">
        {icon}
      </span>
      <p className="mt-4 font-semibold group-hover:text-accent">{title}</p>
      <p className="mt-1 text-sm text-text-secondary">{text}</p>
    </Link>
  );
}
