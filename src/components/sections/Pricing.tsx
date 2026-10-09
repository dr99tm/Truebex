import { Section } from "@/components/layout/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { FadeInWhenVisible } from "@/components/animations/FadeInWhenVisible";
import { TierCards } from "@/components/pricing/TierCards";
import { annualSavingPercent, anyPriced } from "@/lib/catalogue";
import { loadCatalogue } from "@/lib/catalogue-data";
import { PRICING } from "@/lib/constants";
import { pickTiers } from "@/lib/pricing";

/** The home page's three-tier teaser, from the same catalogue as /pricing/. */
export function Pricing() {
  const catalogue = loadCatalogue();
  const priced = anyPriced(catalogue);
  return (
    <Section id="pricing">
      <FadeInWhenVisible>
        <SectionHeading title={PRICING.teaserTitle} subtitle={PRICING.teaserSubtitle} />
      </FadeInWhenVisible>

      <TierCards
        tiers={pickTiers(catalogue, PRICING.teaser)}
        copy={PRICING.tiers}
        labels={PRICING.labels}
        saving={annualSavingPercent(catalogue)}
        showControls={priced}
        headingLevel="h3"
      />

      <p className="mt-10 text-center">
        <a
          href="/pricing/"
          className="inline-flex h-10 items-center justify-center rounded-[var(--radius-button)] border border-accent px-6 text-sm font-medium text-accent transition-all duration-300 hover:bg-accent hover:text-background"
        >
          {PRICING.seeAll}
        </a>
      </p>
    </Section>
  );
}
