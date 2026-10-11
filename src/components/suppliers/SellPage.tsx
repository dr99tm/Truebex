import Link from "next/link";
import { ArrowRight, ChartColumn, FileSpreadsheet, Globe, Inbox, Package, Users, type LucideIcon } from "lucide-react";
import { Footer } from "@/components/layout/Footer";
import { FaqList } from "@/components/sections/FaqList";
import { FEATURE_PAGE_UI, SELL_PAGE } from "@/lib/constants";

const ICONS: Record<(typeof SELL_PAGE.offer)[number]["id"], LucideIcon> = {
  catalogue: Package,
  regions: Globe,
  imports: FileSpreadsheet,
  inbox: Inbox,
  numbers: ChartColumn,
  team: Users,
};

const primary =
  "inline-flex h-10 items-center justify-center rounded-[var(--radius-button)] bg-accent px-6 text-sm font-medium text-background transition-all duration-300 hover:bg-accent-hover";

// The page's one call to action: the supplier portal's sign-up.
function Apply() {
  return (
    <a href={SELL_PAGE.cta.href} data-cta="supplier-signup" className={primary}>
      {SELL_PAGE.cta.label}
    </a>
  );
}

/** Sell on Truebex (/suppliers/): what the supplier portal gives a supplier
 *  today, how the first suppliers are onboarded, and what is on the roadmap.
 *  Every section is server-rendered from SELL_PAGE. */
export function SellPage() {
  const S = SELL_PAGE;
  return (
    <>
      <main className="mx-auto max-w-5xl px-4 pb-24 pt-28 md:px-8">
        <nav aria-label="Breadcrumb" className="text-sm text-text-muted">
          <ol className="flex flex-wrap items-center gap-2">
            <li>
              <Link href="/" className="hover:text-text-primary">
                {FEATURE_PAGE_UI.home}
              </Link>
            </li>
            <li aria-hidden>/</li>
            <li aria-current="page" className="text-text-secondary">
              {S.nav}
            </li>
          </ol>
        </nav>

        <header className="mt-6 max-w-3xl">
          <p className="text-sm font-medium uppercase tracking-wider text-accent">{S.eyebrow}</p>
          <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-5xl">{S.h1}</h1>
          <p className="mt-5 text-lg leading-relaxed text-text-secondary">{S.intro}</p>
          <div className="mt-8">
            <Apply />
          </div>
          <p className="mt-3 text-sm text-text-muted">{S.ctaNote}</p>
        </header>

        <section data-sell="offer" className="mt-16">
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{S.offerTitle}</h2>
          <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {S.offer.map((item) => {
              const Icon = ICONS[item.id];
              return (
                <li key={item.id} className="rounded-[var(--radius-card)] border border-border bg-surface/60 p-5">
                  <Icon className="h-5 w-5 text-accent" aria-hidden />
                  <h3 className="mt-3 font-semibold text-text-primary">{item.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-text-secondary">{item.body}</p>
                </li>
              );
            })}
          </ul>
        </section>

        <section data-sell="onboarding" className="mt-16">
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{S.stepsTitle}</h2>
          <ol className="mt-8 grid gap-6 sm:grid-cols-2">
            {S.steps.map((step, i) => (
              <li key={step.title} className="flex gap-4 rounded-[var(--radius-card)] border border-border bg-surface/60 p-5">
                <span
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-accent/30 text-sm font-semibold text-accent"
                  aria-hidden
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div>
                  <h3 className="font-semibold text-text-primary">{step.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-text-secondary">{step.description}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section data-sell="roadmap" className="mt-16">
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{S.roadmapTitle}</h2>
          <p className="mt-4 max-w-3xl text-lg leading-relaxed text-text-secondary">{S.roadmapIntro}</p>
          <ul className="mt-8 grid gap-4 sm:grid-cols-3">
            {S.roadmap.map((item) => (
              <li
                key={item.title}
                data-roadmap="true"
                className="rounded-[var(--radius-card)] border border-dashed border-border bg-surface/40 p-5"
              >
                <span className="inline-block rounded-full border border-warn/40 px-2.5 py-0.5 text-xs font-medium text-warn">
                  {S.roadmapLabel}
                </span>
                <h3 className="mt-3 font-semibold text-text-primary">{item.title}</h3>
                <p className="mt-1 text-sm leading-relaxed text-text-secondary">{item.body}</p>
              </li>
            ))}
          </ul>
          <a href="/roadmap/" className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline">
            {S.roadmapLink}
            <ArrowRight size={14} aria-hidden />
          </a>
        </section>

        <section data-sell="faq" className="mt-20">
          <h2 className="mb-8 text-2xl font-bold tracking-tight sm:text-3xl">{S.faqTitle}</h2>
          <FaqList items={S.faq} align="start" />
        </section>

        <section data-sell="apply" className="mt-20 rounded-[var(--radius-card)] border border-border bg-surface p-6 md:p-10">
          <h2 className="text-2xl font-bold tracking-tight">{S.closingTitle}</h2>
          <p className="mt-3 text-text-secondary">{S.closingBody}</p>
          <div className="mt-6">
            <Apply />
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
