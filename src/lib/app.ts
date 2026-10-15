"use client";

// The mobile web client (PF9) as a client of the platform: the person and
// their author id, projects (PF4, contract project-log), the snapshot's
// project digest (PF9's proposal for §6.4), the project's followed panorama
// sets (PF6's tiles through PF9's members' read), pushes of `action`
// operations, the head of the log, presence, and regional prices and
// same-category products (PF7, contract marketplace-api). The session token
// stays where the site keeps it (lib/api.ts); the service worker never sees it.
// The answers' shapes come from openapi/clients.json, the document the Android
// app's Dart client is generated from too (PF10, scripts/gen-clients.ps1).

import type { components } from "@/lib/api-clients";
import type { ActionOp, Finish } from "@/viewer/actions";
import { PushError, retryable, type PushAnswer } from "@/viewer/outbox";
import { ApiError, api } from "@/lib/api";
import { APP } from "@/lib/constants";
import type { TileManifest } from "@/lib/jobs";
import type { Price } from "@/lib/market";
import type { Presence } from "@/lib/projects";

type Wire = components["schemas"];

const LOG = { "X-Truebex-Contract": "project-log/1.1" };
const MARKET = { "X-Truebex-Contract": "marketplace-api/1.1" };
const path = (pid: string) => `/projects/${encodeURIComponent(pid)}`;

export type Me = Pick<Wire["UserOut"], "id" | "email" | "name" | "author_id">;

export const getMe = () => api<Me>("/auth/me");

// --- the project digest (truebex-project-digest/1) ---------------------------------------------

export interface DigestWall {
  id: string;
  name: string;
  face: "left" | "right";
}

export interface DigestRoom {
  id: string;
  name: string;
  storey: string | null;
  area_m2?: number | null;
  centroid_mm?: number[];
  theme?: string | null;
  walls?: DigestWall[];
  finishes?: { floor?: Finish | null };
}

export interface DigestView {
  id: string;
  name: string;
  storey?: string | null;
  room?: string | null;
  eye_mm?: number[];
  yaw_deg?: number;
}

export interface DigestProduct {
  id: string;
  name: string;
  room: string | null;
  category?: string;
  product: { supplier_id: string; sku: string; variant_id: string };
}

export interface DigestOpening {
  id: string;
  kind: "door" | "window" | "opening";
  name: string;
  room?: string | null;
  host?: string | null;
}

export interface ProjectDigest {
  schema: string;
  region?: string | null;
  storeys: { id: string; name: string; elevation_mm?: number }[];
  rooms: DigestRoom[];
  views: DigestView[];
  products: DigestProduct[];
  openings?: DigestOpening[];
  themes: { id: string; name: string }[];
}

/** The digest and the snapshot it belongs to (its operation and time label a stale one). */
export interface DigestSnapshot {
  snapshot_id: string;
  at_seq: number;
  created_at: string;
  sha256: string;
  digest: ProjectDigest;
}

type SnapshotAnswer = Wire["Snapshot"];

/** 5.9 and its digest file; null when the project has no snapshot or no digest yet. */
export async function latestDigest(pid: string, known?: DigestSnapshot | null): Promise<DigestSnapshot | null> {
  let snap: SnapshotAnswer;
  try {
    snap = await api<SnapshotAnswer>(`${path(pid)}/snapshots/latest`, { headers: LOG });
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
  const file = snap.files.digest;
  if (!file) return null;
  if (known && known.sha256 === file.sha256) return { ...known, snapshot_id: snap.snapshot_id, at_seq: snap.at_seq, created_at: snap.created_at };
  let res: Response;
  try {
    // A signed URL: no Authorization header (the storage checks the signature).
    res = await fetch(file.url);
  } catch {
    throw new ApiError(0, APP.errors.network);
  }
  if (!res.ok) throw new ApiError(res.status, APP.errors.generic);
  const digest = (await res.json()) as ProjectDigest;
  if (digest?.schema !== "truebex-project-digest/1") return null;
  return { snapshot_id: snap.snapshot_id, at_seq: snap.at_seq, created_at: snap.created_at, sha256: file.sha256, digest };
}

// --- panoramas: the project's followed sets ------------------------------------------------------

export type PanoramaSet = Wire["PanoramaSet"];

export interface SetState {
  rev: number;
  job_id: string | null;
  at_seq: number;
  following: boolean;
  manifest: TileManifest | null;
}

export const listPanoramaSets = (pid: string) => api<{ sets: PanoramaSet[] }>(`${path(pid)}/panoramas`, { headers: LOG });

/** One set's newest manifest; with `rev`, held until the set moves past it (≤ 25 s). */
export const getSetState = (pid: string, setId: string, rev?: number, waitS = 0, signal?: AbortSignal) =>
  api<SetState>(`${path(pid)}/panoramas/${encodeURIComponent(setId)}${rev !== undefined ? `?rev=${rev}&wait_s=${waitS}` : ""}`, {
    headers: LOG,
    signal,
  });

// --- the log: head, push, presence ---------------------------------------------------------------

/** 5.7 with limit 1: the client only follows head_seq, it never applies operations. */
export const waitForHead = (pid: string, after: number, waitS: number, signal?: AbortSignal) =>
  api<Pick<Wire["PullPage"], "head_seq" | "more">>(`${path(pid)}/ops?after=${after}&limit=1&wait_s=${waitS}`, { headers: LOG, signal });

/** 5.6 for the outbox: errors become PushError (retry or give up, contract §8). */
export async function pushOps(pid: string, replicaId: string, ops: ActionOp[]): Promise<PushAnswer> {
  try {
    return await api<Wire["PushAnswer"]>(`${path(pid)}/ops`, { method: "POST", json: { replica_id: replicaId, ops }, headers: LOG });
  } catch (err) {
    if (err instanceof ApiError) throw new PushError(retryable(err.status) || err.status === 401, err.message, err.status, err.code);
    throw new PushError(true, APP.errors.network);
  }
}

export interface PresenceView {
  storey?: string | null;
  eye_mm?: number[];
  yaw_deg?: number;
}

/** 5.17 as `client: "web"`, with the view the person looks at (CL2 shows it). */
export const heartbeatWeb = (pid: string, replicaId: string, view: PresenceView | null, leaving = false) =>
  api<{ ttl_s: number; others: Presence[] }>(`${path(pid)}/presence`, {
    method: "PUT",
    json: { replica_id: replicaId, client: "web", ...(view ? { view } : {}), selection: [], editing: [], leaving },
    headers: LOG,
    keepalive: leaving,
  });

// --- the marketplace (PF7) ------------------------------------------------------------------------

export interface PricedItem {
  supplier_id: string;
  sku: string;
  variant_id: string;
  price: Price | null;
  availability?: { state: string } | null;
}

/** 5.5: prices of the placed products for the project's region (no credential). */
export async function regionPrices(region: string, items: DigestProduct[]): Promise<PricedItem[]> {
  if (!items.length) return [];
  const body = { region, items: items.map((p) => ({ ...p.product, qty: 1 })) };
  const res = await api<Wire["PricesAnswer"]>("/market/prices", { method: "POST", json: body, headers: MARKET, auth: false });
  return res.items;
}

export interface SwapChoice {
  product_id: string;
  name: string;
  options: string;
  ref: { supplier_id: string; sku: string; variant_id: string };
  price: Price | null;
}

type SearchAnswer = Wire["SearchAnswer"];
type ProductAnswer = Wire["ProductAnswer"];

/** Same-category products (5.3 → 5.4) a placed product can be swapped for, its own variant left out. */
export async function swapChoices(product: DigestProduct, region: string | null | undefined): Promise<SwapChoice[]> {
  if (!product.category) return [];
  const q = new URLSearchParams({ category: product.category, limit: "6" });
  if (region) q.set("region", region);
  const found = await api<SearchAnswer>(`/market/search?${q}`, { headers: MARKET, auth: false });
  const out: SwapChoice[] = [];
  for (const hit of found.results) {
    const detail = await api<ProductAnswer>(
      `/market/products/${encodeURIComponent(hit.product_id)}${region ? `?region=${encodeURIComponent(region)}` : ""}`,
      { headers: MARKET, auth: false }
    );
    for (const v of detail.variants.slice(0, 4)) {
      const ref = { supplier_id: detail.supplier_id, sku: detail.sku, variant_id: v.variant_id };
      const current = ref.supplier_id === product.product.supplier_id && ref.sku === product.product.sku && ref.variant_id === product.product.variant_id;
      if (current || ["out_of_stock", "discontinued"].includes(v.availability?.state ?? "")) continue;
      out.push({
        product_id: detail.product_id,
        name: detail.name,
        options: Object.values(v.options ?? {}).join(", "),
        ref,
        price: v.price ?? null,
      });
    }
  }
  return out;
}

// --- finishes the phone offers (agent-interface §5.10 finish objects) -----------------------------

export interface FinishChoice {
  id: string;
  label: string;
  finish: Finish;
}

const FLOOR: Record<string, Finish> = {
  oak: { kind: "pattern3d", pattern: "slat", texture: "oak", tile_mm: [180, 1200] },
  stone: { kind: "pattern3d", pattern: "tile", texture: "stone", tile_mm: [600, 600] },
  concrete: { kind: "paint", colour: "#9A9A96", roughness: 0.3 },
  sand: { kind: "paint", colour: "#C8B79E", roughness: 0.6 },
};

const WALL: Record<string, Finish> = {
  chalk: { kind: "paint", colour: "#F2F0EA", roughness: 0.8 },
  sage: { kind: "paint", colour: "#9CAF88", roughness: 0.8 },
  lattice: { kind: "wallpaper", texture: "lattice" },
  brick: { kind: "pattern3d", pattern: "brick", texture: "brick", tile_mm: [215, 65] },
};

const choices = (set: Record<string, Finish>, labels: Record<string, string>): FinishChoice[] =>
  Object.entries(set).map(([id, finish]) => ({ id, label: labels[id] ?? id, finish }));

export const FLOOR_FINISHES = choices(FLOOR, APP.finishes.floor);
export const WALL_FINISHES = choices(WALL, APP.finishes.wall);

/** The palette entry a finish matches, if any (to name the current one). */
export function finishLabel(finish: Finish | null | undefined, palette: FinishChoice[]): string | null {
  if (!finish) return null;
  const match = palette.find((c) => JSON.stringify(c.finish) === JSON.stringify(finish));
  return match ? match.label : APP.rooms.customFinish;
}
