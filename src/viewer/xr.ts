// The headset view (PF9): an immersive-vr session of the WebXR Device API
// that puts the current view's cube tiles around the person, with controller
// rays for hotspots and a floating menu for theme and finish changes. The 3D
// library (three, MIT) is loaded only here, when the person starts it; the
// page offers it only when `isSessionSupported("immersive-vr")` says so.
//
// Orientation: world north is -Z, east +X, up +Y. Each face of render-jobs
// §6.2 becomes a plane R metres out, its image as the camera saw it from the
// eye (u and d with the image's top edge toward north); the whole sky turns
// so the bearing the person looked at on the phone is straight ahead.
// Tiles load with CORS (WebGL refuses others); a face is composed once per
// manifest and re-composed only when its tiles changed (tilediff.ts).

import type * as Three from "three";
import type { CubeView } from "./cube";
import { diffTiles, FACE_ORDER, levelAtMost, type FaceName, type TileViewLike } from "./tilediff";

export interface XrHotspot {
  id: string;
  label: string;
  yawDeg: number;
  pitchDeg: number;
}

export interface XrMenuItem {
  id: string;
  label: string;
  selected?: boolean;
}

export interface XrMenuGroup {
  title: string;
  items: XrMenuItem[];
}

export interface XrScene {
  view: CubeView;
  tilesBase: string;
  /** The bearing to face at the start (where the person looked on the phone). */
  yawDeg: number;
  hotspots: XrHotspot[];
  menu: { title: string; groups: XrMenuGroup[] };
  labels: { menu: string; close: string; status?: string };
}

export interface XrHandlers {
  onHotspot(id: string): void;
  onMenu(id: string): void;
  onEnd(): void;
}

type XrNavigator = Navigator & {
  xr?: { isSessionSupported(mode: string): Promise<boolean>; requestSession(mode: string, init?: object): Promise<XRSession> };
};

const SKY_R = 20; // metres: far enough that head movement does not shift the room
const SPOT_R = 3;
const MAX_FACE_PX = 2048;
const ACCENT = "#a0ceff";
const GROUND = "#232323";

/** Feature detection only: true where the browser offers an immersive-vr session. */
export async function immersiveSupported(): Promise<boolean> {
  const xr = (navigator as XrNavigator).xr;
  if (!xr?.isSessionSupported) return false;
  try {
    return await xr.isSessionSupported("immersive-vr");
  } catch {
    return false;
  }
}

/** Where each compass face sits around the viewer (position, Euler XYZ). */
export const FACE_POSES: Record<FaceName, { pos: [number, number, number]; rot: [number, number, number] }> = {
  n: { pos: [0, 0, -SKY_R], rot: [0, 0, 0] },
  e: { pos: [SKY_R, 0, 0], rot: [0, -Math.PI / 2, 0] },
  s: { pos: [0, 0, SKY_R], rot: [0, Math.PI, 0] },
  w: { pos: [-SKY_R, 0, 0], rot: [0, Math.PI / 2, 0] },
  u: { pos: [0, SKY_R, 0], rot: [Math.PI / 2, 0, Math.PI] },
  d: { pos: [0, -SKY_R, 0], rot: [-Math.PI / 2, 0, 0] },
};

/** The unit direction of a compass bearing and pitch in the world above. */
export function directionOf(yawDeg: number, pitchDeg: number): [number, number, number] {
  const h = (yawDeg * Math.PI) / 180;
  const p = (pitchDeg * Math.PI) / 180;
  return [Math.sin(h) * Math.cos(p), Math.sin(p), -Math.cos(h) * Math.cos(p)];
}

function loadImage(url: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.decoding = "async";
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = url;
  });
}

interface MenuRect {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

export class HeadsetView {
  private readonly three: typeof Three;
  private readonly renderer: Three.WebGLRenderer;
  private readonly scene: Three.Scene;
  private readonly camera: Three.PerspectiveCamera;
  private readonly sky: Three.Group;
  private readonly spots: Three.Group;
  private readonly faces = new Map<FaceName, { mesh: Three.Mesh; canvas: HTMLCanvasElement; texture: Three.CanvasTexture }>();
  private readonly controllers: Three.Group[] = [];
  private readonly raycaster: Three.Raycaster;
  private menuPanel: Three.Mesh | null = null;
  private menuCanvas: HTMLCanvasElement | null = null;
  private menuTexture: Three.CanvasTexture | null = null;
  private menuRects: MenuRect[] = [];
  private menuButton: Three.Mesh | null = null;
  private menuOpen = false;
  private hovered: string | null = null;
  private current: XrScene;
  private shown: TileViewLike | null = null;
  private ended = false;

  private constructor(three: typeof Three, private readonly session: XRSession, scene: XrScene, private readonly handlers: XrHandlers) {
    this.three = three;
    this.current = scene;
    const T = three;
    this.renderer = new T.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(1);
    this.renderer.xr.enabled = true;
    this.renderer.xr.setReferenceSpaceType("local");
    Object.assign(this.renderer.domElement.style, { position: "fixed", width: "1px", height: "1px", opacity: "0", pointerEvents: "none" });
    document.body.append(this.renderer.domElement);
    this.scene = new T.Scene();
    this.scene.background = new T.Color(GROUND);
    this.camera = new T.PerspectiveCamera(70, 1, 0.05, 100);
    this.sky = new T.Group();
    this.spots = new T.Group();
    this.sky.add(this.spots);
    this.scene.add(this.sky);
    this.raycaster = new T.Raycaster();
    for (const face of FACE_ORDER) {
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 16;
      const texture = new T.CanvasTexture(canvas);
      texture.colorSpace = T.SRGBColorSpace;
      const mesh = new T.Mesh(
        new T.PlaneGeometry(2 * SKY_R, 2 * SKY_R),
        new T.MeshBasicMaterial({ map: texture, depthWrite: false })
      );
      const pose = FACE_POSES[face];
      mesh.position.set(...pose.pos);
      mesh.rotation.set(...pose.rot);
      mesh.renderOrder = -1;
      this.sky.add(mesh);
      this.faces.set(face, { mesh, canvas, texture });
    }
    for (let i = 0; i < 2; i++) {
      const c = this.renderer.xr.getController(i);
      const ray = new T.Line(
        new T.BufferGeometry().setFromPoints([new T.Vector3(0, 0, 0), new T.Vector3(0, 0, -1)]),
        new T.LineBasicMaterial({ color: ACCENT })
      );
      ray.scale.z = 5;
      c.add(ray);
      c.addEventListener("select", () => this.select(c));
      c.addEventListener("squeeze", () => this.toggleMenu());
      this.scene.add(c);
      this.controllers.push(c);
    }
    session.addEventListener("end", () => this.cleanup());
  }

  /** Ask for the session inside the tap, then load the 3D library and show `scene`. */
  static async start(scene: XrScene, handlers: XrHandlers): Promise<HeadsetView> {
    const xr = (navigator as XrNavigator).xr;
    if (!xr) throw new Error("WebXR is not available");
    const session = await xr.requestSession("immersive-vr", { optionalFeatures: ["local-floor", "hand-tracking"] });
    try {
      const three = await import("three");
      const view = new HeadsetView(three, session, scene, handlers);
      await view.renderer.xr.setSession(session as unknown as Parameters<Three.WebXRManager["setSession"]>[0]);
      view.update(scene);
      view.renderer.setAnimationLoop(() => view.frame());
      return view;
    } catch (err) {
      await session.end().catch(() => undefined);
      throw err;
    }
  }

  /** A newer manifest, another view, other hotspots or menu: swap what changed. */
  update(scene: XrScene): void {
    const viewChanged = this.current.view !== scene.view || !this.shown;
    this.current = scene;
    this.sky.rotation.y = (scene.yawDeg * Math.PI) / 180;
    if (viewChanged) void this.paintFaces(scene.view, scene.tilesBase);
    this.buildHotspots(scene.hotspots);
    this.drawMenu();
  }

  end(): void {
    void this.session.end().catch(() => undefined);
  }

  private async paintFaces(view: CubeView, tilesBase: string): Promise<void> {
    const level = levelAtMost(view, MAX_FACE_PX);
    const prev = this.shown;
    const diff = diffTiles(prev && prev.levels[level] === view.levels[level] ? prev : null, view);
    this.shown = view;
    const size = view.levels[level];
    const n = Math.max(1, Math.floor(size / view.tile_px));
    const cell = size / n;
    const base = tilesBase.replace(/\/$/, "");
    await Promise.all(
      diff.faces.map(async (face) => {
        const slot = this.faces.get(face);
        const shas = view.faces[face]?.tiles?.[level] ?? [];
        if (!slot || !shas.length) return;
        const canvas = document.createElement("canvas");
        canvas.width = canvas.height = size;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        ctx.fillStyle = GROUND;
        ctx.fillRect(0, 0, size, size);
        const images = await Promise.all(shas.map((sha) => loadImage(`${base}/${sha}.jpg`)));
        images.forEach((img, i) => {
          if (img) ctx.drawImage(img, (i % n) * cell, Math.floor(i / n) * cell, cell, cell);
        });
        if (this.ended || this.shown !== view) return;
        const texture = new this.three.CanvasTexture(canvas);
        texture.colorSpace = this.three.SRGBColorSpace;
        const material = slot.mesh.material as Three.MeshBasicMaterial;
        slot.texture.dispose();
        material.map = texture;
        material.needsUpdate = true;
        this.faces.set(face, { ...slot, canvas, texture });
      })
    );
  }

  private label(text: string, width: number, height: number, fill: string, ink: string): Three.CanvasTexture {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = fill;
    ctx.beginPath();
    ctx.roundRect(4, 4, width - 8, height - 8, height / 2 - 4);
    ctx.fill();
    ctx.strokeStyle = ACCENT;
    ctx.lineWidth = 4;
    ctx.stroke();
    ctx.fillStyle = ink;
    ctx.font = `600 ${Math.round(height * 0.42)}px system-ui, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, width / 2, height / 2, width - 40);
    const texture = new this.three.CanvasTexture(canvas);
    texture.colorSpace = this.three.SRGBColorSpace;
    return texture;
  }

  private buildHotspots(spots: XrHotspot[]): void {
    const T = this.three;
    for (const child of [...this.spots.children]) {
      const mesh = child as Three.Mesh;
      ((mesh.material as Three.MeshBasicMaterial).map as Three.Texture | null)?.dispose();
      mesh.geometry.dispose();
      this.spots.remove(mesh);
    }
    for (const spot of spots) {
      const mesh = new T.Mesh(
        new T.PlaneGeometry(0.8, 0.2),
        new T.MeshBasicMaterial({ map: this.label(spot.label, 512, 128, "rgba(22,22,22,0.85)", "#ffffff"), transparent: true })
      );
      const [x, y, z] = directionOf(spot.yawDeg, spot.pitchDeg);
      mesh.position.set(x * SPOT_R, y * SPOT_R, z * SPOT_R);
      mesh.rotation.set((spot.pitchDeg * Math.PI) / 180, (-spot.yawDeg * Math.PI) / 180, 0, "YXZ");
      mesh.userData = { hotspot: spot.id };
      this.spots.add(mesh);
    }
    if (!this.menuButton) {
      this.menuButton = new T.Mesh(
        new T.PlaneGeometry(0.36, 0.1),
        new T.MeshBasicMaterial({ map: this.label(this.current.labels.menu, 512, 140, GROUND, "#ffffff"), transparent: true })
      );
      // Ahead of where the session started, below eye level.
      const [x, y, z] = directionOf(0, -32);
      this.menuButton.position.set(x * 1.4, y * 1.4, z * 1.4);
      this.menuButton.rotation.set((-32 * Math.PI) / 180, 0, 0, "YXZ");
      this.menuButton.userData = { button: "menu" };
      this.scene.add(this.menuButton);
    }
  }

  private drawMenu(): void {
    const T = this.three;
    const menu = this.current.menu;
    const W = 1024;
    const pad = 32;
    const itemH = 76;
    const cols = 2;
    const colW = (W - pad * 2 - 16) / cols;
    let h = pad + 64;
    for (const g of menu.groups) h += 56 + Math.ceil(g.items.length / cols) * (itemH + 12);
    h += itemH + pad;
    const canvas = this.menuCanvas ?? document.createElement("canvas");
    canvas.width = W;
    canvas.height = h;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = "rgba(22,22,22,0.94)";
    ctx.fillRect(0, 0, W, h);
    ctx.strokeStyle = ACCENT;
    ctx.lineWidth = 3;
    ctx.strokeRect(1.5, 1.5, W - 3, h - 3);
    ctx.fillStyle = "#ffffff";
    ctx.textBaseline = "middle";
    ctx.font = "700 40px system-ui, sans-serif";
    ctx.fillText(menu.title, pad, pad + 24, W - pad * 2);
    const rects: MenuRect[] = [];
    let y = pad + 64;
    for (const g of menu.groups) {
      ctx.fillStyle = "#cbcbcb";
      ctx.font = "600 30px system-ui, sans-serif";
      ctx.fillText(g.title, pad, y + 26, W - pad * 2);
      y += 56;
      g.items.forEach((item, i) => {
        const x = pad + (i % cols) * (colW + 16);
        const iy = y + Math.floor(i / cols) * (itemH + 12);
        rects.push({ id: item.id, x, y: iy, w: colW, h: itemH });
        const hot = this.hovered === item.id;
        ctx.fillStyle = item.selected ? "#1762c9" : hot ? "#3a3a3a" : "#2b2b2b";
        ctx.beginPath();
        ctx.roundRect(x, iy, colW, itemH, 14);
        ctx.fill();
        if (hot) {
          ctx.strokeStyle = ACCENT;
          ctx.stroke();
        }
        ctx.fillStyle = "#ffffff";
        ctx.font = "500 30px system-ui, sans-serif";
        ctx.fillText(item.label, x + 20, iy + itemH / 2, colW - 40);
      });
      y += Math.ceil(g.items.length / cols) * (itemH + 12);
    }
    const close = { id: "__close", x: pad, y, w: W - pad * 2, h: itemH };
    rects.push(close);
    ctx.fillStyle = this.hovered === close.id ? "#3a3a3a" : "#2b2b2b";
    ctx.beginPath();
    ctx.roundRect(close.x, close.y, close.w, close.h, 14);
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "center";
    ctx.fillText(this.current.labels.close, W / 2, y + itemH / 2);
    ctx.textAlign = "start";
    this.menuRects = rects;
    if (!this.menuPanel) {
      this.menuCanvas = canvas;
      this.menuTexture = new T.CanvasTexture(canvas);
      this.menuTexture.colorSpace = T.SRGBColorSpace;
      this.menuPanel = new T.Mesh(
        new T.PlaneGeometry(1.2, (1.2 * h) / W),
        new T.MeshBasicMaterial({ map: this.menuTexture, transparent: true })
      );
      this.menuPanel.visible = false;
      this.menuPanel.userData = { panel: true };
      this.scene.add(this.menuPanel);
    } else {
      const aspect = h / W;
      const geo = this.menuPanel.geometry as Three.PlaneGeometry;
      if (Math.abs(geo.parameters.height - 1.2 * aspect) > 1e-6) {
        geo.dispose();
        this.menuPanel.geometry = new T.PlaneGeometry(1.2, 1.2 * aspect);
      }
      this.menuTexture!.needsUpdate = true;
    }
  }

  private toggleMenu(open = !this.menuOpen): void {
    if (!this.menuPanel) return;
    this.menuOpen = open;
    this.menuPanel.visible = open;
    if (open) {
      // In front of where the person looks now, a little below the eyes.
      const T = this.three;
      const cam = this.renderer.xr.getCamera();
      const pos = new T.Vector3().setFromMatrixPosition(cam.matrixWorld);
      const dir = new T.Vector3(0, 0, -1).applyQuaternion(new T.Quaternion().setFromRotationMatrix(cam.matrixWorld));
      dir.y = 0;
      if (dir.lengthSq() < 1e-6) dir.set(0, 0, -1);
      dir.normalize();
      this.menuPanel.position.copy(pos).addScaledVector(dir, 1.5);
      this.menuPanel.position.y -= 0.15;
      this.menuPanel.lookAt(pos.x, this.menuPanel.position.y, pos.z);
    }
  }

  private hit(c: Three.Group): { kind: "spot" | "menu" | "button"; id: string } | null {
    const T = this.three;
    const rot = new T.Matrix4().extractRotation(c.matrixWorld);
    this.raycaster.ray.origin.setFromMatrixPosition(c.matrixWorld);
    this.raycaster.ray.direction.set(0, 0, -1).applyMatrix4(rot);
    const targets: Three.Object3D[] = [...this.spots.children];
    if (this.menuButton) targets.push(this.menuButton);
    if (this.menuOpen && this.menuPanel) targets.push(this.menuPanel);
    const found = this.raycaster.intersectObjects(targets, false)[0];
    if (!found) return null;
    const data = found.object.userData as { hotspot?: string; panel?: boolean; button?: string };
    if (data.hotspot) return { kind: "spot", id: data.hotspot };
    if (data.button) return { kind: "button", id: data.button };
    if (data.panel && found.uv && this.menuCanvas) {
      const x = found.uv.x * this.menuCanvas.width;
      const y = (1 - found.uv.y) * this.menuCanvas.height;
      const rect = this.menuRects.find((r) => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h);
      return rect ? { kind: "menu", id: rect.id } : null;
    }
    return null;
  }

  private select(c: Three.Group): void {
    const target = this.hit(c);
    if (!target) return;
    if (target.kind === "button") this.toggleMenu();
    else if (target.kind === "spot") this.handlers.onHotspot(target.id);
    else if (target.id === "__close") this.toggleMenu(false);
    else this.handlers.onMenu(target.id);
  }

  private frame(): void {
    let hovered: string | null = null;
    for (const c of this.controllers) {
      const target = this.hit(c);
      if (target?.kind === "menu") hovered = target.id;
    }
    if (hovered !== this.hovered) {
      this.hovered = hovered;
      if (this.menuOpen) this.drawMenu();
    }
    this.renderer.render(this.scene, this.camera);
  }

  private cleanup(): void {
    if (this.ended) return;
    this.ended = true;
    this.renderer.setAnimationLoop(null);
    this.scene.traverse((obj) => {
      const mesh = obj as Three.Mesh;
      if (!mesh.isMesh) return;
      mesh.geometry.dispose();
      const material = mesh.material as Three.MeshBasicMaterial;
      material.map?.dispose();
      material.dispose();
    });
    this.renderer.dispose();
    this.renderer.domElement.remove();
    this.handlers.onEnd();
  }
}
