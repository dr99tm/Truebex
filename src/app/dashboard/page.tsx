"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, Laptop } from "lucide-react";
import {
  ErrorNote,
  PageHeader,
  Panel,
  useDashboardUser,
} from "@/components/dashboard/DashboardShell";
import { useApiData } from "@/components/dashboard/useApiData";
import { DownloadPanel } from "@/components/releases/DownloadPanel";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/lib/api";
import { logout } from "@/lib/auth";
import { planName } from "@/lib/plans";
import { getSubscription } from "@/lib/developer";
import { listDevices, removeDevice } from "@/lib/licence";
import { latestRelease } from "@/lib/releases";
import { daysUntil, timeAgo } from "@/lib/time";

const BETA_KEY = "truebex_beta_channel";

function readBetaChoice(): boolean {
  try {
    return window.localStorage.getItem(BETA_KEY) === "1";
  } catch {
    return false;
  }
}

export default function DashboardOverview() {
  const user = useDashboardUser();
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
      <div className="grid gap-6 lg:grid-cols-5">
        <DownloadCard />
        <LicenceCard />
      </div>
      <DevicesCard />
    </>
  );
}

function DownloadCard() {
  // The dashboard renders only in the browser (after /auth/me), so reading
  // the per-browser beta choice in the initial state is safe.
  const [beta, setBeta] = useState(readBetaChoice);
  const channel = beta ? "beta" : "stable";

  function toggle(next: boolean) {
    setBeta(next);
    try {
      window.localStorage.setItem(BETA_KEY, next ? "1" : "0");
    } catch {
      /* private mode: the choice lasts for this page only */
    }
  }

  return (
    <Panel className="lg:col-span-3">
      <div className="flex items-center justify-between gap-4">
        <h2 className="font-semibold">Download Truebex</h2>
        <Link href="/changelog/" className="text-sm text-accent hover:underline">
          What&apos;s new
        </Link>
      </div>
      <DownloadPanel key={channel} channel={channel} initial={latestRelease(channel)} compact className="mt-5" />
      <label className="mt-5 flex items-center gap-2 text-sm text-text-secondary">
        <input
          type="checkbox"
          checked={beta}
          onChange={(e) => toggle(e.target.checked)}
          className="h-4 w-4 accent-[var(--color-accent)]"
        />
        Show beta releases
      </label>
    </Panel>
  );
}

function LicenceCard() {
  const user = useDashboardUser();
  const sub = useApiData(getSubscription);
  const plan = sub.data?.tier ?? user.plan;
  const trial = sub.data?.provider === "trial";
  const end = sub.data?.current_period_end ?? null;
  const paid = plan !== "free" && !trial;

  let detail = "Free plan";
  if (trial && end) {
    const days = daysUntil(end);
    detail = `${days} ${days === 1 ? "day" : "days"} left · ends ${formatDate(end)}`;
  } else if (paid && (sub.data?.provider === "paddle" || sub.data?.provider === "stripe") && end) {
    detail = `${sub.data.cancel_at_period_end ? "Ends" : "Renews"} ${formatDate(end)}`;
  } else if (paid && sub.data?.provider === "wayl" && end) {
    detail = `Paid through ${formatDate(end)}`;
  } else if (paid) {
    detail = "Arranged for your account";
  }

  return (
    <Panel className="lg:col-span-2">
      <h2 className="font-semibold">Licence</h2>
      <p className="mt-4 text-3xl font-semibold">
        {planName(plan)}
        {trial && " trial"}
      </p>
      <p className="mt-1 text-sm text-text-secondary">{sub.loading && !sub.data ? "Loading…" : detail}</p>
      <p className="mt-1 text-sm text-text-muted">
        Seat: {trial ? "trial" : paid ? "personal" : "free"}
      </p>
      {sub.error && (
        <div className="mt-4">
          <ErrorNote message={sub.error} />
        </div>
      )}
      <Link
        href="/dashboard/billing/"
        className="mt-5 inline-flex items-center gap-1 text-sm text-accent hover:underline"
      >
        {paid ? "Manage billing" : "Upgrade to Pro"}
        <ArrowRight size={14} aria-hidden />
      </Link>
    </Panel>
  );
}

function DevicesCard() {
  const devices = useApiData(listDevices);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");
  const rows = devices.data?.devices ?? [];
  const limit = devices.data?.limit ?? null;

  async function remove(id: string) {
    setActionError("");
    try {
      await removeDevice(id);
      setConfirming(null);
      await devices.reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Couldn't remove the device.");
    }
  }

  return (
    <Panel className="mt-6">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="font-semibold">Devices</h2>
        {devices.data && limit !== null && (
          <p className="text-sm text-text-muted">
            {rows.length} of {limit} in use
          </p>
        )}
      </div>
      {(devices.error || actionError) && (
        <div className="mt-4">
          <ErrorNote message={actionError || devices.error || ""} />
        </div>
      )}
      {devices.loading && !devices.data ? (
        <p className="mt-4 text-sm text-text-muted">Loading…</p>
      ) : rows.length === 0 ? (
        <div className="mt-4">
          <p className="text-sm text-text-primary">No devices yet</p>
          <p className="mt-1 text-sm text-text-muted">Computers signed in to your account appear here.</p>
        </div>
      ) : (
        <ul className="mt-4 divide-y divide-border">
          {rows.map((d) => (
            <li key={d.device_id} className="flex flex-wrap items-center gap-4 py-3">
              <Laptop size={18} className="shrink-0 text-text-muted" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-text-primary">{d.name}</p>
                <p className="text-sm text-text-muted">
                  {[d.os, d.app_version && `Truebex ${d.app_version}`].filter(Boolean).join(" · ")} · last seen{" "}
                  {timeAgo(d.last_seen_at)}
                </p>
              </div>
              {confirming === d.device_id ? (
                <span className="inline-flex gap-3 text-sm">
                  <button className="text-red-400 hover:underline" onClick={() => remove(d.device_id)}>
                    Confirm remove
                  </button>
                  <button className="text-text-muted hover:underline" onClick={() => setConfirming(null)}>
                    Cancel
                  </button>
                </span>
              ) : (
                <button
                  className="text-sm text-text-muted hover:text-red-400"
                  onClick={() => setConfirming(d.device_id)}
                >
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
