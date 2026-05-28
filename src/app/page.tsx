import { Hero } from "@/components/sections/Hero";
import { WhatIsTruebex } from "@/components/sections/WhatIsTruebex";
import { CoreFeatures } from "@/components/sections/CoreFeatures";
import { HowItWorks } from "@/components/sections/HowItWorks";
import { WhoItsFor } from "@/components/sections/WhoItsFor";
import { WhatMakesItDifferent } from "@/components/sections/WhatMakesItDifferent";
import { Pricing } from "@/components/sections/Pricing";
import { CTAContact } from "@/components/sections/CTAContact";
import { Footer } from "@/components/layout/Footer";

export default function Home() {
  return (
    <>
      <main>
        <Hero />
        <WhatIsTruebex />
        <CoreFeatures />
        <HowItWorks />
        <WhoItsFor />
        <WhatMakesItDifferent />
        <Pricing />
        <CTAContact />
      </main>
      <Footer />
    </>
  );
}
