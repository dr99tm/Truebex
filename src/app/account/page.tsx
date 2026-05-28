"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  LayoutGrid,
  Boxes,
  Headset,
  Settings,
  ArrowRight,
} from "lucide-react";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { fetchMe, logout, type User } from "@/lib/auth";

const FEATURES = [
  {
    icon: LayoutGrid,
    title: "Projects",
    description: "Create and manage your building projects in one workspace.",
  },
  {
    icon: Boxes,
    title: "Designs",
    description: "Browse the market for real materials and drop them into designs.",
  },
  {
    icon: Headset,
    title: "VR Sessions",
    description: "Step inside your spaces and experience them at true scale.",
  },
  {
    icon: Settings,
    title: "Settings",
    description: "Manage your account, team, and workspace preferences.",
  },
] as const;

export default function AccountPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMe()
      .then((u) => {
        if (!u) {
          router.replace("/login");
          return;
        }
        setUser(u);
      })
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  function handleLogout() {
    logout();
    router.replace("/");
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center px-4">
        <p className="text-text-secondary">Loading…</p>
      </main>
    );
  }

  if (!user) return null;

  const name = user.email.split("@")[0];
  const memberSince = new Date(user.created_at).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <main className="min-h-screen px-4 pb-24 pt-28 md:px-8">
      <div className="mx-auto max-w-5xl">
        {/* Welcome header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm text-text-muted">Welcome back,</p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight sm:text-4xl">
              <span className="gradient-text">{name}</span>
            </h1>
          </div>
          <Button variant="secondary" size="sm" onClick={handleLogout}>
            Log out
          </Button>
        </div>

        {/* Profile summary */}
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          <GlassCard className="sm:col-span-1">
            <p className="text-sm text-text-muted">Email</p>
            <p className="mt-1 truncate font-medium text-text-primary">
              {user.email}
            </p>
          </GlassCard>
          <GlassCard className="sm:col-span-1">
            <p className="text-sm text-text-muted">Member since</p>
            <p className="mt-1 font-medium text-text-primary">{memberSince}</p>
          </GlassCard>
          <GlassCard className="sm:col-span-1">
            <p className="text-sm text-text-muted">Plan</p>
            <p className="mt-1 font-medium capitalize text-text-primary">
              {user.plan}
            </p>
            {user.plan === "free" && (
              <a
                href="/payments/callback"
                className="mt-3 inline-flex items-center gap-1 text-sm text-accent hover:underline"
              >
                Upgrade to Pro →
              </a>
            )}
          </GlassCard>
        </div>

        {/* Feature grid */}
        <h2 className="mt-12 text-lg font-semibold text-text-primary">
          Your workspace
        </h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <GlassCard key={title} className="flex flex-col">
              <div className="flex h-11 w-11 items-center justify-center rounded-[var(--radius-button)] bg-accent/10 text-accent">
                <Icon size={20} />
              </div>
              <h3 className="mt-4 font-semibold text-text-primary">{title}</h3>
              <p className="mt-1 flex-1 text-sm text-text-secondary">
                {description}
              </p>
              <span className="mt-4 inline-flex items-center gap-1 text-sm text-accent opacity-70">
                Coming soon
                <ArrowRight size={14} />
              </span>
            </GlassCard>
          ))}
        </div>
      </div>
    </main>
  );
}
