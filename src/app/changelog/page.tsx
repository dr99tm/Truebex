import type { Metadata } from "next";
import { Footer } from "@/components/layout/Footer";
import { ReleaseNotes } from "@/components/releases/ReleaseNotes";
import { Button } from "@/components/ui/Button";
import { CHANGELOG_PAGE as CHANGELOG, SITE } from "@/lib/constants";
import { allReleases, formatReleaseDate } from "@/lib/releases";

export const metadata: Metadata = {
  title: CHANGELOG.metaTitle,
  description: CHANGELOG.description,
  alternates: { canonical: "/changelog/" },
  openGraph: {
    title: `${CHANGELOG.h1} · Truebex`,
    description: CHANGELOG.description,
    url: `${SITE.url}/changelog/`,
  },
};

export default function ChangelogPage() {
  // Notes are rendered at build time from src/content/releases*.json; each
  // section's id is its version, the anchor of the manifest's notes_url.
  const releases = allReleases();
  return (
    <>
      <main className="mx-auto max-w-3xl px-4 pb-24 pt-28 md:px-8">
        <p className="text-sm font-medium uppercase tracking-wider text-accent">{CHANGELOG.eyebrow}</p>
        <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-5xl">{CHANGELOG.h1}</h1>
        <p className="mt-5 text-lg text-text-secondary">{CHANGELOG.intro}</p>
        <div className="mt-6">
          <Button href="/download/" variant="secondary">
            {CHANGELOG.downloadCta}
          </Button>
        </div>

        {releases.length === 0 ? (
          <p className="mt-12 text-text-secondary">{CHANGELOG.empty}</p>
        ) : (
          <div className="mt-12 space-y-12">
            {releases.map((r) => (
              <section key={r.version} id={r.version} className="scroll-mt-28 border-t border-border pt-8">
                <h2 className="flex flex-wrap items-center gap-3 text-2xl font-semibold tracking-tight">
                  <a href={`#${r.version}`} className="hover:text-accent">
                    {CHANGELOG.release} {r.version}
                  </a>
                  {r.channel === "beta" && (
                    <span className="rounded-full border border-warn/40 px-2 py-0.5 text-xs font-medium text-warn">
                      {CHANGELOG.beta}
                    </span>
                  )}
                </h2>
                <p className="mt-1 text-sm text-text-muted">
                  <time dateTime={r.published_at}>{formatReleaseDate(r.published_at)}</time>
                </p>
                <ReleaseNotes md={r.notes_md} className="mt-4" />
              </section>
            ))}
          </div>
        )}
      </main>
      <Footer />
    </>
  );
}
