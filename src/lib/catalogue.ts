// The plan catalogue's shape and the helpers the pricing UI shares between
// server and client. The data is server/app/catalogue.json (PF1's file;
// prices and the founding offer are PF2's fields), loaded at build time by
// src/lib/catalogue-data.ts (public pages) and src/lib/billing-catalog.ts
// (the billing page's fallback). Safe to import from client components.

export type Interval = "month" | "year";
export type Currency = "GBP" | "USD" | "EUR";

export const CURRENCIES: readonly Currency[] = ["GBP", "USD", "EUR"];
export const DEFAULT_CURRENCY: Currency = "GBP";
export const INTERVALS: readonly Interval[] = ["month", "year"];

export interface Price {
  interval: Interval;
  currency: Currency;
  amount_minor: number;
}

export interface Tier {
  id: string;
  name: string;
  rank: number;
  purchasable: boolean;
  per_seat: boolean;
  min_seats: number;
  features: string[];
  limits: Record<string, number | null>;
  api: { monthly_requests: number; max_api_keys: number };
  prices: Price[];
}

export interface Founding {
  total: number | null;
  discount_percent: number | null;
  ends_at: string | null;
  /** The tiers with a founding price. */
  tiers?: string[];
  /** The billing intervals with a founding price; absent = both. */
  intervals?: Interval[];
}

export interface Catalogue {
  tiers: Tier[];
  founding: Founding | null;
  /** PF2: false while prices and the founding offer are placeholders;
   *  absent counts as final. PF2a set the owner's prices (true). */
  prices_final?: boolean;
}

/**
 * What the public pages show: the catalogue's prices and founding offer only
 * once they are final. Placeholder prices stay off /pricing/, the home teaser
 * and the JSON-LD offers (every paid tier reads "Price at launch"); the
 * billing page still lists them from GET /billing/plans.
 */
export function publicCatalogue(catalogue: Catalogue): Catalogue {
  if (catalogue.prices_final !== false) return catalogue;
  return {
    ...catalogue,
    tiers: catalogue.tiers.map((t) => ({ ...t, prices: [] })),
    founding: null,
  };
}

export function priceOf(tier: Tier, interval: Interval, currency: Currency): Price | undefined {
  return tier.prices.find((p) => p.interval === interval && p.currency === currency);
}

export function isPriced(tier: Tier): boolean {
  return tier.prices.length > 0;
}

/**
 * The interval a tier is shown and sold at: the one asked for when the tier
 * has a price there, else the one it has. Team is annual only, so its
 * Monthly view shows (and its checkout link buys) the annual price.
 */
export function intervalFor(
  tier: { prices: readonly { interval: Interval; currency: string }[] },
  interval: Interval,
  currency: string
): Interval {
  const has = (iv: Interval) => tier.prices.some((p) => p.interval === iv && p.currency === currency);
  if (has(interval)) return interval;
  const other: Interval = interval === "month" ? "year" : "month";
  return has(other) ? other : interval;
}

/** What an annual charge comes to per month, billed annually: the charge
 *  divided by 12, to the nearest minor unit (£1,190 a year → £99.17). */
export function perMonthOfYear(amountMinor: number): number {
  return Math.round(amountMinor / 12);
}

export function anyPriced(catalogue: Catalogue): boolean {
  return catalogue.tiers.some(isPriced);
}

/** The founding block shows only once the catalogue has its numbers. */
export function foundingLive(catalogue: Catalogue): boolean {
  const f = catalogue.founding;
  return !!f && !!f.total && f.discount_percent !== null && f.discount_percent !== undefined;
}

// One locale per currency so the symbol reads naturally: £24, $29, €27.
const LOCALE: Record<Currency, string> = { GBP: "en-GB", USD: "en-US", EUR: "en-IE" };

/** Minor units to a display price; pence/cents only when there are any. */
export function formatMinor(amountMinor: number, currency: Currency): string {
  const whole = amountMinor % 100 === 0;
  return new Intl.NumberFormat(LOCALE[currency], {
    style: "currency",
    currency,
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: whole ? 0 : 2,
  }).format(amountMinor / 100);
}

/** Largest annual saving across tiers and currencies, in whole percent. */
export function annualSavingPercent(catalogue: Catalogue): number | null {
  let best: number | null = null;
  for (const tier of catalogue.tiers) {
    for (const year of tier.prices.filter((p) => p.interval === "year")) {
      const month = priceOf(tier, "month", year.currency);
      if (!month || month.amount_minor <= 0) continue;
      const pct = Math.round((1 - year.amount_minor / (12 * month.amount_minor)) * 100);
      if (pct > 0 && (best === null || pct > best)) best = pct;
    }
  }
  return best;
}

/** The founding price of a seat listed at `amountMinor` (as the API rounds). */
export function foundingPrice(amountMinor: number, discountPercent: number): number {
  return Math.floor((amountMinor * (100 - discountPercent) + 50) / 100);
}

/** Whether the founding offer prices `tierId` billed every `interval`
 *  (server/app/plans.py FoundingOffer.covers). */
export function foundingCovers(
  founding: { tiers?: readonly string[]; intervals?: readonly string[] } | null | undefined,
  tierId: string,
  interval: Interval
): boolean {
  if (!founding) return false;
  return (founding.tiers ?? []).includes(tierId) && (founding.intervals ?? INTERVALS).includes(interval);
}

/** Replace {token}s in a copy string. */
export function fill(text: string, values: Record<string, string | number>): string {
  return text.replace(/\{(\w+)\}/g, (m, k: string) => (k in values ? String(values[k]) : m));
}

/** schema.org Offers for the SoftwareApplication JSON-LD: Free at 0, then
 *  one Offer per priced tier, interval and currency. */
export function offersLd(catalogue: Catalogue, url: string): object[] {
  const offers: object[] = [];
  const free = catalogue.tiers.find((t) => t.id === "free");
  if (free) {
    offers.push({
      "@type": "Offer",
      name: free.name,
      price: "0",
      priceCurrency: DEFAULT_CURRENCY,
      url,
    });
  }
  for (const tier of catalogue.tiers) {
    for (const p of tier.prices) {
      const price = (p.amount_minor / 100).toFixed(2);
      offers.push({
        "@type": "Offer",
        name: `${tier.name} (${p.interval === "month" ? "monthly" : "annual"})`,
        price,
        priceCurrency: p.currency,
        url,
        priceSpecification: {
          "@type": "UnitPriceSpecification",
          price,
          priceCurrency: p.currency,
          unitCode: p.interval === "month" ? "MON" : "ANN",
          ...(tier.per_seat ? { referenceQuantity: { "@type": "QuantitativeValue", value: 1, unitText: "seat" } } : {}),
        },
      });
    }
  }
  return offers;
}
