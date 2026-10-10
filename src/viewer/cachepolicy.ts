// What the mobile web client's service worker (src/sw/sw.ts, PF9) may cache,
// and how the tile cache stays inside its budget. Framework-free and pure, so
// the worker bundles it and the self-test (selftest.ts) checks it in Node.
//
// Rules: hashed build files (/_next/static/) cache-first; the app's own pages
// (/app/…) network-first with the cached copy offline; tiles (content-addressed
// `<sha256>.jpg`, public and immutable, render-jobs §6.2) cache-first under a
// 150 MB budget, least recently used out. Nothing else — no API answer, no
// page of another route, nothing sent with credentials — is ever cached.

export const SHELL_CACHE = "shell-v1";
export const TILES_CACHE = "tiles-v1";
export const TILE_BUDGET_BYTES = 150 * 1024 * 1024;
/** The app's routes, network-first; every other page is left to the network. */
export const APP_PAGES = ["/app/", "/app/project/"] as const;

export type Rule = "static" | "page" | "tile" | null;

export interface RequestFacts {
  url: string;
  method: string;
  /** Request.mode: "navigate" for a page load. */
  mode: string;
  /** The service worker's own origin (self.location.origin). */
  origin: string;
  /** An Authorization header is present. */
  authorized?: boolean;
}

const TILE_PATH = /\/[0-9a-f]{64}\.jpg$/;

/** A tile URL: http(s), a path ending in `<64 hex>.jpg`, no query. */
export function isTileUrl(raw: string): boolean {
  try {
    const url = new URL(raw);
    return (url.protocol === "https:" || url.protocol === "http:") && !url.search && TILE_PATH.test(url.pathname);
  } catch {
    return false;
  }
}

/** The page a navigation is cached under: the route without its query (`?id=`). */
export function pageKey(raw: string): string | null {
  const url = new URL(raw);
  const path = url.pathname.endsWith("/") ? url.pathname : `${url.pathname}/`;
  return (APP_PAGES as readonly string[]).includes(path) ? `${url.origin}${path}` : null;
}

/** Which strategy a request gets; null = the network, untouched. */
export function requestRule(req: RequestFacts): Rule {
  if (req.method !== "GET" || req.authorized) return null;
  let url: URL;
  try {
    url = new URL(req.url);
  } catch {
    return null;
  }
  if (isTileUrl(req.url)) return "tile";
  if (url.origin !== req.origin) return null;
  if (url.pathname.startsWith("/_next/static/")) return "static";
  if (req.mode === "navigate" && pageKey(req.url)) return "page";
  return null;
}

export interface CacheEntry {
  url: string;
  bytes: number;
  /** Last use, ms since the epoch. */
  used: number;
}

/**
 * The URLs to drop so the cache plus `incoming` bytes fits `budget`: least
 * recently used first; ties by URL so the plan is deterministic.
 */
export function planEviction(entries: CacheEntry[], budget: number, incoming = 0): string[] {
  let total = incoming + entries.reduce((sum, e) => sum + Math.max(0, e.bytes), 0);
  if (total <= budget) return [];
  const order = [...entries].sort((a, b) => a.used - b.used || (a.url < b.url ? -1 : a.url > b.url ? 1 : 0));
  const out: string[] = [];
  for (const e of order) {
    if (total <= budget) break;
    out.push(e.url);
    total -= Math.max(0, e.bytes);
  }
  return out;
}
