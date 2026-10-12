// The share viewer's cube-tile mode (PF6): a panorama rendered in the cloud
// as six faces of content-addressed JPEG tiles (contract render-jobs §6.2),
// shown from inside a CSS 3D cube. Framework-free, so the share page (PF5's
// viewer bundle) and the dashboard's live preview both mount it.
//
// Faces n, e, s, w look north (+Y), east, south and west with +Z up; u looks
// up and d down, both with the image's top edge toward north. Seen from the
// cube's centre, n is ahead at yaw 0, e to its right, u overhead. Each face
// shows one level (the smallest whose pixels cover the face on screen);
// `update()` swaps only the tiles whose hashes changed, after they load, so an
// edit re-renders two faces and the viewer fetches only those.
//
// PF9 adds what the mobile client needs, all optional: hotspots (buttons at a
// bearing and pitch that lead to another view), `look()` for device
// orientation, and `onTurn` when the person turns the view by hand.

export type CubeFace = "n" | "e" | "s" | "w" | "u" | "d";

export interface CubeFaceTiles {
  tiles: string[][];
}

export interface CubeView {
  face_px: number;
  tile_px: number;
  levels: number[];
  faces: Record<CubeFace, CubeFaceTiles>;
}

export interface CubeOptions {
  /** `<tiles_base>/<sha256>.jpg` (the manifest's `tiles_base`). */
  tilesBase: string;
  /** What the cube shows, for screen readers. */
  label: string;
  hfovDeg?: number;
  yawDeg?: number;
  pitchDeg?: number;
  /** Called after the person turns the view (drag or keys), with the new look. */
  onTurn?: (yawDeg: number, pitchDeg: number) => void;
}

/** A button floating at a compass bearing and pitch (up positive), PF9. */
export interface CubeHotspot {
  id: string;
  label: string;
  yawDeg: number;
  pitchDeg: number;
}

const ORDER: CubeFace[] = ["n", "e", "s", "w", "u", "d"];

// Each face starts facing the viewer at the centre; these place it on the cube
// (H = half the face) so its image reads as the camera saw it.
function faceTransform(face: CubeFace, half: number): string {
  const t = `translateZ(${-half}px)`;
  switch (face) {
    case "n":
      return t;
    case "e":
      return `rotateY(-90deg) ${t}`;
    case "s":
      return `rotateY(180deg) ${t}`;
    case "w":
      return `rotateY(90deg) ${t}`;
    case "u":
      return `rotateX(-90deg) ${t} rotateZ(180deg)`;
    case "d":
      return `rotateX(90deg) ${t}`;
  }
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

export class CubeTileViewer {
  readonly root: HTMLDivElement;
  private readonly cube: HTMLDivElement;
  private readonly faces = new Map<CubeFace, HTMLDivElement>();
  private readonly shown = new Map<string, string>(); // `${face}:${index}` -> sha
  private view: CubeView | null = null;
  private level = -1;
  private yaw: number;
  private pitch: number;
  private hfov: number;
  private focal = 500;
  private readonly resize: ResizeObserver | null = null;
  private drag: { x: number; y: number; yaw: number; pitch: number } | null = null;
  private readonly spots: HTMLDivElement;
  private hotspots: { spot: CubeHotspot; el: HTMLButtonElement }[] = [];

  constructor(
    private readonly host: HTMLElement,
    private readonly options: CubeOptions
  ) {
    this.yaw = options.yawDeg ?? 0;
    this.pitch = options.pitchDeg ?? 0;
    this.hfov = options.hfovDeg ?? 80;
    this.root = document.createElement("div");
    this.root.tabIndex = 0;
    this.root.setAttribute("role", "img");
    this.root.setAttribute("aria-label", options.label);
    Object.assign(this.root.style, {
      position: "relative",
      width: "100%",
      height: "100%",
      overflow: "hidden",
      cursor: "grab",
      touchAction: "none",
      userSelect: "none",
      background: "#161616",
    });
    this.cube = document.createElement("div");
    Object.assign(this.cube.style, {
      position: "absolute",
      left: "50%",
      top: "50%",
      width: "0",
      height: "0",
      transformStyle: "preserve-3d",
    });
    for (const face of ORDER) {
      const el = document.createElement("div");
      el.dataset.face = face;
      Object.assign(el.style, { position: "absolute", transformStyle: "preserve-3d", overflow: "hidden" });
      this.faces.set(face, el);
      this.cube.append(el);
    }
    this.spots = document.createElement("div");
    Object.assign(this.spots.style, { position: "absolute", left: "0", top: "0", transformStyle: "preserve-3d" });
    this.cube.append(this.spots);
    this.root.append(this.cube);
    host.append(this.root);
    this.root.addEventListener("pointerdown", this.onDown);
    this.root.addEventListener("pointermove", this.onMove);
    this.root.addEventListener("pointerup", this.onUp);
    this.root.addEventListener("pointercancel", this.onUp);
    this.root.addEventListener("wheel", this.onWheel, { passive: false });
    this.root.addEventListener("keydown", this.onKey);
    if (typeof ResizeObserver !== "undefined") {
      this.resize = new ResizeObserver(() => this.layout());
      this.resize.observe(this.root);
    }
    this.layout();
  }

  /** Show `view` (the first time) or swap the tiles that changed. */
  update(view: CubeView, tilesBase?: string): void {
    if (tilesBase) this.options.tilesBase = tilesBase;
    this.view = view;
    this.layout(true);
  }

  destroy(): void {
    this.resize?.disconnect();
    this.root.remove();
  }

  /** Where the view looks: compass bearing (0 = north) and pitch (up positive). */
  get yawDeg(): number {
    return this.yaw;
  }

  get pitchDeg(): number {
    return this.pitch;
  }

  /** Look at a bearing and pitch (device orientation, a saved view's start). */
  look(yawDeg: number, pitchDeg: number): void {
    this.yaw = ((yawDeg % 360) + 360) % 360;
    this.pitch = clamp(pitchDeg, -89, 89);
    this.orient();
  }

  /** Replace the hotspots; `onSelect` gets the id of the one tapped. */
  setHotspots(spots: CubeHotspot[], onSelect: (id: string) => void): void {
    this.spots.replaceChildren();
    this.hotspots = spots.map((spot) => {
      const el = document.createElement("button");
      el.type = "button";
      el.textContent = spot.label;
      el.dir = "auto"; // a room name reads in its own direction (PF5a)
      el.dataset.hotspot = spot.id;
      el.className = "tbx-hotspot";
      Object.assign(el.style, {
        position: "absolute",
        left: "0",
        top: "0",
        whiteSpace: "nowrap",
        padding: "8px 14px",
        borderRadius: "999px",
        border: "1px solid rgba(160, 206, 255, 0.6)",
        background: "rgba(22, 22, 22, 0.78)",
        color: "#ffffff",
        font: "600 14px/1.2 system-ui, sans-serif",
        cursor: "pointer",
        backfaceVisibility: "hidden",
      });
      // A tap on the hotspot is not the start of a drag.
      el.addEventListener("pointerdown", (e) => e.stopPropagation());
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        onSelect(spot.id);
      });
      this.spots.append(el);
      return { spot, el };
    });
    this.placeHotspots();
  }

  private placeHotspots(): void {
    const r = this.focal * 0.8;
    for (const { spot, el } of this.hotspots) {
      el.style.transform = `rotateY(${-spot.yawDeg}deg) rotateX(${-spot.pitchDeg}deg) translateZ(${-r}px) translate(-50%, -50%)`;
    }
    this.cullHotspots();
  }

  // Only those within 100° of where the view looks: one behind the viewer
  // would be drawn through the projection's back side.
  private cullHotspots(): void {
    for (const { spot, el } of this.hotspots) {
      const d = Math.abs(((spot.yawDeg - this.yaw + 540) % 360) - 180);
      el.style.visibility = d <= 100 ? "visible" : "hidden";
    }
  }

  private pickLevel(): number {
    const view = this.view;
    if (!view) return -1;
    const ratio = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
    const need = 2 * this.focal * ratio;
    const idx = view.levels.findIndex((px) => px >= need);
    return idx === -1 ? view.levels.length - 1 : idx;
  }

  private layout(force = false): void {
    const width = this.root.clientWidth || 640;
    this.focal = width / 2 / Math.tan((this.hfov * Math.PI) / 360);
    const half = this.focal;
    this.root.style.perspective = `${this.focal}px`;
    for (const [face, el] of this.faces) {
      Object.assign(el.style, {
        width: `${2 * half}px`,
        height: `${2 * half}px`,
        left: `${-half}px`,
        top: `${-half}px`,
        transform: faceTransform(face, half),
      });
    }
    this.orient();
    this.placeHotspots();
    const level = this.pickLevel();
    if (force || level !== this.level) this.paint(level, level !== this.level);
  }

  private orient(): void {
    this.cube.style.transform = `translateZ(${this.focal}px) rotateX(${this.pitch}deg) rotateY(${this.yaw}deg)`;
    this.cullHotspots();
  }

  private paint(level: number, rebuild: boolean): void {
    const view = this.view;
    if (!view || level < 0) return;
    this.level = level;
    const size = view.levels[level];
    const n = Math.max(1, Math.floor(size / view.tile_px));
    const cell = 100 / n;
    for (const face of ORDER) {
      const el = this.faces.get(face)!;
      const shas = view.faces[face]?.tiles?.[level] ?? [];
      if (rebuild || el.childElementCount !== shas.length) {
        el.replaceChildren();
        for (let i = 0; i < shas.length; i++) {
          const img = document.createElement("img");
          img.alt = "";
          img.draggable = false;
          img.decoding = "async";
          const row = Math.floor(i / n);
          const col = i % n;
          // A hair of overlap hides the seams between tiles.
          Object.assign(img.style, {
            position: "absolute",
            left: `${col * cell}%`,
            top: `${row * cell}%`,
            width: `calc(${cell}% + 1px)`,
            height: `calc(${cell}% + 1px)`,
            pointerEvents: "none",
          });
          el.append(img);
        }
        for (const key of [...this.shown.keys()]) if (key.startsWith(`${face}:`)) this.shown.delete(key);
      }
      shas.forEach((sha, i) => this.swap(face, i, sha, el.children[i] as HTMLImageElement));
    }
  }

  private swap(face: CubeFace, index: number, sha: string, img: HTMLImageElement): void {
    const key = `${face}:${index}`;
    if (this.shown.get(key) === sha) return;
    this.shown.set(key, sha);
    const url = `${this.options.tilesBase.replace(/\/$/, "")}/${sha}.jpg`;
    if (!img.getAttribute("src")) {
      img.src = url;
      return;
    }
    // Keep the old tile on screen until the new one has arrived.
    const next = new Image();
    next.decoding = "async";
    next.onload = () => {
      if (this.shown.get(key) === sha) img.src = url;
    };
    next.src = url;
  }

  private turn(dYaw: number, dPitch: number): void {
    this.yaw = (((this.yaw + dYaw) % 360) + 360) % 360;
    this.pitch = clamp(this.pitch + dPitch, -89, 89);
    this.orient();
    this.options.onTurn?.(this.yaw, this.pitch);
  }

  private readonly onDown = (e: PointerEvent) => {
    this.drag = { x: e.clientX, y: e.clientY, yaw: this.yaw, pitch: this.pitch };
    this.root.setPointerCapture?.(e.pointerId);
    this.root.style.cursor = "grabbing";
  };

  private readonly onMove = (e: PointerEvent) => {
    if (!this.drag) return;
    const perPx = this.hfov / (this.root.clientWidth || 640);
    this.yaw = this.drag.yaw;
    this.pitch = this.drag.pitch;
    this.turn(-(e.clientX - this.drag.x) * perPx, (e.clientY - this.drag.y) * perPx);
  };

  private readonly onUp = () => {
    this.drag = null;
    this.root.style.cursor = "grab";
  };

  private readonly onWheel = (e: WheelEvent) => {
    e.preventDefault();
    this.hfov = clamp(this.hfov + Math.sign(e.deltaY) * 5, 30, 110);
    this.layout();
  };

  private readonly onKey = (e: KeyboardEvent) => {
    const step = { ArrowLeft: [-5, 0], ArrowRight: [5, 0], ArrowUp: [0, 5], ArrowDown: [0, -5] }[e.key];
    if (step) {
      e.preventDefault();
      this.turn(step[0], step[1]);
    } else if (e.key === "+" || e.key === "-") {
      this.hfov = clamp(this.hfov + (e.key === "+" ? -5 : 5), 30, 110);
      this.layout();
    }
  };
}
