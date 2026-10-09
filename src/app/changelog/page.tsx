import type { Metadata } from "next";
import { Rss } from "lucide-react";
import { Footer } from "@/components/layout/Footer";
import { CHANGELOG } from "@/lib/constants";
import {
  formatDay,
  historyEntries,
  inlineParts,
  noteBlocks,
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

function Inline({ text }: { text: string }) {
  return (
    <>
      {inlineParts(text).map((p, i) =>
        p.type === "bold" ? (
          <strong key={i} className="font-semibold text-text-primary">
            {p.text}
          </strong>
        ) : p.type === "link" ? (
          <a key={i} href={p.href} className="text-accent hover:underline">
            {p.text}
          </a>
        ) : (
          <span key={i}>{p.text}</span>
        )
      )}
    </>
  );
}

/** Release notes in the contract's subset, rendered at build time. */
function Notes({ md }: { md: string }) {
  return (
    <div className="prose-doc mt-3">
      {noteBlocks(md).map((b, i) =>
        b.type === "heading" ? (
          <h4 key={i} className="mt-4 font-semibold text-text-primary">
            <Inline text={b.text} />
          </h4>
        ) : b.type === "list" ? (
          <ul key={i}>
            {b.items.map((item, j) => (
              <li key={j}>
                <Inline text={item} />
              </li>
            ))}
          </ul>
        ) : (
          <p key={i}>
            <Inline text={b.text} />
          </p>
        )
      )}
    </div>
  );
}

function Entry({ entry }: { entry: ChangelogEntry }) {
  return (
    <article id={entry.id} className="scroll-mt-28 border-t border-border py-8">
      <p className="text-sm text-text-muted">
        <time dateTime={entry.date}>{formatDay(entry.date)}</time>
      </p>
      <h3 className="mt-1 text-xl font-semibold text-text-primary">
        <a href={`#${entry.id}`} className="hover:text-accent">
          {entry.title}
        </a>
      </h3>
      {entry.summary && <p className="mt-3 leading-relaxed text-text-secondary">{entry.summary}</p>}
      {entry.notes && <Notes md={entry.notes} />}
    </article>
  );
}

export default function ChangelogPage() {
  const releases = releaseEntries();
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
        <a href={FEED} className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-accent hover:underline">
          <Rss size={15} aria-hidden />
          {CHANGELOG.feedLink}
        </a>

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
