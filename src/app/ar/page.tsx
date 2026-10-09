import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { Mail } from "lucide-react";
import { Footer } from "@/components/layout/Footer";
import { Section } from "@/components/layout/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { GlassCard } from "@/components/ui/GlassCard";
import { Lockup } from "@/components/brand/Logo";
import { FaqList } from "@/components/sections/FaqList";
import { TierCards } from "@/components/pricing/TierCards";
import { annualSavingPercent, anyPriced } from "@/lib/catalogue";
import { loadCatalogue } from "@/lib/catalogue-data";
import { AR_HOME, AUDIENCES, FEATURES, PRICING, PRODUCT_SHOT, SITE } from "@/lib/constants";
import { pickTiers } from "@/lib/pricing";
import { ROADMAP_ITEMS, roadmapIcon, STATUS_CLASS } from "@/lib/roadmap";
import { faqLd, HOME_LANGUAGES, ldJson, pageMetadata, webPageLd } from "@/lib/seo";
import { cn } from "@/lib/utils";

export const metadata: Metadata = pageMetadata({
  title: AR_HOME.meta.title,
  absoluteTitle: true,
  description: AR_HOME.meta.description,
  path: "/ar/",
  languages: HOME_LANGUAGES,
  locale: AR_HOME.meta.ogLocale,
});

const primary =
  "inline-flex h-10 items-center justify-center rounded-[var(--radius-button)] bg-accent px-8 text-base font-medium text-background transition-all duration-300 hover:bg-accent-hover";
const secondary =
  "inline-flex h-10 items-center justify-center rounded-[var(--radius-button)] border border-accent px-8 text-base font-medium text-accent transition-all duration-300 hover:bg-accent hover:text-background";

/** The home page in Arabic, right to left (hreflang-paired with /). */
export default function ArabicHome() {
  const catalogue = loadCatalogue();
  const t = AR_HOME;
  const roadmap = ROADMAP_ITEMS.filter((i) => i.id in t.roadmap.items);
  const ld = ldJson([
    webPageLd({ name: t.meta.title, description: t.meta.description, path: "/ar/", inLanguage: "ar" }),
    faqLd(t.faq.items),
  ]);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ld }} />
      <main>
        {/* Hero */}
        <section className="relative overflow-hidden px-4 pb-20 pt-32 md:pt-40">
          <div className="pointer-events-none absolute inset-0">
            <div className="blueprint-grid absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black_25%,transparent_70%)]" />
          </div>
          <div className="relative z-10 mx-auto max-w-4xl text-center">
            <div dir="ltr">
              <Lockup className="text-3xl sm:text-4xl" />
            </div>
            <p className="mt-5">
              <span className="inline-block rounded-full border border-accent/25 bg-accent/5 px-4 py-1.5 text-sm text-accent">
                {t.hero.badge}
              </span>
            </p>
            <h1 className="mt-8 text-4xl font-bold leading-[1.25] tracking-normal sm:text-6xl md:text-7xl">
              {t.hero.titleStart} <span className="gradient-text">{t.hero.titleAccent}</span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg leading-loose text-text-secondary md:text-xl">
              {t.hero.subtitle}
            </p>
            <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
              <a href={t.hero.primary.href} className={primary}>
                {t.hero.primary.label}
              </a>
              <a href={t.hero.secondary.href} className={secondary}>
                {t.hero.secondary.label}
              </a>
            </div>
          </div>
          <figure className="relative z-10 mx-auto mt-16 max-w-6xl">
            <div className="relative overflow-hidden rounded-[var(--radius-card)] border border-white/10 shadow-[0_30px_80px_#00000080]">
              <Image
                src={PRODUCT_SHOT.wide}
                alt={t.hero.alt}
                width={1600}
                height={900}
                priority
                sizes="(min-width: 1200px) 1152px, 100vw"
                className="h-auto w-full"
              />
            </div>
            <figcaption className="mt-4 text-center text-sm text-text-muted">{t.hero.caption}</figcaption>
          </figure>
        </section>

        {/* What is Truebex */}
        <Section id="about">
          <SectionHeading title={t.about.title} subtitle={t.about.subtitle} />
          <div className="mx-auto max-w-3xl space-y-6">
            {t.about.paragraphs.map((p) => (
              <p key={p} className="text-lg leading-loose text-text-secondary">
                {p}
              </p>
            ))}
          </div>
        </Section>

        {/* Features */}
        <Section id="features">
          <SectionHeading title={t.features.title} subtitle={t.features.subtitle} />
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => {
              const words = t.features.items[f.id];
              return (
                <GlassCard key={f.id} className="h-full">
                  <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-accent/10">
                    <f.icon className="h-6 w-6 text-accent" aria-hidden />
                  </div>
                  <h3 className="mb-2 text-xl font-semibold">{words.title}</h3>
                  <p className="leading-loose text-text-secondary">{words.description}</p>
                </GlassCard>
              );
            })}
          </div>
        </Section>

        {/* How it works */}
        <Section id="how-it-works">
          <SectionHeading title={t.steps.title} subtitle={t.steps.subtitle} />
          <ol className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {t.steps.items.map((step) => (
              <li key={step.number} className="flex flex-col items-center text-center">
                <span className="flex h-20 w-20 items-center justify-center rounded-full border border-accent/30 bg-background text-2xl font-bold text-accent">
                  {step.number}
                </span>
                <h3 className="mt-6 text-lg font-semibold">{step.title}</h3>
                <p className="mt-2 text-sm leading-loose text-text-secondary">{step.description}</p>
              </li>
            ))}
          </ol>
        </Section>

        {/* Who it's for */}
        <Section id="who-its-for">
          <SectionHeading title={t.audiences.title} subtitle={t.audiences.subtitle} />
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {t.audiences.items.map((a, i) => {
              const Icon = AUDIENCES[i].icon;
              return (
                <GlassCard key={a.title} className="flex h-full items-start gap-4">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-accent/10">
                    <Icon className="h-6 w-6 text-accent" aria-hidden />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold">{a.title}</h3>
                    <p className="mt-1 text-sm leading-loose text-text-secondary">{a.description}</p>
                  </div>
                </GlassCard>
              );
            })}
          </div>
        </Section>

        {/* Pricing teaser */}
        <Section id="pricing">
          <SectionHeading title={t.pricing.title} subtitle={t.pricing.subtitle} />
          <TierCards
            tiers={pickTiers(catalogue, PRICING.teaser)}
            copy={t.pricing.tiers}
            labels={t.pricing.labels}
            saving={annualSavingPercent(catalogue)}
            showControls={anyPriced(catalogue)}
            headingLevel="h3"
          />
          <p className="mt-10 text-center">
            <a href="/pricing/" hrefLang="en" className={secondary}>
              {t.pricing.seeAll}
            </a>
          </p>
        </Section>

        {/* Roadmap */}
        <Section id="roadmap">
          <SectionHeading title={t.roadmap.title} subtitle={t.roadmap.subtitle} />
          <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {roadmap.map((item) => {
              const words = t.roadmap.items[item.id as keyof typeof t.roadmap.items];
              const Icon = roadmapIcon(item.icon);
              return (
                <li
                  key={item.id}
                  className="flex gap-3 rounded-[var(--radius-card)] border border-dashed border-border p-5"
                >
                  <Icon className="mt-1 h-5 w-5 shrink-0 text-text-muted" aria-hidden />
                  <div>
                    <p className="font-medium text-text-primary">{words.title}</p>
                    <p className="mt-1 text-sm leading-loose text-text-secondary">{words.description}</p>
                    <span
                      className={cn(
                        "mt-2 inline-block rounded-full border px-2 py-0.5 text-xs font-medium",
                        STATUS_CLASS[item.status]
                      )}
                    >
                      {t.roadmap.status[item.status]}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
          <p className="mt-8 text-center">
            <a href="/roadmap/" hrefLang="en" className="text-sm font-medium text-accent hover:underline">
              {t.roadmap.link}
            </a>
          </p>
        </Section>

        {/* FAQ */}
        <Section id="faq">
          <SectionHeading title={t.faq.title} subtitle={t.faq.subtitle} />
          <FaqList items={t.faq.items} />
        </Section>

        {/* Contact */}
        <section id="contact" className="relative overflow-hidden">
          <Section>
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-2xl font-bold sm:text-3xl md:text-5xl md:leading-tight">
                {t.contact.titleStart} <span className="gradient-text">{t.contact.titleAccent}</span>
              </h2>
              <p className="mt-6 text-lg leading-loose text-text-secondary">{t.contact.body}</p>
              <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
                <a href={`mailto:${SITE.email}?subject=Truebex`} className={primary}>
                  <Mail size={18} className="me-2" aria-hidden />
                  {t.contact.email}
                </a>
                <Link href="/#contact" hrefLang="en" className={secondary}>
                  {t.contact.form}
                </Link>
              </div>
            </div>
          </Section>
        </section>
      </main>
      <Footer locale="ar" />
    </>
  );
}
