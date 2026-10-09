"use client";

import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { fill, type Founding } from "@/lib/catalogue";

interface LiveFounding {
  enabled?: boolean;
  total?: number | null;
  remaining?: number | null;
}

/**
 * The founding offer from the catalogue (build time), with the seats left
 * refreshed from GET /billing/plans after load. Reads well without the API:
 * the count is the only number that waits for it.
 */
export function FoundingBanner({
  founding,
  copy,
}: {
  founding: Founding;
  copy: { title: string; body: string; left: string; ends: string };
}) {
  const [live, setLive] = useState<LiveFounding | null>(null);

  useEffect(() => {
    let cancelled = false;
    api<{ founding?: LiveFounding }>("/billing/plans", { auth: false })
      .then((data) => {
        if (!cancelled && data && typeof data.founding === "object" && data.founding) setLive(data.founding);
      })
      .catch(() => {
        /* offline or an older API: keep the build-time text */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (live?.enabled === false) return null;
  const total = live?.total ?? founding.total ?? 0;
  const values = { total, pct: founding.discount_percent ?? 0 };
  const ends = founding.ends_at
    ? fill(copy.ends, {
        date: new Date(founding.ends_at).toLocaleDateString("en-GB", {
          day: "numeric",
          month: "long",
          year: "numeric",
          timeZone: "UTC",
        }),
      })
    : "";

  return (
    <div
      data-founding=""
      className="mx-auto mb-10 flex max-w-3xl items-start gap-4 rounded-[var(--radius-card)] border border-accent/30 bg-accent/5 p-5"
    >
      <Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-accent" aria-hidden />
      <div>
        <p className="font-semibold text-text-primary">{copy.title}</p>
        <p className="mt-1 text-sm text-text-secondary">
          {fill(copy.body, values)} {ends}
        </p>
        {typeof live?.remaining === "number" && (
          <p className="mt-2 text-sm font-medium text-accent" role="status">
            {fill(copy.left, { ...values, remaining: live.remaining })}
          </p>
        )}
      </div>
    </div>
  );
}
