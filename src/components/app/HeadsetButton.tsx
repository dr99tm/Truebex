"use client";

import { useEffect, useRef, useState } from "react";
import { Glasses } from "lucide-react";
import { HeadsetView, immersiveSupported, type XrScene } from "@/viewer/xr";

/**
 * "View in headset": offered only where the browser says an immersive-vr
 * session is supported (feature detection). The session is asked for inside
 * the tap; the 3D library loads after it (src/viewer/xr.ts). While it runs,
 * every newer scene (tiles, view, menu) is handed to it.
 */
export function HeadsetButton({
  scene,
  label,
  onHotspot,
  onMenu,
  onError,
}: {
  scene: XrScene | null;
  label: string;
  onHotspot: (id: string) => void;
  onMenu: (id: string) => void;
  onError: (message: string) => void;
}) {
  const [supported, setSupported] = useState(false);
  const [running, setRunning] = useState(false);
  const session = useRef<HeadsetView | null>(null);
  const handlers = useRef({ onHotspot, onMenu });

  useEffect(() => {
    handlers.current = { onHotspot, onMenu };
  }, [onHotspot, onMenu]);

  useEffect(() => {
    let live = true;
    immersiveSupported().then((ok) => live && setSupported(ok));
    return () => {
      live = false;
      session.current?.end();
    };
  }, []);

  useEffect(() => {
    if (scene) session.current?.update(scene);
  }, [scene]);

  if (!supported || !scene) return null;

  const start = async () => {
    try {
      session.current = await HeadsetView.start(scene, {
        onHotspot: (id) => handlers.current.onHotspot(id),
        onMenu: (id) => handlers.current.onMenu(id),
        onEnd: () => {
          session.current = null;
          setRunning(false);
        },
      });
      setRunning(true);
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <button
      type="button"
      onClick={() => void start()}
      disabled={running}
      className="flex h-10 items-center gap-2 rounded-[var(--radius-button)] border border-accent/60 bg-background/80 px-3 text-sm text-text-primary backdrop-blur disabled:opacity-50"
    >
      <Glasses className="h-4 w-4" aria-hidden="true" />
      {label}
    </button>
  );
}
