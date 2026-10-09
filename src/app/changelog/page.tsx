import type { Metadata } from "next";
import { Rss } from "lucide-react";
import { Footer } from "@/components/layout/Footer";
import { ReleaseNotes } from "@/components/releases/ReleaseNotes";
import { Button } from "@/components/ui/Button";
import { CHANGELOG } from "@/lib/constants";
import {
  betaEntries,
  formatDay,
  historyEntries,
  releaseEntries,
  type ChangelogEntry,
} from "@/lib/changelog";
import { absolute, breadcrumbLd, ldJson, pageMetadata, webPageLd } from "@/lib/seo";

const FEED = "/changelog/feed.xml";

export const metadata: Metadata = pageMetadata({
  title: CHANGELOG.title,
  description: CHANGELOG.description,
  path: "/changelog/",
  types: { "application/atom+xml": FEED },
});

function Entry({ entry }: { entry: ChangelogEntry }) {
  return (
    <article id={entry.id} className="scroll-mt-28 border-t border-border py-8">
      <p className="text-sm text-text-muted">
        <time dateTime={entry.date}>{formatDay(entry.date)}</time>
      </p>
      <h3 className="mt-1 flex flex-wrap items-center gap-3 text-xl font-semibold text-text-primary">
        <a href={`#${entry.id}`} className="hover:text-accent">
          {entry.title}
        </a>
        {entry.beta && (
          <span className="rounded-full border border-warn/40 px-2 py-0.5 text-xs font-medium text-warn">
            {CHANGELOG.beta}
          </span>
        )}
      </h3>
      {entry.summary && <p className="mt-3 leading-relaxed text-text-secondary">{entry.summary}</p>}
      {/* Release notes: the contract's subset, rendered as React text. */}
      {entry.notes && <ReleaseNotes md={entry.notes} className="mt-3" />}
    </article>
  );
}

export default function ChangelogPage() {
  // Stable and beta releases, newest first; each anchor is the version (the
  // manifest's notes_url).
  const releases = [...releaseEntries(), ...betaEntries()].sort((a, b) =>
    b.updated.localeCompare(a.updated)
  );
  const history = historyEntries();
  const ld = ldJson([
    webPageLd({ name: CHANGELOG.heading, description: CHANGELOG.description, path: "/changelog/" }),
    breadcrumbLd([
      { name: "Truebex", path: "/" },
      { name: CHANGELOG.title, path: "/changelog/" },
    ]),
    {
      "@type": "ItemList",
      name: CHANGELOG.heading,
      itemListElement: [...releases, ...history].map((e, i) => ({
        "@type": "ListItem",
        position: i + 1,
        name: e.title,
        url: absolute(`/changelog/#${e.id}`),
      })),
    },
  ]);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ld }} />
      <main className="mx-auto max-w-3xl px-4 pb-24 pt-28 md:px-8">
        <p className="text-sm font-medium uppercase tracking-wider text-accent">{CHANGELOG.eyebrow}</p>
        <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-5xl">{CHANGELOG.heading}</h1>
        <p className="mt-5 text-lg text-text-secondary">{CHANGELOG.intro}</p>
        <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3">
          <Button href="/download/" variant="secondary">
            {CHANGELOG.downloadCta}
          </Button>
          <a href={FEED} className="inline-flex items-center gap-2 text-sm font-medium text-accent hover:underline">
            <Rss size={15} aria-hidden />
            {CHANGELOG.feedLink}
          </a>
        </div>

        {releases.length > 0 && (
          <section className="mt-12">
            <h2 className="text-2xl font-bold tracking-tight">{CHANGELOG.releasesTitle}</h2>
            {releases.map((e) => (
              <Entry key={e.id} entry={e} />
            ))}
          </section>
        )}

        <section className="mt-12">
          <h2 className="text-2xl font-bold tracking-tight">{CHANGELOG.historyTitle}</h2>
          {history.map((e) => (
            <Entry key={e.id} entry={e} />
          ))}
        </section>
      </main>
      <Footer />
    </>
  );
}
