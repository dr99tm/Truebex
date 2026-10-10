"use client";

// The project service (contract project-log v1.0, PF4) as the website uses
// it: the Projects dashboard (list, people, versions, restore, delete) and
// the invitation page. Deleting needs this session: the app cannot.
import { ApiError, api } from "@/lib/api";
import { PROJECTS } from "@/lib/constants";

const CONTRACT = { "X-Truebex-Contract": "project-log/1.0" };

export type ProjectRole = "owner" | "editor" | "viewer";

export interface SnapshotSummary {
  snapshot_id: string;
  at_seq: number;
  doc_version: number;
  created_at: string;
}

export interface ProjectRecord {
  project_id: string;
  name: string;
  role: ProjectRole;
  owner: { user_id: number; name: string } | null;
  created_at: string;
  updated_at: string;
  head_seq: number;
  latest_snapshot: SnapshotSummary | null;
  doc_version: number;
  members: number;
  bytes: number;
}

export interface Member {
  user_id: number | null;
  invite_id: string | null;
  email: string;
  name: string | null;
  role: ProjectRole;
  state: "active" | "invited";
  invited_at: string | null;
  accepted_at: string | null;
}

export interface OpenProject extends Omit<ProjectRecord, "members"> {
  members: Member[];
  quota: { bytes: number | null; bytes_used: number };
}

export interface Version {
  version_id: string;
  name: string;
  note: string;
  at_seq: number;
  snapshot_id: string;
  created_by: number;
  created_at: string;
}

export interface Presence {
  user_id: number;
  name: string;
  replica_id: string;
  client: "desktop" | "web" | "android" | "headset" | "worker";
  seen_at: string;
  selection: string[];
  editing: string[];
}

/** 32 lowercase hex: replica ids and Idempotency-Keys. */
export function hex32(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

const once = () => ({ ...CONTRACT, "Idempotency-Key": hex32() });
const path = (pid: string) => `/projects/${encodeURIComponent(pid)}`;

export const listProjects = (cursor?: string | null) =>
  api<{ projects: ProjectRecord[]; next_cursor: string | null }>(
    `/projects${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`,
    { headers: CONTRACT }
  );

export const createProject = (name: string) =>
  api<ProjectRecord>("/projects", { method: "POST", json: { name, doc_version: 38 }, headers: once() });

export const getProject = (pid: string) => api<OpenProject>(path(pid), { headers: CONTRACT });

export const renameProject = (pid: string, name: string) =>
  api<ProjectRecord>(path(pid), { method: "PATCH", json: { name }, headers: CONTRACT });

export const deleteProject = (pid: string) =>
  api<void>(path(pid), { method: "DELETE", headers: CONTRACT });

export const listVersions = (pid: string) =>
  api<{ versions: Version[] }>(`${path(pid)}/versions`, { headers: CONTRACT });

export const nameVersion = (pid: string, body: { name: string; note: string; at_seq: number; snapshot_id: string }) =>
  api<Version>(`${path(pid)}/versions`, { method: "POST", json: body, headers: once() });

export const restoreVersion = (pid: string, versionId: string) =>
  api<{ op: { server_seq: number } }>(`${path(pid)}/versions/${encodeURIComponent(versionId)}/restore`, {
    method: "POST",
    headers: once(),
  });

export const inviteMember = (pid: string, email: string, role: Exclude<ProjectRole, "owner">) =>
  api<Member>(`${path(pid)}/members`, { method: "POST", json: { email, role }, headers: once() });

/** A member by user id, or a pending invitation by invite id. */
export const memberRef = (m: Member) => String(m.user_id ?? m.invite_id);

export const changeRole = (pid: string, ref: string, role: Exclude<ProjectRole, "owner">) =>
  api<Member>(`${path(pid)}/members/${encodeURIComponent(ref)}`, { method: "PATCH", json: { role }, headers: CONTRACT });

export const removeMember = (pid: string, ref: string) =>
  api<void>(`${path(pid)}/members/${encodeURIComponent(ref)}`, { method: "DELETE", headers: CONTRACT });

export const heartbeat = (pid: string, replicaId: string, leaving = false) =>
  api<{ ttl_s: number; others: Presence[] }>(`${path(pid)}/presence`, {
    method: "PUT",
    json: { replica_id: replicaId, client: "web", leaving },
    headers: CONTRACT,
    // A page being closed still sends its "leaving" heartbeat.
    keepalive: leaving,
  });

export const acceptInvite = (token: string) =>
  api<{ project: ProjectRecord; member: Member }>("/projects/invites/accept", {
    method: "POST",
    json: { token },
    headers: CONTRACT,
  });

/** 1 536 → "1.5 KB", 10 GiB → "10 GB": 1 024-based, as Windows shows sizes. */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = "B";
  for (const u of units) {
    if (value < 1024) break;
    value /= 1024;
    unit = u;
  }
  const shown = value < 10 ? Math.round(value * 10) / 10 : Math.round(value);
  return `${shown} ${unit}`;
}

/** The message to show for a failed call: plan gates in the site's words. */
export function projectError(err: unknown): string {
  if (err instanceof ApiError && err.code === "plan_required") return PROJECTS.errors.plan;
  return err instanceof Error ? err.message : PROJECTS.errors.generic;
}
