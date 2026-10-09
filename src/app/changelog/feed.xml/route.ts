import { CHANGELOG, SITE } from "@/lib/constants";
import { changelogEntries, escapeHtml, notesHtml } from "@/lib/changelog";

// Written once at build time into out/changelog/feed.xml (like sitemap.ts).
export const dynamic = "force-static";

const FEED_URL = `${SITE.url}/changelog/feed.xml`;
const PAGE_URL = `${SITE.url}/changelog/`;

/** The changelog as an Atom 1.0 feed (RFC 4287): one entry per release and
 *  per milestone, each linking to its anchor on /changelog/. */
export function GET() {
  const entries = changelogEntries();
  const updated = entries[0]?.updated ?? "2026-10-07T00:00:00Z";
  const body = entries
    .map((e) => {
      const url = `${PAGE_URL}#${encodeURIComponent(e.id)}`;
      const html = e.notes ? notesHtml(e.notes) : `<p>${escapeHtml(e.summary ?? "")}</p>`;
      return [
        "  <entry>",
        `    <id>${escapeHtml(url)}</id>`,
        `    <title>${escapeHtml(e.title)}</title>`,
        `    <link rel="alternate" type="text/html" href="${escapeHtml(url)}"/>`,
        `    <updated>${e.updated}</updated>`,
        `    <published>${e.updated}</published>`,
        `    <content type="html">${escapeHtml(html)}</content>`,
        "  </entry>",
      ].join("\n");
    })
    .join("\n");

  const xml = [
    '<?xml version="1.0" encoding="utf-8"?>',
    '<feed xmlns="http://www.w3.org/2005/Atom">',
    `  <id>${PAGE_URL}</id>`,
    `  <title>${escapeHtml(CHANGELOG.feedTitle)}</title>`,
    `  <subtitle>${escapeHtml(CHANGELOG.feedSubtitle)}</subtitle>`,
    `  <link rel="self" type="application/atom+xml" href="${FEED_URL}"/>`,
    `  <link rel="alternate" type="text/html" href="${PAGE_URL}"/>`,
    `  <updated>${updated}</updated>`,
    `  <author><name>Truebex</name><uri>${SITE.url}/</uri></author>`,
    `  <icon>${SITE.url}/icon-192.png</icon>`,
    body,
    "</feed>",
    "",
  ].join("\n");

  return new Response(xml, {
    headers: { "Content-Type": "application/atom+xml; charset=utf-8" },
  });
}
