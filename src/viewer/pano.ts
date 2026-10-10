// The panorama view of the share page: an equirectangular image on the inside
// of a sphere, drawn with WebGL 1 (no library, nothing reported anywhere).
//
// Bearings are compass degrees (contract share-bundle §6.1): 0 = north,
// growing eastward; `center_bearing_deg` is the bearing of the image's middle
// column. The view keeps an absolute bearing, so walking through a hotspot
// keeps facing the same way. Drag, pinch or wheel to look and zoom; on a
// phone the gyroscope can steer (DeviceOrientation, asked for on iOS).

import { DEG, deviceLook, toCamera, wrap180, type PanoSources } from "./geometry";
import type { Hotspot, Panorama } from "./types";

const MIN_FOV = 30;
const MAX_FOV = 100;
const MAX_VFOV = 95;
const MAX_PITCH = 85;

export interface PanoLabels {
  goTo: string;
}

const VERTEX = `
attribute vec3 a_pos;
attribute vec2 a_uv;
uniform mat4 u_mvp;
varying vec2 v_uv;
void main() {
  v_uv = a_uv;
  gl_Position = u_mvp * vec4(a_pos, 1.0);
}`;

const FRAGMENT = `
precision mediump float;
uniform sampler2D u_tex;
varying vec2 v_uv;
void main() {
  gl_FragColor = texture2D(u_tex, v_uv);
}`;

function sphere(lonSeg = 72, latSeg = 36) {
  const pos: number[] = [];
  const uv: number[] = [];
  const idx: number[] = [];
  for (let i = 0; i <= latSeg; i++) {
    const v = i / latSeg;
    const lat = Math.PI / 2 - v * Math.PI;
    for (let j = 0; j <= lonSeg; j++) {
      const u = j / lonSeg;
      const lon = (u - 0.5) * 2 * Math.PI;
      pos.push(Math.sin(lon) * Math.cos(lat), Math.sin(lat), -Math.cos(lon) * Math.cos(lat));
      uv.push(u, v);
    }
  }
  for (let i = 0; i < latSeg; i++) {
    for (let j = 0; j < lonSeg; j++) {
      const a = i * (lonSeg + 1) + j;
      const b = a + lonSeg + 1;
      idx.push(a, b, a + 1, b, b + 1, a + 1);
    }
  }
  return { pos: new Float32Array(pos), uv: new Float32Array(uv), idx: new Uint16Array(idx) };
}

function compile(gl: WebGLRenderingContext, type: number, source: string): WebGLShader {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("shader");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader) ?? "shader");
  return shader;
}

export class PanoViewer {
  readonly element: HTMLElement;
  private readonly canvas: HTMLCanvasElement;
  private readonly layer: HTMLElement;
  private readonly gl: WebGLRenderingContext;
  private readonly program: WebGLProgram;
  private readonly count: number;
  private readonly uMvp: WebGLUniformLocation | null;
  private texture: WebGLTexture | null = null;
  private loadToken = 0;
  private pano: Panorama | null = null;
  private bearing = 0;
  private pitch = 0;
  private fov = 75;
  private frame = 0;
  private hotspots: { el: HTMLButtonElement; hs: Hotspot }[] = [];
  private pointers = new Map<number, { x: number; y: number }>();
  private pinch = 0;
  private motionOffset: number | null = null;
  private motionOn = false;
  private readonly resize: ResizeObserver;
  readonly maxTexture: number;

  static supported(): boolean {
    try {
      const c = document.createElement("canvas");
      return Boolean(c.getContext("webgl"));
    } catch {
      return false;
    }
  }

  private readonly onNavigate: (target: string) => void;
  private readonly labels: PanoLabels;

  constructor(host: HTMLElement, onNavigate: (target: string) => void, labels: PanoLabels) {
    this.onNavigate = onNavigate;
    this.labels = labels;
    this.element = document.createElement("div");
    this.element.className = "tbx-pano";
    this.canvas = document.createElement("canvas");
    this.canvas.className = "tbx-pano-canvas";
    this.canvas.tabIndex = 0;
    this.layer = document.createElement("div");
    this.layer.className = "tbx-hotspots";
    this.element.append(this.canvas, this.layer);
    host.append(this.element);

    const gl = this.canvas.getContext("webgl", { alpha: false, antialias: false });
    if (!gl) throw new Error("webgl");
    this.gl = gl;
    this.maxTexture = gl.getParameter(gl.MAX_TEXTURE_SIZE) as number;
    const program = gl.createProgram();
    if (!program) throw new Error("program");
    gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, VERTEX));
    gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, FRAGMENT));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error("link");
    this.program = program;
    gl.useProgram(program);

    const mesh = sphere();
    this.count = mesh.idx.length;
    const bind = (data: Float32Array, name: string, size: number) => {
      const buf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
      const loc = gl.getAttribLocation(program, name);
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 0, 0);
    };
    bind(mesh.pos, "a_pos", 3);
    bind(mesh.uv, "a_uv", 2);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, mesh.idx, gl.STATIC_DRAW);
    this.uMvp = gl.getUniformLocation(program, "u_mvp");
    gl.uniform1i(gl.getUniformLocation(program, "u_tex"), 0);
    gl.disable(gl.CULL_FACE);
    gl.clearColor(0.086, 0.086, 0.086, 1);

    this.resize = new ResizeObserver(() => this.fit());
    this.resize.observe(this.element);
    this.listen();
    this.fit();
  }

  /** Current view, compass degrees. */
  get view() {
    return { bearing: this.bearing, pitch: this.pitch, fov: this.fov };
  }

  show(pano: Panorama, sources: PanoSources, keepBearing: boolean): Promise<void> {
    const first = this.pano === null;
    this.pano = pano;
    if (first || !keepBearing) this.bearing = pano.start_bearing_deg ?? pano.center_bearing_deg;
    this.pitch = pano.start_pitch_deg ?? 0;
    if (first) this.fov = Math.min(MAX_FOV, Math.max(MIN_FOV, pano.start_hfov_deg ?? 75));
    this.motionOffset = null;
    this.makeHotspots(pano);
    const token = ++this.loadToken;
    const order = [sources.preview, sources.main].filter((u, i, all): u is string => Boolean(u) && all.indexOf(u) === i);
    let shown = false;
    const loads = order.map((url, rank) =>
      loadImage(url).then((img) => {
        if (token !== this.loadToken) return;
        // The sharper image wins; the preview only fills in until it arrives.
        if (rank === 0 && shown) return;
        this.upload(img);
        shown = true;
      }),
    );
    return Promise.any(loads).catch(() => {
      throw new Error("image");
    });
  }

  async setMotion(on: boolean): Promise<boolean> {
    if (!on) {
      window.removeEventListener("deviceorientation", this.onOrient);
      this.motionOn = false;
      return false;
    }
    const DOE = (window as Window & { DeviceOrientationEvent?: { requestPermission?: () => Promise<string> } })
      .DeviceOrientationEvent;
    if (!DOE) return false;
    if (typeof DOE.requestPermission === "function") {
      try {
        if ((await DOE.requestPermission()) !== "granted") return false;
      } catch {
        return false;
      }
    }
    this.motionOffset = null;
    this.motionOn = true;
    window.addEventListener("deviceorientation", this.onOrient);
    return true;
  }

  destroy(): void {
    this.setMotion(false);
    this.resize.disconnect();
    cancelAnimationFrame(this.frame);
    this.element.remove();
  }

  // --- drawing -----------------------------------------------------------------

  private fit(): void {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(1, Math.round(this.element.clientWidth * dpr));
    const h = Math.max(1, Math.round(this.element.clientHeight * dpr));
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
    }
    this.request();
  }

  private upload(img: HTMLImageElement): void {
    const gl = this.gl;
    if (this.texture) gl.deleteTexture(this.texture);
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, img);
    const pot = (n: number) => (n & (n - 1)) === 0;
    if (pot(img.naturalWidth) && pot(img.naturalHeight)) {
      gl.generateMipmap(gl.TEXTURE_2D);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
    } else {
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    }
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    const aniso = gl.getExtension("EXT_texture_filter_anisotropic");
    if (aniso) gl.texParameterf(gl.TEXTURE_2D, aniso.TEXTURE_MAX_ANISOTROPY_EXT, 4);
    this.texture = tex;
    this.element.dataset.ready = "true";
    this.request();
  }

  /** Horizontal and vertical field of view; a tall screen narrows the horizontal. */
  private fovs(): { h: number; v: number } {
    const aspect = this.canvas.width / this.canvas.height;
    let h = this.fov;
    let v = (2 * Math.atan(Math.tan((h * DEG) / 2) / aspect)) / DEG;
    if (v > MAX_VFOV) {
      v = MAX_VFOV;
      h = (2 * Math.atan(Math.tan((v * DEG) / 2) * aspect)) / DEG;
    }
    return { h, v };
  }

  private request(): void {
    if (!this.frame) this.frame = requestAnimationFrame(() => this.draw());
  }

  private draw(): void {
    this.frame = 0;
    const gl = this.gl;
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.clear(gl.COLOR_BUFFER_BIT);
    if (!this.pano || !this.texture) return;
    this.pitch = Math.max(-MAX_PITCH, Math.min(MAX_PITCH, this.pitch));
    const { h, v } = this.fovs();
    const psi = wrap180(this.bearing - this.pano.center_bearing_deg) * DEG;
    const t = this.pitch * DEG;
    const c = Math.cos(psi), s = Math.sin(psi), ct = Math.cos(t), st = Math.sin(t);
    // View = Rx(-pitch) * Ry(yaw), rows.
    const V = [
      [c, 0, s],
      [-st * s, ct, st * c],
      [-ct * s, -st, ct * c],
    ];
    const fy = 1 / Math.tan((v * DEG) / 2);
    const fx = 1 / Math.tan((h * DEG) / 2);
    const near = 0.1, far = 10;
    const A = (far + near) / (near - far), B = (2 * far * near) / (near - far);
    // MVP = P * V, column-major.
    const m = new Float32Array(16);
    for (let col = 0; col < 3; col++) {
      m[col * 4 + 0] = fx * V[0][col];
      m[col * 4 + 1] = fy * V[1][col];
      m[col * 4 + 2] = A * V[2][col];
      m[col * 4 + 3] = -V[2][col];
    }
    m[14] = B;
    gl.uniformMatrix4fv(this.uMvp, false, m);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.texture);
    gl.drawElements(gl.TRIANGLES, this.count, gl.UNSIGNED_SHORT, 0);
    this.placeHotspots(fx, fy);
  }

  // --- hotspots ------------------------------------------------------------------

  private makeHotspots(pano: Panorama): void {
    this.layer.replaceChildren();
    this.hotspots = (pano.hotspots ?? []).map((hs) => {
      const el = document.createElement("button");
      el.type = "button";
      el.className = "tbx-hotspot";
      const label = hs.label || hs.target;
      el.setAttribute("aria-label", `${this.labels.goTo} ${label}`);
      const dot = document.createElement("span");
      dot.className = "tbx-hotspot-dot";
      dot.setAttribute("aria-hidden", "true");
      const text = document.createElement("span");
      text.className = "tbx-hotspot-label";
      text.textContent = label;
      el.append(dot, text);
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        this.onNavigate(hs.target);
      });
      this.layer.append(el);
      return { el, hs };
    });
  }

  private placeHotspots(fx: number, fy: number): void {
    const w = this.element.clientWidth;
    const h = this.element.clientHeight;
    for (const { el, hs } of this.hotspots) {
      const [x, y, z] = toCamera(hs.bearing_deg, hs.pitch_deg, { bearing: this.bearing, pitch: this.pitch });
      const sx = (w / 2) * (1 + (x / -z) * fx);
      const sy = (h / 2) * (1 - (y / -z) * fy);
      const visible = z < -0.05 && sx > -40 && sx < w + 40 && sy > -40 && sy < h + 40;
      el.style.visibility = visible ? "visible" : "hidden";
      if (visible) el.style.transform = `translate(${sx.toFixed(1)}px, ${sy.toFixed(1)}px)`;
    }
  }

  // --- input ---------------------------------------------------------------------

  private listen(): void {
    const c = this.canvas;
    c.addEventListener("pointerdown", (e) => {
      c.setPointerCapture(e.pointerId);
      this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      this.pinch = this.spread();
      this.element.dataset.dragging = "true";
    });
    c.addEventListener("pointermove", (e) => {
      const prev = this.pointers.get(e.pointerId);
      if (!prev) return;
      const next = { x: e.clientX, y: e.clientY };
      this.pointers.set(e.pointerId, next);
      if (this.pointers.size >= 2) {
        const spread = this.spread();
        if (this.pinch > 0 && spread > 0) this.zoom(this.pinch / spread);
        this.pinch = spread;
        return;
      }
      const { h, v } = this.fovs();
      const dBearing = (-(next.x - prev.x) * h) / this.element.clientWidth;
      this.bearing += dBearing;
      if (this.motionOn && this.motionOffset !== null) this.motionOffset += dBearing;
      else this.pitch += ((next.y - prev.y) * v) / this.element.clientHeight;
      this.request();
    });
    const up = (e: PointerEvent) => {
      this.pointers.delete(e.pointerId);
      this.pinch = this.spread();
      if (this.pointers.size === 0) delete this.element.dataset.dragging;
    };
    c.addEventListener("pointerup", up);
    c.addEventListener("pointercancel", up);
    c.addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        this.zoom(1 + Math.max(-0.5, Math.min(0.5, e.deltaY * 0.0015)));
      },
      { passive: false },
    );
    c.addEventListener("keydown", (e) => {
      const step = e.shiftKey ? 15 : 5;
      const keys: Record<string, () => void> = {
        ArrowLeft: () => (this.bearing -= step),
        ArrowRight: () => (this.bearing += step),
        ArrowUp: () => (this.pitch += step),
        ArrowDown: () => (this.pitch -= step),
        "+": () => this.zoom(0.9),
        "=": () => this.zoom(0.9),
        "-": () => this.zoom(1.1),
      };
      const act = keys[e.key];
      if (act) {
        e.preventDefault();
        act();
        this.request();
      }
    });
  }

  private spread(): number {
    const pts = [...this.pointers.values()];
    if (pts.length < 2) return 0;
    return Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
  }

  private zoom(factor: number): void {
    this.fov = Math.min(MAX_FOV, Math.max(MIN_FOV, this.fov * factor));
    this.request();
  }

  private onOrient = (e: DeviceOrientationEvent): void => {
    if (e.alpha === null || e.beta === null || e.gamma === null) return;
    const angle = screen.orientation?.angle ?? 0;
    const look = deviceLook(e.alpha, e.beta, e.gamma, angle);
    if (this.motionOffset === null) this.motionOffset = this.bearing - look.yaw;
    this.bearing = look.yaw + this.motionOffset;
    this.pitch = look.pitch;
    this.request();
  };
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.decoding = "async";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`image ${url}`));
    img.src = url;
  });
}
