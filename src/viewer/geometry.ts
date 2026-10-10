// Pure geometry of the share page's panorama view (no DOM): compass bearings,
// the camera-space direction of a hotspot, the phone's gyroscope as a look
// direction, and which image a device should load. Unit-tested under Node
// (server/tests/test_site_pf5.py).

import type { Panorama } from "./types";

export const DEG = Math.PI / 180;

export interface PanoSources {
  preview: string | null;
  main: string | null;
}

/** Degrees in (-180, 180]. */
export function wrap180(deg: number): number {
  const d = ((((deg + 180) % 360) + 360) % 360) - 180;
  return d === -180 ? 180 : d;
}

/** The camera-space direction of a bearing / pitch, seen from `view`. */
export function toCamera(
  bearing: number,
  pitch: number,
  view: { bearing: number; pitch: number },
): [number, number, number] {
  const lon = wrap180(bearing - view.bearing) * DEG;
  const lat = pitch * DEG;
  const t = view.pitch * DEG;
  // d(lon, lat) with the view's yaw already removed, then pitched by -t.
  const dx = Math.sin(lon) * Math.cos(lat);
  const dy = Math.sin(lat);
  const dz = -Math.cos(lon) * Math.cos(lat);
  return [dx, Math.cos(t) * dy + Math.sin(t) * dz, -Math.sin(t) * dy + Math.cos(t) * dz];
}

/**
 * Where the phone's back camera points (three.js DeviceOrientationControls'
 * mapping): compass-style yaw (growing clockwise) and pitch, in degrees.
 */
export function deviceLook(alpha: number, beta: number, gamma: number, screenAngle: number): { yaw: number; pitch: number } {
  const x = beta * DEG;
  const y = alpha * DEG;
  const z = -gamma * DEG;
  const c1 = Math.cos(x / 2), c2 = Math.cos(y / 2), c3 = Math.cos(z / 2);
  const s1 = Math.sin(x / 2), s2 = Math.sin(y / 2), s3 = Math.sin(z / 2);
  // Euler order YXZ.
  let q: [number, number, number, number] = [
    s1 * c2 * c3 + c1 * s2 * s3,
    c1 * s2 * c3 - s1 * c2 * s3,
    c1 * c2 * s3 - s1 * s2 * c3,
    c1 * c2 * c3 + s1 * s2 * s3,
  ];
  q = qmul(q, [-Math.SQRT1_2, 0, 0, Math.SQRT1_2]); // the camera looks out of the back
  const o = (-screenAngle * DEG) / 2;
  q = qmul(q, [0, 0, Math.sin(o), Math.cos(o)]);
  const [fx, fy, fz] = qrotate(q, [0, 0, -1]);
  return { yaw: Math.atan2(fx, -fz) / DEG, pitch: Math.asin(Math.max(-1, Math.min(1, fy))) / DEG };
}

type Quat = [number, number, number, number];

function qmul(a: Quat, b: Quat): Quat {
  const [ax, ay, az, aw] = a;
  const [bx, by, bz, bw] = b;
  return [
    ax * bw + aw * bx + ay * bz - az * by,
    ay * bw + aw * by + az * bx - ax * bz,
    az * bw + aw * bz + ax * by - ay * bx,
    aw * bw - ax * bx - ay * by - az * bz,
  ];
}

function qrotate(q: Quat, v: [number, number, number]): [number, number, number] {
  const [x, y, z, w] = q;
  const tx = 2 * (y * v[2] - z * v[1]);
  const ty = 2 * (z * v[0] - x * v[2]);
  const tz = 2 * (x * v[1] - y * v[0]);
  return [
    v[0] + w * tx + (y * tz - z * ty),
    v[1] + w * ty + (z * tx - x * tz),
    v[2] + w * tz + (x * ty - y * tx),
  ];
}

/** The connection asks to save data (Save-Data, or 2G / 3G, or cellular). */
export function meteredConnection(): boolean {
  const c = (navigator as Navigator & {
    connection?: { saveData?: boolean; effectiveType?: string; type?: string };
  }).connection;
  if (!c) return false;
  return Boolean(c.saveData) || c.type === "cellular" || ["slow-2g", "2g", "3g"].includes(c.effectiveType ?? "");
}

/**
 * The image to show: the 8k original only on a desktop GPU that holds it and
 * an unmetered connection; otherwise the 4096 derivative. Never the original
 * on a phone (a coarse pointer), whatever its GPU reports.
 */
export function pickSources(pano: Panorama, maxTexture: number, fileUrl: string | null, opts: { coarse: boolean; metered: boolean }): PanoSources {
  const d4096 = pano.derivatives?.["pano-4096"];
  const d1024 = pano.derivatives?.["pano-1024"];
  let main = d4096?.url ?? fileUrl;
  const big = pano.width > (d4096?.width ?? 0);
  if (fileUrl && big && pano.width <= maxTexture && !opts.coarse && !opts.metered) main = fileUrl;
  if (d4096 && d4096.width > maxTexture) main = d1024?.url ?? main;
  return { preview: d1024?.url ?? null, main };
}
