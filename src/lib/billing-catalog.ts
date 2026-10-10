// The billing page's plan catalogue before GET /billing/plans answers, read
// at build time from the API's own file (server/app/catalogue.json): tier
// names, prices per interval and currency, and the founding offer. The
// dashboard refreshes it from the API after load (the founding count and
// which provider is live). Prices are the owner's pricing plan (PF2a).
import raw from "../../server/app/catalogue.json";
import type { Catalog, Interval, PlanInfo } from "@/lib/developer";

export const CATALOGUE_TIERS: PlanInfo[] = raw.tiers.map((t) => ({
  id: t.id,
  name: t.name,
  purchasable: t.purchasable,
  per_seat: t.per_seat,
  min_seats: t.min_seats,
  prices: t.prices.map((p) => ({
    interval: p.interval as Interval,
    currency: p.currency,
    amount_minor: p.amount_minor,
  })),
}));

/** What the billing page shows before /billing/plans answers: no provider,
 *  so nothing can be bought until the API confirms one. */
export const STATIC_CATALOG: Catalog = {
  tiers: CATALOGUE_TIERS,
  founding: {
    enabled: false,
    total: raw.founding.total,
    remaining: raw.founding.total,
    discount_percent: raw.founding.discount_percent,
    ends_at: raw.founding.ends_at,
    tiers: [...raw.founding.tiers],
    intervals: raw.founding.intervals.map((i) => i as Interval),
  },
  provider: null,
  currencies: [...raw.currencies],
};
