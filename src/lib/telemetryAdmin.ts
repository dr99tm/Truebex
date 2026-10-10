"use client";

// The telemetry admin dashboard's calls (server/app/routers/admin_telemetry.py).
import { api, API_URL, ApiError, getToken } from "@/lib/api";

export interface TelemetrySummary {
  days: number;
  installs_per_day: { day: string; count: number }[];
  versions: { version: string; installs: number }[];
  top_events: { name: string; events: number }[];
  timings: { name: string; p50_ms: number | null; p95_ms: number | null; samples: number }[];
  crash_free_sessions: number | null;
  crashes: number;
  sessions: number;
}

export type CrashStatus = "new" | "investigating" | "fixed" | "ignored";

export interface CrashGroup {
  signature: string;
  title: string;
  kind: string;
  status: CrashStatus;
  count: number;
  first_seen: string;
  last_seen: string;
  versions: string[];
  fixed_in: string | null;
  note: string | null;
}

export interface CrashReport {
  crash_id: string;
  received_at: string;
  kind: string;
  app_version: string;
  os: string | null;
  gpu_driver: string | null;
  exception: Record<string, string> | null;
  frames: string[];
  symbolicated: boolean;
  has_minidump: boolean;
  has_log: boolean;
}

export interface CrashGroupDetail extends CrashGroup {
  reports: CrashReport[];
}

export type FeedbackStatus = "new" | "replied" | "closed";

export interface FeedbackItem {
  feedback_id: string;
  received_at: string;
  kind: "bug" | "idea" | "question" | "praise";
  text: string;
  reply: boolean;
  email: string | null;
  app_version: string;
  os: string | null;
  status: FeedbackStatus;
  replied_at: string | null;
  has_screenshot: boolean;
  has_log: boolean;
}

export interface SignedLink {
  url: string;
  expires_at: string;
}

export type TelemetryTab = "overview" | "crashes" | "feedback";

export const getSummary = (days: number) =>
  api<TelemetrySummary>(`/admin/telemetry/summary?days=${days}`);
export const listCrashGroups = () => api<CrashGroup[]>("/admin/telemetry/crashes");
export const getCrashGroup = (signature: string) =>
  api<CrashGroupDetail>(`/admin/telemetry/crashes/${signature}`);
export const updateCrashGroup = (
  signature: string,
  patch: Partial<Pick<CrashGroup, "status" | "title" | "fixed_in" | "note">>
) => api<CrashGroup>(`/admin/telemetry/crashes/${signature}`, { method: "PATCH", json: patch });
export const crashFileLink = (crashId: string, file: "minidump" | "log") =>
  api<SignedLink>(`/admin/telemetry/reports/${crashId}/${file}`);

export const listFeedback = () => api<FeedbackItem[]>("/admin/feedback");
export const updateFeedback = (id: string, status: FeedbackStatus) =>
  api<FeedbackItem>(`/admin/feedback/${id}`, { method: "PATCH", json: { status } });
export const feedbackFileLink = (id: string, file: "screenshot" | "log") =>
  api<SignedLink>(`/admin/feedback/${id}/${file}`);
export const replyToFeedback = (id: string, text: string) =>
  api<FeedbackItem>(`/admin/feedback/${id}/reply`, { method: "POST", json: { text } });

/** Download a tab as CSV (the request needs the session token, so no plain link). */
export async function downloadCsv(tab: TelemetryTab, days: number): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/admin/telemetry/export.csv?tab=${tab}&days=${days}`, {
      headers: { Authorization: `Bearer ${getToken() ?? ""}` },
    });
  } catch {
    throw new ApiError(0, "Can't reach the Truebex server. Please try again in a moment.");
  }
  if (!res.ok) throw new ApiError(res.status, `Export failed (${res.status}).`);
  const blob = await res.blob();
  const name =
    /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ??
    `truebex-telemetry-${tab}.csv`;
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(href);
}
