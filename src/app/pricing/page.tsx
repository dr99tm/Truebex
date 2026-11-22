import type { Metadata } from "next";
import { Footer } from "@/components/layout/Footer";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { FaqList } from "@/components/sections/FaqList";
import { TierCards } from "@/components/pricing/TierCards";
import { ComparisonTable } from "@/components/pricing/ComparisonTable";
import { annualSavingPercent, foundingLive } from "@/lib/catalogue";
import { loadCatalogue } from "@/lib/catalogue-data";
import { ContactButtons } from "@/components/sections/ContactButtons";
import { CONTACT_CTA, PRELAUNCH, PRELAUNCH_PLANS, PRICING } from "@/lib/constants";
import { pricingFaq, softwareApplicationLd } from "@/lib/pricing";
import { breadcrumbLd, faqLd, ldJson, pageMetadata, webPageLd } from "@/lib/seo";

// Pre-launch: the address stays (old links land here), but the page is a
// short note with the contact buttons: no plans, no prices, noindex and no
// canonical, and it is in neither the sitemap nor any menu.
export const metadata: Metadata = PRELAUNCH.hidePricing
  ? { title: PRELAUNCH_PLANS.title, description: PRELAUNCH_PLANS.description, robots: { index: false, follow: true } }
  : pageMetadata({
      title: PRICING.title,
      description: PRICING.description,
      path: "/pricing/",
    });

function PlansAtLaunch() {
  return (
    <>
      <main className="mx-auto max-w-7xl px-4 pb-24 pt-28 md:px-8" data-prelaunch="plans">
        <header className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-medium uppercase tracking-wider text-accent">{PRELAUNCH_PLANS.eyebrow}</p>
          <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-5xl">{PRELAUNCH_PLANS.heading}</h1>
          <p className="mt-5 text-lg text-text-secondary">{PRELAUNCH_PLANS.intro}</p>
          <ContactButtons copy={CONTACT_CTA} />
        </header>
      </main>
      <Footer />
    </>
  );
}

export default function PricingPage() {
  return PRELAUNCH.hidePricing ? <PlansAtLaunch /> : <FullPricing />;
}

function FullPricing() {
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
          <TierCards
            tiers={catalogue.tiers}
            copy={PRICING.tiers}
            labels={PRICING.labels}
            saving={annualSavingPercent(catalogue)}
            showControls
            founding={
              foundingLive(catalogue) && catalogue.founding
                ? { offer: catalogue.founding, copy: PRICING.founding }
                : null
            }
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
