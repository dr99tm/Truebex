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
import { FAQS, FEATURES, SITE } from "@/lib/constants";

// Structured data: the product (SoftwareApplication) and the FAQ, which can
// earn rich results in Google. Keep in step with the visible content.
const homeLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "SoftwareApplication",
      name: "Truebex",
      url: SITE.url,
      applicationCategory: "DesignApplication",
      applicationSubCategory: "Building design",
      operatingSystem: "Windows",
      description: SITE.description,
      image: `${SITE.url}/images/og-image.jpg`,
      screenshot: `${SITE.url}/images/product/daylight-doorway.jpg`,
      featureList: FEATURES.map((f) => f.title),
      publisher: { "@id": `${SITE.url}/#organization` },
      offers: [
        { "@type": "Offer", name: "Starter", price: "0", priceCurrency: "USD" },
        {
          "@type": "Offer",
          name: "Professional",
          price: "99",
          priceCurrency: "USD",
          priceSpecification: {
            "@type": "UnitPriceSpecification",
            price: "99",
            priceCurrency: "USD",
            unitCode: "MON",
          },
        },
      ],
    },
    {
      "@type": "FAQPage",
      mainEntity: FAQS.map((f) => ({
        "@type": "Question",
        name: f.q,
        acceptedAnswer: { "@type": "Answer", text: f.a },
      })),
    },
  ],
};

export default function Home() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(homeLd) }}
      />
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
