import Image from "next/image";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Footer } from "@/components/layout/Footer";
import { FaqList } from "@/components/sections/FaqList";
import { FEATURE_PAGE_UI, type FeaturePageCopy } from "@/lib/constants";
import type { Capture } from "@/lib/site-routes";
import { cn } from "@/lib/utils";

const primary =
  "inline-flex h-10 items-center justify-center rounded-[var(--radius-button)] bg-accent px-6 text-sm font-medium text-background transition-all duration-300 hover:bg-accent-hover";
const secondary =
  "inline-flex h-10 items-center justify-center rounded-[var(--radius-button)] border border-accent px-6 text-sm font-medium text-accent transition-all duration-300 hover:bg-accent hover:text-background";

function Ctas({
  download,
  supplier,
}: {
  download: { href: string; label: string };
  supplier?: { href: string; label: string };
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row">
      <a href={download.href} data-cta="download" className={primary}>
        {download.label}
      </a>
      <a href="/signup/" className={secondary}>
        {FEATURE_PAGE_UI.signup}
      </a>
      {supplier && (
        <a href={supplier.href} className={secondary}>
          {supplier.label}
        </a>
      )}
    </div>
  );
}

/** One feature page per search cluster (truebex-seo keyword map), filled
 *  from FEATURE_PAGES. Roadmap pages speak in the future tense. */
export function FeaturePage({
  page,
  capture,
  download,
  related,
}: {
  page: FeaturePageCopy;
  capture: Capture | null;
  download: { href: string; label: string };
  related: readonly FeaturePageCopy[];
}) {
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
              {page.nav}
            </li>
          </ol>
        </nav>

        <header className="mt-6 max-w-3xl">
          <p
            className={cn(
              "text-sm font-medium uppercase tracking-wider",
              page.roadmap ? "text-warn" : "text-accent"
            )}
          >
            {page.eyebrow}
          </p>
          <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-5xl">{page.h1}</h1>
          <p className="mt-5 text-lg leading-relaxed text-text-secondary">{page.intro}</p>
          <div className="mt-8">
            <Ctas download={download} supplier={page.supplierCta} />
          </div>
        </header>

        {capture && (
          <figure className="mt-14 overflow-hidden rounded-[var(--radius-card)] border border-border">
            <Image
              src={capture.src}
              alt={capture.alt}
              width={capture.width}
              height={capture.height}
              sizes="(max-width: 1024px) 100vw, 1024px"
              className="h-auto w-full"
            />
            <figcaption className="border-t border-border bg-surface px-4 py-3 text-sm text-text-muted">
              {capture.caption}
            </figcaption>
          </figure>
        )}

        <section className="mt-16">
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{page.stepsTitle}</h2>
          <ol className="mt-8 grid gap-6 sm:grid-cols-2">
            {page.steps.map((step, i) => (
              <li key={step.title} className="flex gap-4 rounded-[var(--radius-card)] border border-border bg-surface/60 p-5">
                <span
                  className={cn(
                    "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-sm font-semibold",
                    page.roadmap ? "border-warn/40 text-warn" : "border-accent/30 text-accent"
                  )}
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

        {page.sections.map((section) => (
          <section key={section.title} className="mt-14 max-w-3xl">
            <h2 className="text-2xl font-bold tracking-tight">{section.title}</h2>
            <p className="mt-4 text-lg leading-relaxed text-text-secondary">{section.body}</p>
          </section>
        ))}

        <section className="mt-20">
          <h2 className="mb-8 text-2xl font-bold tracking-tight sm:text-3xl">{FEATURE_PAGE_UI.faqTitle}</h2>
          <FaqList items={page.faq} />
        </section>

        <section className="mt-20 rounded-[var(--radius-card)] border border-border bg-surface p-6 md:p-10">
          <h2 className="text-2xl font-bold tracking-tight">
            {page.roadmap ? FEATURE_PAGE_UI.roadmapCtaTitle : FEATURE_PAGE_UI.ctaTitle}
          </h2>
          <p className="mt-3 text-text-secondary">
            {page.roadmap ? FEATURE_PAGE_UI.roadmapCtaBody : FEATURE_PAGE_UI.ctaBody}
          </p>
          <div className="mt-6">
            <Ctas download={download} supplier={page.supplierCta} />
          </div>
          {page.roadmap && (
            <a href="/roadmap/" className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline">
              {FEATURE_PAGE_UI.roadmapLink}
              <ArrowRight size={14} aria-hidden />
            </a>
          )}
        </section>

        <nav aria-label={FEATURE_PAGE_UI.related} className="mt-16">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-text-muted">{FEATURE_PAGE_UI.related}</h2>
          <ul className="mt-4 grid gap-3 sm:grid-cols-2">
            {related.map((r) => (
              <li key={r.slug}>
                <a
                  href={`/features/${r.slug}/`}
                  className="flex items-center justify-between gap-3 rounded-[var(--radius-button)] border border-border px-4 py-3 text-sm text-text-secondary transition-colors hover:border-accent/40 hover:text-text-primary"
                >
                  <span>{r.h1}</span>
                  <ArrowRight size={14} aria-hidden className="shrink-0" />
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </main>
      <Footer />
    </>
  );
}
