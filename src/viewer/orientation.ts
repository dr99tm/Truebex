// Look around a panorama by turning the phone (W3C DeviceOrientation Event):
// the direction out of the back of the screen, as a compass bearing and a
// pitch, from the device's alpha, beta and gamma (intrinsic Z-X'-Y'' angles,
// earth frame x east, y north, z up). The screen's own rotation does not
// change where the back of the phone points, so portrait and landscape need
// no correction. Alpha is relative on most phones; the viewer anchors the
// first reading to where the person already looks. Framework-free.

export interface Look {
  yawDeg: number;
  pitchDeg: number;
}

const RAD = Math.PI / 180;

/** The bearing (0 = north, 90 = east) and pitch (up positive) the back of the phone faces. */
export function lookFromOrientation(alphaDeg: number, betaDeg: number, gammaDeg: number): Look {
  const [a, b, g] = [alphaDeg * RAD, betaDeg * RAD, gammaDeg * RAD];
  const [ca, sa, cb, sb, cg, sg] = [Math.cos(a), Math.sin(a), Math.cos(b), Math.sin(b), Math.cos(g), Math.sin(g)];
  // -(R · ẑ) for R = Rz(alpha) · Rx(beta) · Ry(gamma).
  const x = -(ca * sg + sa * sb * cg);
  const y = -(sa * sg - ca * sb * cg);
  const z = -(cb * cg);
  const yaw = (Math.atan2(x, y) / RAD + 360) % 360;
  const pitch = Math.asin(Math.max(-1, Math.min(1, z))) / RAD;
  return { yawDeg: yaw, pitchDeg: pitch };
}

type PermissionApi = { requestPermission?: () => Promise<"granted" | "denied"> };

/** Device orientation exists here at all (feature detection, never the user agent). */
export function orientationAvailable(): boolean {
  return typeof window !== "undefined" && "DeviceOrientationEvent" in window;
}

/** iOS asks once, from a tap; elsewhere the events simply flow. */
export async function requestOrientation(): Promise<boolean> {
  if (!orientationAvailable()) return false;
  const api = (window as unknown as { DeviceOrientationEvent: PermissionApi }).DeviceOrientationEvent;
  if (typeof api.requestPermission !== "function") return true;
  try {
    return (await api.requestPermission()) === "granted";
  } catch {
    return false;
  }
}

/** Calls `onLook` with each reading until the returned function is called. */
export function watchOrientation(onLook: (look: Look) => void): () => void {
  const handler = (e: DeviceOrientationEvent) => {
    if (e.alpha === null || e.beta === null || e.gamma === null) return;
    onLook(lookFromOrientation(e.alpha, e.beta, e.gamma));
  };
  window.addEventListener("deviceorientation", handler);
  return () => window.removeEventListener("deviceorientation", handler);
}

/** The signed difference a − b in degrees, in (−180, 180]. */
export function angleDelta(a: number, b: number): number {
  const d = (((a - b) % 360) + 540) % 360 - 180;
  return d === -180 ? 180 : d;
}

/** Bearing and pitch from one eye to another (doc mm): a hotspot's direction. */
export function bearingTo(from: number[], to: number[]): Look {
  const [dx, dy, dz] = [to[0] - from[0], to[1] - from[1], (to[2] ?? 0) - (from[2] ?? 0)];
  const flat = Math.hypot(dx, dy);
  const yaw = (Math.atan2(dx, dy) / RAD + 360) % 360;
  // Aim a little below the horizon: a hotspot marks the floor of the other room.
  const pitch = flat > 0 ? Math.atan2(dz, flat) / RAD - 8 : 0;
  return { yawDeg: yaw, pitchDeg: Math.max(-60, Math.min(60, pitch)) };
}
