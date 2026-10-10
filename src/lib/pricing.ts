// Server-side pricing helpers: the FAQ entries that apply to the catalogue,
// and the SoftwareApplication JSON-LD shared by the home and pricing pages.
import { anyPriced, fill, foundingLive, offersLd, type Catalogue } from "@/lib/catalogue";
import { FEATURES, PRICING, PRODUCT_SHOT, SITE } from "@/lib/constants";

/** Names joined as a list: "Pro, Studio and Team". */
function nameList(names: string[]): string {
  if (names.length < 2) return names.join("");
  return `${names.slice(0, -1).join(", ")} ${PRICING.founding.and} ${names[names.length - 1]}`;
}

/** The pricing FAQ for this catalogue, with its numbers filled in. */
export function pricingFaq(catalogue: Catalogue): { q: string; a: string }[] {
  const seatTier = catalogue.tiers.find((t) => t.per_seat && t.purchasable) ?? catalogue.tiers[0];
  const founding = catalogue.founding;
  // Paid tiers sold only by the year (Team).
  const annualOnly = catalogue.tiers.filter(
    (t) => t.prices.some((p) => p.interval === "year") && !t.prices.some((p) => p.interval === "month")
  );
  const values = {
    devices: seatTier?.limits.devices ?? 2,
    min: seatTier?.min_seats ?? 1,
    total: founding?.total ?? 0,
    pct: founding?.discount_percent ?? 0,
    tiers: nameList(
      catalogue.tiers.filter((t) => (founding?.tiers ?? []).includes(t.id)).map((t) => t.name)
    ),
    ends: founding?.ends_at
      ? new Date(founding.ends_at).toLocaleDateString("en-GB", {
          day: "numeric",
          month: "long",
          year: "numeric",
          timeZone: "UTC",
        })
      : "",
    annualOnly: nameList(annualOnly.map((t) => t.name)),
  };
  return PRICING.faq
    .filter((f) => {
      if (!("when" in f)) return true;
      if (f.when === "founding") return foundingLive(catalogue);
      if (f.when === "unpriced") return !anyPriced(catalogue);
      if (f.when === "annualOnly") return annualOnly.length > 0;
      return true;
    })
    .map((f) => ({ q: fill(f.q, values), a: fill(f.a, values) }));
}

/** The tiers named in `ids`, in that order (the home teasers). */
export function pickTiers(catalogue: Catalogue, ids: readonly string[]) {
  return ids
    .map((id) => catalogue.tiers.find((t) => t.id === id))
    .filter((t): t is Catalogue["tiers"][number] => !!t);
}

export function softwareApplicationLd(catalogue: Catalogue): object {
  return {
    "@type": "SoftwareApplication",
    "@id": `${SITE.url}/#software`,
    name: "Truebex",
    url: SITE.url,
    applicationCategory: "DesignApplication",
    applicationSubCategory: "Building design",
    operatingSystem: "Windows",
    description: SITE.description,
    image: `${SITE.url}/images/og-image.jpg`,
    screenshot: `${SITE.url}${PRODUCT_SHOT.src}`,
    featureList: FEATURES.map((f) => f.title),
    publisher: { "@id": `${SITE.url}/#organization` },
    offers: offersLd(catalogue, `${SITE.url}/pricing/`),
  };
}
