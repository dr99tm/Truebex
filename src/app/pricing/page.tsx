import type { Metadata } from "next";
import { Footer } from "@/components/layout/Footer";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { FaqList } from "@/components/sections/FaqList";
import { TierCards } from "@/components/pricing/TierCards";
import { FoundingBanner } from "@/components/pricing/FoundingBanner";
import { ComparisonTable } from "@/components/pricing/ComparisonTable";
import { annualSavingPercent, foundingLive } from "@/lib/catalogue";
import { loadCatalogue } from "@/lib/catalogue-data";
import { PRICING } from "@/lib/constants";
import { pricingFaq, softwareApplicationLd } from "@/lib/pricing";
import { breadcrumbLd, faqLd, ldJson, pageMetadata, webPageLd } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: PRICING.title,
  description: PRICING.description,
  path: "/pricing/",
});

export default function PricingPage() {
  const catalogue = loadCatalogue();
  const faq = pricingFaq(catalogue);
  const ld = ldJson([
    webPageLd({ name: PRICING.heading, description: PRICING.description, path: "/pricing/" }),
    breadcrumbLd([
      { name: "Truebex", path: "/" },
      { name: PRICING.title, path: "/pricing/" },
    ]),
    softwareApplicationLd(catalogue),
    faqLd(faq),
  ]);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ld }} />
      <main className="mx-auto max-w-7xl px-4 pb-24 pt-28 md:px-8">
        <header className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-medium uppercase tracking-wider text-accent">{PRICING.eyebrow}</p>
          <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-5xl">{PRICING.heading}</h1>
          <p className="mt-5 text-lg text-text-secondary">{PRICING.intro}</p>
        </header>

        <div className="mt-12">
          {foundingLive(catalogue) && catalogue.founding && (
            <FoundingBanner founding={catalogue.founding} copy={PRICING.founding} />
          )}
          <TierCards
            tiers={catalogue.tiers}
            copy={PRICING.tiers}
            labels={PRICING.labels}
            saving={annualSavingPercent(catalogue)}
            showControls
          />
        </div>

        <section className="mt-24">
          <SectionHeading title={PRICING.comparisonTitle} subtitle={PRICING.comparisonSubtitle} className="sm:mb-10" />
          <ComparisonTable tiers={catalogue.tiers} />
        </section>

        <section className="mt-24">
          <SectionHeading title={PRICING.faqTitle} subtitle={PRICING.faqSubtitle} className="sm:mb-10" />
          <FaqList items={faq} />
        </section>
      </main>
      <Footer />
    </>
  );
}
