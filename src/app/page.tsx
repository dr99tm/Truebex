import type { Metadata } from "next";
import { Hero } from "@/components/sections/Hero";
import { WhatIsTruebex } from "@/components/sections/WhatIsTruebex";
import { CoreFeatures } from "@/components/sections/CoreFeatures";
import { HowItWorks } from "@/components/sections/HowItWorks";
import { WhoItsFor } from "@/components/sections/WhoItsFor";
import { WhatMakesItDifferent } from "@/components/sections/WhatMakesItDifferent";
import { Pricing } from "@/components/sections/Pricing";
import { FAQ } from "@/components/sections/FAQ";
import { CTAContact } from "@/components/sections/CTAContact";
import { Footer } from "@/components/layout/Footer";
import { loadCatalogue } from "@/lib/catalogue-data";
import { FAQS } from "@/lib/constants";
import { softwareApplicationLd } from "@/lib/pricing";
import { faqLd, HOME_LANGUAGES, ldJson } from "@/lib/seo";

// The English home is paired with the Arabic landing page (hreflang).
export const metadata: Metadata = {
  alternates: { canonical: "/", languages: HOME_LANGUAGES },
};

export default function Home() {
  // Structured data: the product (SoftwareApplication, offers from the plan
  // catalogue) and the FAQ, which can earn rich results in Google. Built from
  // the same constants as the visible content so the two stay in step.
  const homeLd = ldJson([softwareApplicationLd(loadCatalogue()), faqLd(FAQS)]);
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: homeLd }} />
      <main>
        <Hero />
        <WhatIsTruebex />
        <CoreFeatures />
        <HowItWorks />
        <WhoItsFor />
        <WhatMakesItDifferent />
        <Pricing />
        <FAQ />
        <CTAContact />
      </main>
      <Footer />
    </>
  );
}
