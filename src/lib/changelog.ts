// The changelog's entries: releases from the release feeds
// (src/content/releases.json and releases-beta.json, written by
// `npm run sync:releases`) and the product's history
// (src/content/history.json). Used by /changelog/ and its Atom feed at build
// time.
import betaFeed from "@/content/releases-beta.json";
import releasesFeed from "@/content/releases.json";
import history from "@/content/history.json";

export interface ReleaseManifest {
  version: string;
  published_at: string;
  notes_md?: string;
  notes_url?: string;
  channel?: string;
  installer?: { file: string; bytes: number; sha256: string };
}

export interface ChangelogEntry {
  /** The anchor on /changelog/: the version for a release (as the release
   *  manifest's notes_url expects), a slug for a milestone. */
  id: string;
  kind: "release" | "history";
  date: string; // YYYY-MM-DD
  updated: string; // RFC 3339
  title: string;
  summary?: string;
  notes?: string;
  /** A release from the beta channel. */
  beta?: boolean;
}

interface Feed {
  releases: { manifest: ReleaseManifest }[];
}

function feedEntries(feed: unknown, beta: boolean): ChangelogEntry[] {
  return ((feed as Feed).releases ?? []).map(({ manifest }) => ({
    id: manifest.version,
    kind: "release",
    date: manifest.published_at.slice(0, 10),
    updated: manifest.published_at,
    title: `Truebex ${manifest.version}`,
    notes: manifest.notes_md ?? "",
    ...(beta ? { beta: true } : {}),
  }));
}

/** Stable releases: the page and the Atom feed. */
export function releaseEntries(): ChangelogEntry[] {
  return feedEntries(releasesFeed, false);
}

/** Beta releases not in the stable feed: the page only (each beta manifest's
 *  notes_url points at its anchor there), never the Atom feed. */
export function betaEntries(): ChangelogEntry[] {
  const stable = new Set(releaseEntries().map((r) => r.id));
  return feedEntries(betaFeed, true).filter((r) => !stable.has(r.id));
}

/** Milestones; one that shares its id with a release (1.0.0 once the feed
 *  lists it) gives way to the release entry. */
export function historyEntries(): ChangelogEntry[] {
  const versions = new Set(releaseEntries().map((r) => r.id));
  return history.filter((h) => !versions.has(h.id)).map((h) => ({
    id: h.id,
    kind: "history",
    date: h.date,
    updated: `${h.date}T00:00:00Z`,
    title: h.title,
    summary: h.summary,
  }));
}

/** Every entry, newest first. */
export function changelogEntries(): ChangelogEntry[] {
  return [...releaseEntries(), ...historyEntries()].sort((a, b) =>
    b.updated.localeCompare(a.updated)
  );
}

export function formatDay(day: string): string {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

// --- release notes: the contract's subset (headings, bullets, bold, links) ---

export type NoteBlock =
  | { type: "heading"; text: string }
  | { type: "list"; items: string[] }
  | { type: "paragraph"; text: string };

/** Split notes_md into blocks. Inline marks are handled by `inlineParts`. */
export function noteBlocks(md: string): NoteBlock[] {
  const blocks: NoteBlock[] = [];
  let list: string[] | null = null;
  for (const raw of md.split(/\r?\n/)) {
    const line = raw.trim();
    const bullet = /^[*-]\s+(.*)$/.exec(line);
    if (bullet) {
      if (!list) {
        list = [];
        blocks.push({ type: "list", items: list });
      }
      list.push(bullet[1]);
      continue;
    }
    list = null;
    if (!line) continue;
    const heading = /^#{1,6}\s+(.*)$/.exec(line);
    blocks.push(heading ? { type: "heading", text: heading[1] } : { type: "paragraph", text: line });
  }
  return blocks;
}

export type InlinePart =
  | { type: "text"; text: string }
  | { type: "bold"; text: string }
  | { type: "link"; text: string; href: string };

/** **bold** and [text](https://…) only; everything else stays plain text. */
export function inlineParts(text: string): InlinePart[] {
  const parts: InlinePart[] = [];
  const re = /\*\*([^*]+)\*\*|\[([^\]]+)\]\((https?:\/\/[^\s)]+|\/[^\s)]*)\)/g;
  let last = 0;
  for (let m = re.exec(text); m; m = re.exec(text)) {
    if (m.index > last) parts.push({ type: "text", text: text.slice(last, m.index) });
    if (m[1] !== undefined) parts.push({ type: "bold", text: m[1] });
    else parts.push({ type: "link", text: m[2], href: m[3] });
    last = re.lastIndex;
  }
  if (last < text.length) parts.push({ type: "text", text: text.slice(last) });
  return parts;
}

const ESCAPES: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

/** Release notes as escaped HTML, for the Atom feed's content. */
export function notesHtml(md: string): string {
  const inline = (t: string) =>
    inlineParts(t)
      .map((p) =>
        p.type === "bold"
          ? `<strong>${escapeHtml(p.text)}</strong>`
          : p.type === "link"
            ? `<a href="${escapeHtml(p.href)}">${escapeHtml(p.text)}</a>`
            : escapeHtml(p.text)
      )
      .join("");
  return noteBlocks(md)
    .map((b) =>
      b.type === "heading"
        ? `<h3>${inline(b.text)}</h3>`
        : b.type === "list"
          ? `<ul>${b.items.map((i) => `<li>${inline(i)}</li>`).join("")}</ul>`
          : `<p>${inline(b.text)}</p>`
    )
    .join("");
}
