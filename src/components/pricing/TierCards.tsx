"use client";

import { useState, useSyncExternalStore } from "react";
import { Check } from "lucide-react";
import { FoundingBanner, type FoundingCopy } from "@/components/pricing/FoundingBanner";
import {
  CURRENCIES,
  DEFAULT_CURRENCY,
  fill,
  formatMinor,
  intervalFor,
  isPriced,
  perMonthOfYear,
  priceOf,
  type Currency,
  type Founding,
  type Interval,
  type Price,
  type Tier,
} from "@/lib/catalogue";
import type { PricingHighlight, TierCopy } from "@/lib/constants";
import { cn } from "@/lib/utils";

export type PricingLabels = Record<
  | "interval" | "month" | "year" | "saveUpTo" | "currency" | "perMonth" | "perMonthAnnual"
  | "perYear" | "orYear" | "perSeat" | "fromSeats" | "priceAtLaunch" | "startFree"
  | "free" | "freeNote" | "custom" | "customNote" | "mostPopular" | "onTheRoadmap",
  string
>;

const CURRENCY_KEY = "truebex_currency";
const EURO_REGIONS = new Set([
  "AT", "BE", "CY", "DE", "EE", "ES", "FI", "FR", "GR", "HR", "IE", "IT", "LT", "LU",
  "LV", "MT", "NL", "PT", "SI", "SK",
]);

/** The visitor's saved choice, else a guess from the browser's locale. */
function preferredCurrency(): Currency | null {
  try {
    const saved = window.localStorage.getItem(CURRENCY_KEY);
    if (saved && (CURRENCIES as readonly string[]).includes(saved)) return saved as Currency;
  } catch {
    /* storage blocked */
  }
  const region = (navigator.language || "").split("-")[1]?.toUpperCase();
  if (!region) return null;
  if (region === "GB") return "GBP";
  if (EURO_REGIONS.has(region)) return "EUR";
  return "USD";
}

const nf = new Intl.NumberFormat("en-US");
const subscribeNever = () => () => {};

function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { value: T; label: React.ReactNode }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex rounded-full border border-border bg-surface p-1"
    >
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-full px-4 py-1.5 text-sm transition-colors",
            value === o.value
              ? "bg-accent text-background"
              : "text-text-secondary hover:text-text-primary"
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/**
 * A tier's price for the chosen interval and currency. Every figure is a
 * charge or follows from one: a monthly price (with the annual price beside
 * it), or an annual price with what it comes to per month, billed annually.
 * A tier without the chosen interval shows the one it has (Team is annual
 * only, so its Monthly view is the annual charge / 12, billed annually).
 * Listed amounts carry `data-amount-minor`; figures worked out from one
 * carry `data-derived` (the build checks read both).
 */
export function PriceBlock({
  tier,
  interval,
  currency,
  labels,
}: {
  tier: Tier;
  interval: Interval;
  currency: Currency;
  labels: PricingLabels;
}) {
  const big = "text-4xl font-bold tracking-tight";
  const small = "mt-1 text-sm text-text-muted";

  if (tier.id === "free") {
    return (
      <div>
        <p className={big}>{labels.free}</p>
        <p className={small}>{labels.freeNote}</p>
      </div>
    );
  }
  const price = priceOf(tier, intervalFor(tier, interval, currency), currency);
  if (!isPriced(tier) || !price) {
    if (!tier.purchasable) {
      return (
        <div>
          <p className={big}>{labels.custom}</p>
          <p className={small}>{labels.customNote}</p>
        </div>
      );
    }
    return (
      <div>
        <p className="text-2xl font-semibold tracking-tight text-text-primary" data-price-status="launch">
          {labels.priceAtLaunch}
        </p>
        {tier.per_seat && <p className={small}>{labels.perSeat}</p>}
      </div>
    );
  }

  const listed = (p: Price) => (
    <span
      data-amount-minor={String(p.amount_minor)}
      data-tier={tier.id}
      data-interval={p.interval}
      data-currency={p.currency}
    >
      {formatMinor(p.amount_minor, currency)}
    </span>
  );
  const derived = (minor: number) => <span data-derived="">{formatMinor(minor, currency)}</span>;
  const withAmount = (template: string, amount: React.ReactNode) => {
    const [before, after] = template.split("{amount}");
    return (
      <>
        {before}
        {amount}
        {after}
      </>
    );
  };
  const seat = tier.per_seat
    ? ` · ${labels.perSeat}${tier.min_seats > 1 ? ` · ${fill(labels.fromSeats, { n: tier.min_seats })}` : ""}`
    : "";

  if (price.interval === "month") {
    const year = priceOf(tier, "year", currency);
    return (
      <div>
        <p className="flex items-baseline gap-2">
          <span className={big}>{listed(price)}</span>
          <span className="text-sm text-text-muted">
            {labels.perMonth}
            {seat}
          </span>
        </p>
        {year && <p className={small}>{withAmount(labels.orYear, listed(year))}</p>}
      </div>
    );
  }
  return (
    <div>
      <p className="flex items-baseline gap-2">
        <span className={big}>{derived(perMonthOfYear(price.amount_minor))}</span>
        <span className="text-sm text-text-muted">
          {labels.perMonthAnnual}
          {seat}
        </span>
      </p>
      <p className={small}>{withAmount(labels.perYear, listed(price))}</p>
    </div>
  );
}

function Highlight({ item, api, labels }: { item: PricingHighlight; api: string; labels: PricingLabels }) {
  if (typeof item === "string") {
    return (
      <li className="flex items-start gap-3 text-sm text-text-secondary">
        <Check className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden />
        <span>{fill(item, { api })}</span>
      </li>
    );
  }
  return (
    <li className="flex items-start gap-3 text-sm text-text-muted">
      <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full border border-warn" aria-hidden />
      <span>
        {item.text}{" "}
        <span className="whitespace-nowrap text-xs font-medium text-warn">· {labels.onTheRoadmap}</span>
      </span>
    </li>
  );
}

export function TierCards({
  tiers,
  copy,
  labels,
  saving,
  showControls,
  founding,
  headingLevel = "h2",
  className,
}: {
  tiers: Tier[];
  copy: Record<string, TierCopy & { name?: string }>;
  labels: PricingLabels;
  saving: number | null;
  showControls: boolean;
  /** The founding offer's banner, in the chosen currency (/pricing/). */
  founding?: { offer: Founding; copy: FoundingCopy } | null;
  headingLevel?: "h2" | "h3";
  className?: string;
}) {
  const [interval, setPeriod] = useState<Interval>("month");
  const [chosen, setChosen] = useState<Currency | null>(null);
  // The visitor's currency on the client; the static HTML carries the
  // default, so crawlers and no-JS visitors see GBP.
  const detected = useSyncExternalStore(
    subscribeNever,
    () => (showControls ? preferredCurrency() : null) ?? DEFAULT_CURRENCY,
    () => DEFAULT_CURRENCY
  );
  const currency = chosen ?? detected;
  const Heading = headingLevel;

  const chooseCurrency = (c: Currency) => {
    setChosen(c);
    try {
      window.localStorage.setItem(CURRENCY_KEY, c);
    } catch {
      /* storage blocked: the choice lasts for this page view */
    }
  };

  return (
    <div className={className}>
      {founding && (
        <FoundingBanner
          founding={founding.offer}
          copy={founding.copy}
          tiers={tiers}
          currency={currency}
          perSeat={labels.perSeat}
        />
      )}
      {showControls && (
        <div className="mb-10 flex flex-col items-center justify-center gap-3 sm:flex-row sm:gap-6">
          <Segmented<Interval>
            label={labels.interval}
            value={interval}
            onChange={setPeriod}
            options={[
              { value: "month", label: labels.month },
              {
                value: "year",
                label: (
                  <>
                    {labels.year}
                    {saving !== null && (
                      <span className="ms-1.5 text-xs opacity-80">{fill(labels.saveUpTo, { pct: saving })}</span>
                    )}
                  </>
                ),
              },
            ]}
          />
          <Segmented<Currency>
            label={labels.currency}
            value={currency}
            onChange={chooseCurrency}
            options={CURRENCIES.map((c) => ({ value: c, label: c }))}
          />
        </div>
      )}

      <div
        className={cn(
          "grid items-stretch gap-6",
          tiers.length >= 5
            ? "sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5"
            : "mx-auto max-w-5xl sm:grid-cols-2 lg:grid-cols-3"
        )}
      >
        {tiers.map((tier) => {
          const c = copy[tier.id];
          if (!c) return null;
          const name = c.name ?? tier.name;
          // Team is annual only: its link buys the annual price.
          const sold = intervalFor(tier, interval, currency);
          const priced = isPriced(tier) && !!priceOf(tier, sold, currency);
          const cta = priced && tier.purchasable
            ? {
                label: c.cta,
                href: `/dashboard/billing/?tier=${tier.id}&interval=${sold}&currency=${currency}`,
              }
            : c.href
              ? { label: c.cta, href: c.href }
              : { label: labels.startFree, href: "/signup/" };
          return (
            <div key={tier.id} className="relative h-full pt-4">
              {c.highlighted && (
                <span className="absolute left-1/2 top-0 z-20 -translate-x-1/2 whitespace-nowrap rounded-full bg-accent px-4 py-1 text-xs font-semibold text-background">
                  {labels.mostPopular}
                </span>
              )}
              <article
                data-tier={tier.id}
                className={cn(
                  "flex h-full flex-col rounded-[var(--radius-card)] border bg-[var(--color-glass)] p-6 backdrop-blur-[12px]",
                  c.highlighted ? "border-accent/30" : "border-[var(--color-glass-border)]"
                )}
              >
                <Heading className="text-lg font-semibold">{name}</Heading>
                <div className="mt-3 min-h-[5.5rem]">
                  <PriceBlock tier={tier} interval={interval} currency={currency} labels={labels} />
                </div>
                <p className="mt-3 text-sm text-text-secondary">{c.description}</p>
                <ul className="mb-8 mt-6 flex-1 space-y-3">
                  {c.highlights.map((h) => (
                    <Highlight
                      key={typeof h === "string" ? h : h.text}
                      item={h}
                      api={nf.format(tier.api.monthly_requests)}
                      labels={labels}
                    />
                  ))}
                </ul>
                <a
                  href={cta.href}
                  className={cn(
                    "inline-flex h-10 w-full items-center justify-center rounded-[var(--radius-button)] px-6 text-sm font-medium transition-all duration-300",
                    c.highlighted
                      ? "bg-accent text-background hover:bg-accent-hover"
                      : "border border-accent text-accent hover:bg-accent hover:text-background"
                  )}
                >
                  {cta.label}
                </a>
              </article>
            </div>
          );
        })}
      </div>
    </div>
  );
}
