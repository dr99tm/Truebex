import { Section } from "@/components/layout/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { FaqList } from "@/components/sections/FaqList";
import { FAQS } from "@/lib/constants";

// The same Q&A is emitted as FAQPage structured data in app/page.tsx.
export function FAQ() {
  return (
    <Section id="faq">
      <SectionHeading
        title="Frequently asked questions"
        subtitle="Short answers about Truebex, hardware, the API and billing."
      />
      <FaqList items={FAQS} />
    </Section>
  );
}
