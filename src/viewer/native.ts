// The Android app's panorama (PF10): PF9's cube-tile viewer (cube.ts) and its
// look-by-tilting (orientation.ts), hosted in the app's web view. The app
// serves this bundle and every tile from its own loopback server (tiles from
// the phone's cache first, so a panorama seen once shows offline) and drives
// it through `window.truebex`; the page answers on the `TruebexHost` channel
// with JSON messages: `ready`, `turn` (where the person looks) and `hotspot`
// (a label tapped). Built by scripts/build-mobile-viewer.mjs into
// mobile/android/assets/viewer/viewer.js. Framework-free.

import { CubeTileViewer, type CubeHotspot, type CubeView } from "./cube";
import { angleDelta, watchOrientation, type Look } from "./orientation";

export interface NativeView extends CubeView {
  view: string;
  title?: string;
}

interface Host {
  postMessage(message: string): void;
}

export interface NativeApi {
  show(view: NativeView, tilesBase: string, hotspots: CubeHotspot[], yawDeg: number, label: string): void;
  hotspots(spots: CubeHotspot[]): void;
  tilt(on: boolean): void;
}

declare global {
  interface Window {
    TruebexHost?: Host;
    truebex?: NativeApi;
  }
}

const post = (message: Record<string, unknown>) => window.TruebexHost?.postMessage(JSON.stringify(message));

let viewer: CubeTileViewer | null = null;
let shownView: string | null = null;
let stopTilt: (() => void) | null = null;
// The difference between the phone's heading and the view's, kept as the person drags.
let sensor: Look | null = null;
let offset: Look | null = null;

const turned = () => viewer && post({ type: "turn", yaw: viewer.yawDeg, pitch: viewer.pitchDeg });
const onSpot = (id: string) => post({ type: "hotspot", id });

const api: NativeApi = {
  show(view, tilesBase, hotspots, yawDeg, label) {
    const host = document.getElementById("pano");
    if (!host) return;
    if (!viewer) {
      viewer = new CubeTileViewer(host, {
        tilesBase,
        label,
        yawDeg,
        onTurn: (yaw, pitch) => {
          if (sensor) offset = { yawDeg: angleDelta(yaw, sensor.yawDeg), pitchDeg: pitch - sensor.pitchDeg };
          post({ type: "turn", yaw, pitch });
        },
      });
    }
    viewer.root.setAttribute("aria-label", label);
    // A newer manifest of the same view swaps only the tiles that changed.
    viewer.update(view, tilesBase);
    if (shownView !== view.view) {
      if (shownView !== null) viewer.look(yawDeg, 0);
      shownView = view.view;
      turned();
    }
    viewer.setHotspots(hotspots, onSpot);
  },
  hotspots(spots) {
    viewer?.setHotspots(spots, onSpot);
  },
  tilt(on) {
    stopTilt?.();
    stopTilt = null;
    sensor = null;
    offset = null;
    if (!on) return;
    // The first reading anchors to where the view already looks.
    stopTilt = watchOrientation((look) => {
      const v = viewer;
      if (!v) return;
      sensor = look;
      offset ??= { yawDeg: angleDelta(v.yawDeg, look.yawDeg), pitchDeg: v.pitchDeg - look.pitchDeg };
      v.look(look.yawDeg + offset.yawDeg, look.pitchDeg + offset.pitchDeg);
      turned();
    });
  },
};

window.truebex = api;
post({ type: "ready" });
