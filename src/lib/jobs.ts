"use client";

// Cloud render jobs (contract render-jobs v1.0, PF6) as the website uses them:
// the Cloud page (usage, recent jobs, cancel, the live preview, the overage
// cap) and the render admin (queue, workers, tokens).
import { ApiError, api } from "@/lib/api";
import { CLOUD } from "@/lib/constants";

const CONTRACT = { "X-Truebex-Contract": "render-jobs/1.0" };

export type JobKind = "panorama" | "tiles" | "pack" | "wind" | "energy" | "acoustics" | "texture";
export type JobState = "queued" | "claimed" | "running" | "succeeded" | "failed" | "cancelled" | "expired";
export type Face = "n" | "e" | "s" | "w" | "u" | "d";
export const FACES: readonly Face[] = ["n", "e", "s", "w", "u", "d"];

export interface JobRecord {
  job_id: string;
  kind: JobKind;
  state: JobState;
  rev: number;
  project_id: string | null;
  at_seq: number;
  progress: number;
  message: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  attempts: number;
  cost_units_estimate: number;
  cost_units: number | null;
  output_ready: boolean;
  error: { code: string; message: string } | null;
  views: string[];
  follow: boolean;
  quality: string;
}

export interface TileFace {
  rendered: boolean;
  reason: string;
  /** Per level, its tiles row by row from the top-left (SHA-256). */
  tiles: string[][];
}

export interface TileView {
  view: string;
  title?: string;
  face_px: number;
  tile_px: number;
  levels: number[];
  faces: Record<Face, TileFace>;
}

/** The tile manifest (`truebex-tiles/1`, contract §6.2) as 5.5 serves it. */
export interface TileManifest {
  schema: string;
  job_id: string;
  at_seq: number;
  tiles_base: string;
  views: TileView[];
  faces_rendered: number;
  faces_reused: number;
}

export interface CloudUsage {
  period_start: string;
  period_end: string;
  used_cu: number;
  limit_cu: number | null;
  remaining_cu: number | null;
  classes: Record<string, number>;
  by_kind: Record<string, number>;
  daily: { day: string; cu: number }[];
  reserved_cu: number;
  plan: string;
  overage: { allowed: boolean; cap_cu: number; used_cu: number; price_minor: number; currency: string };
}

const path = (id: string) => `/jobs/${encodeURIComponent(id)}`;

export const getCloudUsage = () => api<CloudUsage>("/jobs/usage", { headers: CONTRACT });

export const listJobs = (cursor?: string | null) =>
  api<{ jobs: JobRecord[]; next_cursor: string | null }>(
    `/jobs?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    { headers: CONTRACT }
  );

/** 5.2: with `rev`, the server holds the request until the job moves past it (≤ 25 s). */
export const getJob = (id: string, rev?: number, waitS = 0, signal?: AbortSignal) =>
  api<JobRecord>(`${path(id)}${rev !== undefined ? `?rev=${rev}&wait_s=${waitS}` : ""}`, { headers: CONTRACT, signal });

export const cancelJob = (id: string) => api<JobRecord>(`${path(id)}/cancel`, { method: "POST", headers: CONTRACT });

export const getOutput = (id: string) => api<TileManifest>(`${path(id)}/output`, { headers: CONTRACT });

export const setOverageCap = (capCu: number) =>
  api<CloudUsage>("/jobs/usage/overage", { method: "PUT", json: { cap_cu: capCu }, headers: CONTRACT });

/** "1.5" cost units: one decimal, as the platform charges them. */
export function formatCu(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(value);
}

export function formatMoney(minor: number, currency: string): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(minor / 100);
}

export function jobError(err: unknown): string {
  if (err instanceof ApiError && err.code === "plan_required") return CLOUD.meter.none;
  return err instanceof Error ? err.message : CLOUD.errors.generic;
}

// --- the render admin ------------------------------------------------------------

export interface WorkerRow {
  worker_id: string;
  kinds: JobKind[];
  class: string;
  pool: string;
  pool_state: "running" | "stopped";
  app_version: string | null;
  doc_version_max: number | null;
  last_heartbeat_at: string | null;
  created_at: string | null;
  revoked_at: string | null;
  job_id?: string | null;
}

export interface RenderOverview {
  now: string;
  queue: { kind: JobKind; queued: number; running: number; oldest_wait_s: number | null }[];
  workers: WorkerRow[];
  pool: {
    name: string;
    /** `machines`: running machines of the class; `running`: jobs in progress. */
    classes: { class: string; desired: number | null; machines: number; running: number; queued: number }[];
  };
  cost_by_kind: Record<string, number>;
  period_start: string;
  recent_failures: { job_id: string; kind: JobKind; error: { code: string; message: string } | null; finished_at: string | null }[];
}

export const getRenderOverview = () => api<RenderOverview>("/admin/render");

export const issueWorker = (name: string, kinds: JobKind[], workerClass: string) =>
  api<WorkerRow & { token: string }>("/admin/workers", { method: "POST", json: { name, kinds, class: workerClass } });

export const revokeWorker = (workerId: string) =>
  api<WorkerRow>(`/admin/workers/${encodeURIComponent(workerId)}`, { method: "DELETE" });
