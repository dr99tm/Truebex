// Releases as the site knows them at build time: the release feed documents
// (contract licence-api 5.13) that `npm run sync:releases` saves as
// src/content/releases.json (stable) and releases-beta.json (beta). The build
// itself never touches the network; client components refresh from the live
// feed after load (src/lib/licence.ts).
import betaFeed from "@/content/releases-beta.json";
import stableFeed from "@/content/releases.json";

export interface ReleaseManifest {
  schema: "truebex-release/1";
  version: string;
  channel: "stable" | "beta";
  platform: string;
  published_at: string;
  mandatory: boolean;
  min_update_from: string | null;
  notes_md: string;
  notes_url: string;
  installer: { file: string; bytes: number; sha256: string };
}

export interface ReleaseFeed {
  schema: "truebex-releases/1";
  channel: "stable" | "beta";
  platform: string;
  latest: string | null;
  releases: { manifest: ReleaseManifest; download?: string }[];
}

const FEEDS: Record<"stable" | "beta", ReleaseFeed> = {
  stable: stableFeed as unknown as ReleaseFeed,
  beta: betaFeed as unknown as ReleaseFeed,
};

export function latestRelease(channel: "stable" | "beta" = "stable"): ReleaseManifest | null {
  const feed = FEEDS[channel];
  const entry = feed.releases.find((r) => r.manifest.version === feed.latest) ?? feed.releases[0];
  return entry?.manifest ?? null;
}

/** Stable and beta releases together, newest first (the changelog). */
export function allReleases(): ReleaseManifest[] {
  const seen = new Map<string, ReleaseManifest>();
  for (const { manifest } of [...FEEDS.beta.releases, ...FEEDS.stable.releases]) {
    if (!seen.has(manifest.version)) seen.set(manifest.version, manifest);
  }
  return [...seen.values()].sort((a, b) => b.published_at.localeCompare(a.published_at));
}

/** "312.0 MB": decimal megabytes, one decimal. */
export function formatBytes(bytes: number): string {
  if (bytes < 1_000_000) return `${Math.max(1, Math.round(bytes / 1000))} KB`;
  return `${(bytes / 1_000_000).toFixed(1)} MB`;
}

/** "2 November 2026", in UTC so the static build is the same everywhere. */
export function formatReleaseDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    timeZone: "UTC",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}
