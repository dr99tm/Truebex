// The mobile web client's service worker (PF9), bundled by
// scripts/build-app.mjs into out/sw.js and registered by the /app/ layout
// with scope "/". It caches only what cachepolicy.ts allows:
//
//   /_next/static/*   hashed build files, cache-first (shell-v1); the files the
//                     /app/ pages reference are precached at install
//   /app/, /app/project/   network-first, the cached copy offline
//   <sha256>.jpg      tiles, cache-first (tiles-v1), fetched with CORS, 150 MB,
//                     least recently used out (an index in IndexedDB)
//
// Everything else — API answers, other pages, anything with credentials —
// passes through untouched; the worker never sees the session token. A
// background sync only wakes an open app page to flush its outbox (the page
// holds the token). The page posts {type: "clear"} on sign-out.
//
// Written against the DOM types the site already uses: the worker's own
// globals are declared below instead of the webworker lib (which clashes
// with the DOM lib in one TypeScript project).

import { planEviction, pageKey, requestRule, SHELL_CACHE, TILE_BUDGET_BYTES, TILES_CACHE, type CacheEntry } from "../viewer/cachepolicy";

declare const PRECACHE: string[];
declare const BUILD_ID: string;

interface ExtendableEvent extends Event {
  waitUntil(p: Promise<unknown>): void;
}
interface FetchEvent extends ExtendableEvent {
  request: Request;
  respondWith(r: Promise<Response> | Response): void;
}
interface SyncEvent extends ExtendableEvent {
  tag: string;
}
interface MessageEventLike extends ExtendableEvent {
  data: unknown;
}
interface WindowClientLike {
  postMessage(message: unknown): void;
}
interface WorkerScope {
  location: Location;
  clients: { claim(): Promise<void>; matchAll(options: { type: string; includeUncontrolled?: boolean }): Promise<WindowClientLike[]> };
  skipWaiting(): Promise<void>;
  addEventListener(type: "install" | "activate", fn: (e: ExtendableEvent) => void): void;
  addEventListener(type: "fetch", fn: (e: FetchEvent) => void): void;
  addEventListener(type: "sync", fn: (e: SyncEvent) => void): void;
  addEventListener(type: "message", fn: (e: MessageEventLike) => void): void;
}

const sw = self as unknown as WorkerScope;
const ORIGIN = sw.location.origin;
const LRU_DB = "truebex-tiles";

// --- install / activate ------------------------------------------------------------------

sw.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE);
      // One by one: a file missing from this deploy must not fail the install.
      await Promise.all(PRECACHE.map((path) => cache.add(new Request(path, { cache: "reload" })).catch(() => undefined)));
      await sw.skipWaiting();
    })()
  );
});

sw.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keep = new Set([SHELL_CACHE, TILES_CACHE]);
      for (const name of await caches.keys()) if (!keep.has(name)) await caches.delete(name);
      // Build files of earlier deploys go; this build's stay.
      const current = new Set(PRECACHE.map((p) => new URL(p, ORIGIN).href));
      const shell = await caches.open(SHELL_CACHE);
      for (const req of await shell.keys()) {
        const url = new URL(req.url);
        if (url.pathname.startsWith("/_next/static/") && !current.has(url.href)) await shell.delete(req);
      }
      await sw.clients.claim();
    })()
  );
});

// --- fetch -----------------------------------------------------------------------------------

sw.addEventListener("fetch", (event) => {
  const req = event.request;
  const rule = requestRule({
    url: req.url,
    method: req.method,
    mode: req.mode,
    origin: ORIGIN,
    authorized: req.headers.has("Authorization"),
  });
  if (rule === "static") event.respondWith(cacheFirst(req));
  else if (rule === "page") event.respondWith(networkFirst(req));
  else if (rule === "tile") event.respondWith(tile(req, event));
});

async function cacheFirst(req: Request): Promise<Response> {
  const cache = await caches.open(SHELL_CACHE);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok && res.type === "basic") await cache.put(req, res.clone());
  return res;
}

async function networkFirst(req: Request): Promise<Response> {
  const key = pageKey(req.url)!;
  const cache = await caches.open(SHELL_CACHE);
  try {
    const res = await fetch(req);
    if (res.ok && res.type === "basic") await cache.put(key, res.clone());
    return res;
  } catch {
    const hit = (await cache.match(key)) ?? (await cache.match(new URL("/app/", ORIGIN).href));
    if (hit) return hit;
    throw new Error("offline and not cached");
  }
}

async function tile(req: Request, event: FetchEvent): Promise<Response> {
  const cache = await caches.open(TILES_CACHE);
  const hit = await cache.match(req.url);
  if (hit) {
    event.waitUntil(touch(req.url));
    return hit;
  }
  let res: Response;
  try {
    // A CORS response has a real size (an opaque one would count as megabytes
    // against the quota) and is what WebGL needs anyway.
    res = await fetch(req.url, { mode: "cors", credentials: "omit" });
  } catch {
    return fetch(req); // no CORS on this host: the network, uncached
  }
  if (res.ok) event.waitUntil(store(cache, req.url, res.clone()));
  return res;
}

async function store(cache: Cache, url: string, res: Response): Promise<void> {
  const body = await res.blob();
  const headers = new Headers(res.headers);
  await cache.put(url, new Response(body, { status: 200, headers }));
  await saveLru([{ url, bytes: body.size, used: Date.now() }], []);
  const drop = planEviction([...(await lru()).values()], TILE_BUDGET_BYTES);
  for (const gone of drop) await cache.delete(gone);
  if (drop.length) await saveLru([], drop);
}

// --- the LRU index (IndexedDB truebex-tiles, store lru: url -> {bytes, used}) -----------------

function openLru(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(LRU_DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore("lru", { keyPath: "url" });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function lru(): Promise<Map<string, CacheEntry>> {
  const db = await openLru();
  const rows = await new Promise<CacheEntry[]>((resolve, reject) => {
    const r = db.transaction("lru").objectStore("lru").getAll();
    r.onsuccess = () => resolve(r.result as CacheEntry[]);
    r.onerror = () => reject(r.error);
  });
  db.close();
  return new Map(rows.map((e) => [e.url, e]));
}

async function saveLru(entries: CacheEntry[], dropped: string[]): Promise<void> {
  const db = await openLru();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction("lru", "readwrite");
    const s = tx.objectStore("lru");
    for (const e of entries) s.put(e);
    for (const url of dropped) s.delete(url);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

async function touch(url: string): Promise<void> {
  const db = await openLru();
  await new Promise<void>((resolve) => {
    const tx = db.transaction("lru", "readwrite");
    const s = tx.objectStore("lru");
    const r = s.get(url);
    r.onsuccess = () => {
      const e = r.result as CacheEntry | undefined;
      if (e) s.put({ ...e, used: Date.now() });
    };
    tx.oncomplete = tx.onerror = () => resolve();
  });
  db.close();
}

// --- messages and background sync ------------------------------------------------------------

sw.addEventListener("message", (event) => {
  const data = event.data as { type?: string } | null;
  if (data?.type === "clear") {
    event.waitUntil(
      Promise.all([
        caches.delete(TILES_CACHE),
        new Promise<void>((resolve) => {
          const r = indexedDB.deleteDatabase(LRU_DB);
          r.onsuccess = r.onerror = r.onblocked = () => resolve();
        }),
      ])
    );
  }
});

sw.addEventListener("sync", (event) => {
  if (event.tag !== "truebex-outbox") return;
  event.waitUntil(
    sw.clients.matchAll({ type: "window" }).then((pages) => pages.forEach((p) => p.postMessage({ type: "flush", build: BUILD_ID })))
  );
});
