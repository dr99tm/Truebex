"use client";

import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import {
  fill,
  formatMinor,
  foundingCovers,
  foundingPrice,
  priceOf,
  type Currency,
  type Founding,
  type Tier,
} from "@/lib/catalogue";

interface LiveFounding {
  enabled?: boolean;
  total?: number | null;
  remaining?: number | null;
}

export interface FoundingCopy {
  title: string;
  body: string;
  /** "{list}": each founding tier's annual founding price. */
  prices: string;
  /** Joins the last two prices of the list. */
  and: string;
  left: string;
  ends: string;
}

/**
 * The founding offer from the catalogue (build time), with the seats left
 * refreshed from GET /billing/plans after load. Reads well without the API:
 * the count is the only number that waits for it. The founding prices are
 * the annual prices of the offer's tiers, `discount_percent` off, in the
 * currency the tier cards show.
 */
export function FoundingBanner({
  founding,
  copy,
  tiers,
  currency,
  perSeat,
}: {
  founding: Founding;
  copy: FoundingCopy;
  tiers: Tier[];
  currency: Currency;
  perSeat: string;
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
  const pct = founding.discount_percent ?? 0;
  const values = { total, pct };
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
  const prices = tiers.flatMap((t) => {
    const year = priceOf(t, "year", currency);
    if (!year || !foundingCovers(founding, t.id, "year")) return [];
    return [{ tier: t, amount: foundingPrice(year.amount_minor, pct) }];
  });

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
        {prices.length > 0 && (
          <p className="mt-1 text-sm text-text-secondary" data-founding-prices="">
            {(() => {
              const [before, after] = copy.prices.split("{list}");
              return (
                <>
                  {before}
                  {prices.map(({ tier, amount }, i) => (
                    <span key={tier.id}>
                      {i > 0 && (i === prices.length - 1 ? ` ${copy.and} ` : ", ")}
                      {tier.name}{" "}
                      <span
                        className="font-medium text-text-primary"
                        data-founding-minor={String(amount)}
                        data-tier={tier.id}
                        data-currency={currency}
                      >
                        {formatMinor(amount, currency)}
                      </span>
                      {tier.per_seat && ` ${perSeat}`}
                    </span>
                  ))}
                  {after}
                </>
              );
            })()}
          </p>
        )}
        {typeof live?.remaining === "number" && (
          <p className="mt-2 text-sm font-medium text-accent" role="status">
            {fill(copy.left, { ...values, remaining: live.remaining })}
          </p>
        )}
      </div>
    </div>
  );
}
