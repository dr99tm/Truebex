import { Section } from "@/components/layout/Section";
import { FadeInWhenVisible } from "@/components/animations/FadeInWhenVisible";
import { ContactButtons } from "@/components/sections/ContactButtons";
import { CONTACT_CTA } from "@/lib/constants";

/**
 * The closing call to action. Pre-launch (owner, 2026-11-22) it is contact
 * only: email or WhatsApp, to join the early-adopter or tester list. The
 * demo request form that posted to a spreadsheet is gone.
 */
export function CTAContact() {
  return (
    <section id="contact" className="relative overflow-hidden">
      {/* Background glow */}
      <div className="pointer-events-none absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-[400px] w-[400px] rounded-full bg-accent/5 blur-[100px]" />

      <Section>
        <div className="relative z-10 mx-auto max-w-2xl text-center">
          <FadeInWhenVisible>
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl md:text-5xl">
              {CONTACT_CTA.titleStart}{" "}
              <span className="gradient-text">{CONTACT_CTA.titleAccent}</span>
            </h2>
            <p className="mt-6 text-lg text-text-secondary">{CONTACT_CTA.body}</p>
          </FadeInWhenVisible>

          <FadeInWhenVisible delay={0.2}>
            <ContactButtons copy={CONTACT_CTA} />
          </FadeInWhenVisible>
        </div>
      </Section>
    </section>
  );
}
