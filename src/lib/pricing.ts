// Server-side pricing helpers: the FAQ entries that apply to the catalogue,
// and the SoftwareApplication JSON-LD shared by the home and pricing pages.
import { anyPriced, fill, foundingLive, offersLd, type Catalogue } from "@/lib/catalogue";
import { FEATURES, PRICING, PRODUCT_SHOT, SITE } from "@/lib/constants";

/** The pricing FAQ for this catalogue, with its numbers filled in. */
export function pricingFaq(catalogue: Catalogue): { q: string; a: string }[] {
  const seatTier = catalogue.tiers.find((t) => t.per_seat) ?? catalogue.tiers[0];
  const values = {
    devices: seatTier?.limits.devices ?? 2,
    total: catalogue.founding?.total ?? 0,
    pct: catalogue.founding?.discount_percent ?? 0,
  };
  return PRICING.faq
    .filter((f) => {
      if (!("when" in f)) return true;
      if (f.when === "founding") return foundingLive(catalogue);
      if (f.when === "unpriced") return !anyPriced(catalogue);
      return true;
    })
    .map((f) => ({ q: f.q, a: fill(f.a, values) }));
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
