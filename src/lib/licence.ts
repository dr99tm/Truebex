"use client";

// The licence API (contract licence-api v1.0) as the website uses it: devices,
// approving a sign-in from the app, the release feed and download links.
import { api } from "@/lib/api";
import type { ReleaseFeed } from "@/lib/releases";

export type { ReleaseFeed, ReleaseManifest } from "@/lib/releases";

const CONTRACT = { "X-Truebex-Contract": "licence-api/1.0" };

export interface Device {
  device_id: string;
  name: string;
  os: string;
  app_version: string;
  activated_at: string;
  last_seen_at: string;
  current: boolean;
  deactivated_at?: string | null;
}

export interface LinkInfo {
  link_code: string;
  device_name: string;
  app_version: string;
  status: "pending" | "approved" | "denied" | "spent";
  expires_at: string;
}

export interface DownloadLink {
  url: string;
  expires_at: string;
  bytes: number;
  sha256: string;
}

export const listDevices = () =>
  api<{ devices: Device[]; limit: number | null }>("/licence/devices", { headers: CONTRACT });

export const removeDevice = (deviceId: string) =>
  api<Device>(`/licence/devices/${encodeURIComponent(deviceId)}`, {
    method: "DELETE",
    headers: CONTRACT,
  });

export const lookupLink = (code: string) =>
  api<LinkInfo>(`/licence/link/${encodeURIComponent(code)}`, { headers: CONTRACT });

export const decideLink = (code: string, approve: boolean) =>
  api<{ status: "approved" | "denied"; device_name: string }>("/licence/link/approve", {
    method: "POST",
    json: { link_code: code, approve },
    headers: CONTRACT,
  });

export const getReleaseFeed = (channel: "stable" | "beta" = "stable") =>
  api<ReleaseFeed>(`/releases/feed?channel=${channel}&platform=win64`, {
    auth: false,
    headers: CONTRACT,
  });

/** A fresh 15-minute download URL (asked for at click time, never cached). */
export const getDownloadLink = (version: string) =>
  api<DownloadLink>(`/releases/${encodeURIComponent(version)}/download?platform=win64`, {
    auth: false,
    headers: { ...CONTRACT, Accept: "application/json" },
  });

/** `QX7D K9MP`, `qx7dk9mp` → `QX7D-K9MP`; null when it cannot be a code. */
export function normaliseLinkCode(raw: string | null | undefined): string | null {
  const compact = (raw ?? "").replace(/[\s-]/g, "").toUpperCase();
  if (!/^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{8}$/.test(compact)) return null;
  return `${compact.slice(0, 4)}-${compact.slice(4)}`;
}
