import { Section } from "@/components/layout/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { FAQS } from "@/lib/constants";

// Native <details> so answers are in the HTML (crawlable) and work without JS.
// The same Q&A is emitted as FAQPage structured data in app/page.tsx.
export function FAQ() {
  return (
    <Section id="faq">
      <SectionHeading
        title="Frequently asked questions"
        subtitle="Short answers about Truebex, hardware, the API and billing."
      />
      <div className="mx-auto max-w-3xl divide-y divide-border rounded-[var(--radius-card)] border border-border bg-surface/60">
        {FAQS.map((item) => (
          <details key={item.q} className="group px-5 py-4 [&_summary::-webkit-details-marker]:hidden">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-left font-medium text-text-primary">
              <h3 className="text-base">{item.q}</h3>
              <span
                aria-hidden
                className="text-xl leading-none text-text-muted transition-transform group-open:rotate-45"
              >
                +
              </span>
            </summary>
            <p className="mt-3 leading-relaxed text-text-secondary">{item.a}</p>
          </details>
        ))}
      </div>
    </Section>
  );
}
