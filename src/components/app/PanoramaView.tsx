"use client";

import { useEffect, useRef } from "react";
import { APP } from "@/lib/constants";
import type { TileView } from "@/lib/jobs";
import { CubeTileViewer, type CubeHotspot } from "@/viewer/cube";
import { angleDelta, watchOrientation, type Look } from "@/viewer/orientation";

/**
 * One view of a followed set, full screen, through the shared cube-tile
 * viewer (src/viewer/cube.ts): drag (or tilt the phone) to look around, tap a
 * hotspot to go to another view. `update()` swaps only the tiles a newer
 * manifest changed. `lookRef` always holds where the person looks.
 */
export function PanoramaView({
  view,
  tilesBase,
  hotspots,
  onHotspot,
  tilt,
  startYaw,
  lookRef,
}: {
  view: TileView;
  tilesBase: string;
  hotspots: CubeHotspot[];
  onHotspot: (id: string) => void;
  tilt: boolean;
  startYaw: number;
  lookRef: React.MutableRefObject<Look>;
}) {
  const host = useRef<HTMLDivElement>(null);
  const viewer = useRef<CubeTileViewer | null>(null);
  // The difference between the phone's heading and the view's, kept as the person drags.
  const offset = useRef<Look | null>(null);
  const sensor = useRef<Look | null>(null);
  const shownView = useRef<string | null>(null);

  // Mount once; tiles swap on every manifest.
  useEffect(() => {
    if (!host.current) return;
    if (!viewer.current) {
      viewer.current = new CubeTileViewer(host.current, {
        tilesBase,
        label: view.title || APP.project.view,
        yawDeg: startYaw,
        onTurn: (yaw, pitch) => {
          lookRef.current = { yawDeg: yaw, pitchDeg: pitch };
          if (sensor.current) {
            offset.current = { yawDeg: angleDelta(yaw, sensor.current.yawDeg), pitchDeg: pitch - sensor.current.pitchDeg };
          }
        },
      });
    }
    viewer.current.update(view, tilesBase);
    if (shownView.current !== view.view) {
      // Another view: face where its saved view looks.
      if (shownView.current !== null) viewer.current.look(startYaw, 0);
      shownView.current = view.view;
      lookRef.current = { yawDeg: viewer.current.yawDeg, pitchDeg: viewer.current.pitchDeg };
    }
  }, [view, tilesBase, startYaw, lookRef]);

  useEffect(() => {
    viewer.current?.setHotspots(hotspots, onHotspot);
  }, [hotspots, onHotspot]);

  useEffect(
    () => () => {
      viewer.current?.destroy();
      viewer.current = null;
    },
    []
  );

  // Tilt to look: the first reading anchors to where the view already looks.
  useEffect(() => {
    if (!tilt) {
      sensor.current = null;
      offset.current = null;
      return;
    }
    return watchOrientation((look) => {
      const v = viewer.current;
      if (!v) return;
      sensor.current = look;
      offset.current ??= { yawDeg: angleDelta(v.yawDeg, look.yawDeg), pitchDeg: v.pitchDeg - look.pitchDeg };
      v.look(look.yawDeg + offset.current.yawDeg, look.pitchDeg + offset.current.pitchDeg);
      lookRef.current = { yawDeg: v.yawDeg, pitchDeg: v.pitchDeg };
    });
  }, [tilt, lookRef]);

  return <div ref={host} className="absolute inset-0" />;
}
