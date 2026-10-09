// The share page's viewer (PF5), loaded by the HTML the API writes at
// ${SHARE_BASE_URL}/view/{slug}: <main id="viewer" data-slug data-api data-site>.
// It fetches the page data (share-bundle 5.10), counts one visit (5.11) and
// shows the panoramas with hotspots, the renders and the drawings, with
// "Designed in Truebex" and a link to download Truebex.
//
// Built by scripts/build-viewer.mjs into out/viewer/viewer.js; framework-free
// so it loads fast on a phone from another origin. Copy: SHARE_PAGE.

import { SHARE_PAGE } from "../lib/constants";
import { buildGallery } from "./gallery";
import { meteredConnection, pickSources } from "./geometry";
import { PanoViewer } from "./pano";
import { buildDrawings } from "./pdf";
import { SCHEMA_MAJOR, schemaMajor, type Manifest, type PageData, type Panorama } from "./types";

const CONTRACT = { "X-Truebex-Contract": "share-bundle/1.0" };
const VISITOR_KEY = "truebex_share_visitor";
const VISITOR_LIFETIME_MS = 24 * 3600 * 1000;

type Tab = "panoramas" | "renders" | "drawings";

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/** A random id the page keeps for 24 h, so a visitor counts once a day. */
function visitorId(): string {
  const fresh = () => {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  };
  try {
    const saved = JSON.parse(localStorage.getItem(VISITOR_KEY) ?? "null") as { id?: string; at?: number } | null;
    if (saved?.id && /^[0-9a-f]{32}$/.test(saved.id) && Date.now() - (saved.at ?? 0) < VISITOR_LIFETIME_MS) return saved.id;
    const id = fresh();
    localStorage.setItem(VISITOR_KEY, JSON.stringify({ id, at: Date.now() }));
    return id;
  } catch {
    return fresh(); // storage blocked: count this page view on its own
  }
}

function message(root: HTMLElement, title: string, text: string, site: string, retry?: () => void): void {
  const box = el("section", "tbx-message");
  box.append(el("h1", undefined, title), el("p", undefined, text));
  if (retry) {
    const b = el("button", "tbx-button", SHARE_PAGE.retry);
    b.type = "button";
    b.addEventListener("click", retry);
    box.append(b);
  }
  root.replaceChildren(box, footer(site));
}

function footer(site: string, expires?: string | null): HTMLElement {
  const foot = el("footer", "tbx-foot");
  const brand = el("p", "tbx-brand");
  const mark = el("span", "tbx-mark");
  mark.setAttribute("aria-hidden", "true");
  const get = el("a", undefined, SHARE_PAGE.getTruebex);
  get.href = `${site}/download/?utm_source=share`;
  brand.append(mark, document.createTextNode(`${SHARE_PAGE.designedIn} · `), get);
  foot.append(brand);
  if (expires) foot.append(el("p", "tbx-until", `${SHARE_PAGE.openUntil} ${formatDate(expires)}`));
  return foot;
}

function fileUrls(m: Manifest): Map<string, string> {
  const out = new Map<string, string>();
  for (const f of m.files ?? []) if (f.url) out.set(f.sha256, f.url);
  return out;
}

async function start(root: HTMLElement): Promise<void> {
  const slug = root.dataset.slug ?? "";
  const api = (root.dataset.api || window.location.origin).replace(/\/$/, "");
  const site = (root.dataset.site || new URL("..", import.meta.url).origin).replace(/\/$/, "");
  const base = new URL(".", import.meta.url);
  root.replaceChildren(el("p", "tbx-status", SHARE_PAGE.loading));

  let res: Response;
  try {
    res = await fetch(`${api}/s/${encodeURIComponent(slug)}`, { headers: CONTRACT, cache: "no-store" });
  } catch {
    message(root, SHARE_PAGE.notFoundTitle, SHARE_PAGE.offline, site, () => void start(root));
    return;
  }
  if (res.status === 410) return message(root, SHARE_PAGE.endedTitle, SHARE_PAGE.endedText, site);
  if (res.status === 404) return message(root, SHARE_PAGE.notFoundTitle, SHARE_PAGE.notFoundText, site);
  if (!res.ok) return message(root, SHARE_PAGE.notFoundTitle, SHARE_PAGE.offline, site, () => void start(root));
  const data = (await res.json()) as PageData;
  const major = schemaMajor(data.manifest?.schema);
  if (major === null || major > SCHEMA_MAJOR) return message(root, SHARE_PAGE.updateTitle, SHARE_PAGE.updateText, site);

  void fetch(`${api}/s/${encodeURIComponent(slug)}/visits`, {
    method: "POST",
    headers: { ...CONTRACT, "Content-Type": "application/json" },
    body: JSON.stringify({ visitor: visitorId() }),
    keepalive: true,
  }).catch(() => undefined);

  render(root, data, site, base);
}

function render(root: HTMLElement, data: PageData, site: string, base: URL): void {
  const m = data.manifest;
  const urls = fileUrls(m);
  const panoramas = (m.panoramas ?? []).filter((p) => urls.has(p.file) || p.derivatives?.["pano-4096"]);
  const renders = (m.renders ?? []).filter((r) => urls.has(r.file)).map((render) => ({ render, url: urls.get(render.file)! }));
  const sheets = m.sheets && urls.has(m.sheets.file) ? m.sheets : null;
  const pdfFile = sheets ? m.files.find((f) => f.sha256 === sheets.file) : undefined;

  const header = el("header", "tbx-bar");
  header.append(el("h1", "tbx-title", data.title));
  const tabs = el("nav", "tbx-tabs");
  tabs.setAttribute("role", "tablist");
  header.append(tabs);
  const stage = el("div", "tbx-stage");
  root.replaceChildren(header, stage, footer(site, data.expires_at));
  document.title = `${data.title}${SHARE_PAGE.ogTitleSuffix}`;

  const panels = new Map<Tab, HTMLElement>();
  const openers = new Map<Tab, () => void>();
  const available: Tab[] = [];
  if (panoramas.length) available.push("panoramas");
  if (renders.length) available.push("renders");
  if (sheets && pdfFile?.url) available.push("drawings");

  const select = (tab: Tab) => {
    for (const [name, panel] of panels) panel.hidden = name !== tab;
    for (const b of tabs.querySelectorAll<HTMLButtonElement>("button")) {
      b.setAttribute("aria-selected", String(b.dataset.tab === tab));
      b.tabIndex = b.dataset.tab === tab ? 0 : -1;
    }
    openers.get(tab)?.();
    root.dataset.tab = tab;
  };
  for (const tab of available) {
    const b = el("button", "tbx-tab", SHARE_PAGE.tabs[tab]);
    b.type = "button";
    b.dataset.tab = tab;
    b.setAttribute("role", "tab");
    b.addEventListener("click", () => select(tab));
    tabs.append(b);
    const panel = el("section", `tbx-panel tbx-panel-${tab}`);
    panel.setAttribute("role", "tabpanel");
    panel.hidden = true;
    stage.append(panel);
    panels.set(tab, panel);
  }
  if (available.length < 2) tabs.hidden = true;

  if (panoramas.length) setupPanoramas(panels.get("panoramas")!, panoramas, m, urls, openers);
  if (renders.length) panels.get("renders")!.append(buildGallery(renders, SHARE_PAGE));
  if (sheets && pdfFile?.url) {
    const drawings = buildDrawings({
      url: pdfFile.url,
      name: pdfFile.name,
      titles: sheets.titles ?? [],
      base,
      labels: SHARE_PAGE,
    });
    panels.get("drawings")!.append(drawings.element);
    openers.set("drawings", drawings.open);
  }
  // #renders and #drawings open that tab first (a link can point at the drawings).
  const asked = window.location.hash.slice(1) as Tab;
  if (available.length) select(available.includes(asked) ? asked : available[0]);
}

function setupPanoramas(
  panel: HTMLElement,
  panoramas: Panorama[],
  m: Manifest,
  urls: Map<string, string>,
  openers: Map<Tab, () => void>,
): void {
  const byId = new Map(panoramas.map((p) => [p.id, p]));
  const first = byId.get(m.start ?? "") ?? panoramas[0];

  if (!PanoViewer.supported()) {
    const flat = el("div", "tbx-flat");
    flat.append(el("p", "tbx-status", SHARE_PAGE.noWebgl));
    for (const p of panoramas) {
      const img = el("img");
      img.src = p.derivatives?.["pano-4096"]?.url ?? urls.get(p.file) ?? "";
      img.alt = p.title;
      flat.append(img);
    }
    panel.append(flat);
    return;
  }

  const coarse = window.matchMedia("(pointer: coarse)").matches;
  const chips = el("div", "tbx-rooms");
  chips.setAttribute("aria-label", SHARE_PAGE.rooms);
  const tools = el("div", "tbx-tools");
  const hint = el("p", "tbx-hint", SHARE_PAGE.dragHint);
  let viewer: PanoViewer | null = null;
  let currentId = "";

  const go = (id: string, keepBearing: boolean) => {
    const pano = byId.get(id);
    if (!pano || !viewer) return;
    currentId = id;
    for (const c of chips.querySelectorAll<HTMLButtonElement>("button")) {
      c.setAttribute("aria-pressed", String(c.dataset.id === id));
    }
    const sources = pickSources(pano, viewer.maxTexture, urls.get(pano.file) ?? null, {
      coarse,
      metered: meteredConnection(),
    });
    panel.dataset.loading = "true";
    viewer
      .show(pano, sources, keepBearing)
      .catch(() => undefined)
      .finally(() => {
        if (currentId === id) delete panel.dataset.loading;
      });
  };

  for (const p of panoramas) {
    const chip = el("button", "tbx-chip", p.title);
    chip.type = "button";
    chip.dataset.id = p.id;
    chip.addEventListener("click", () => go(p.id, false));
    chips.append(chip);
  }
  if (panoramas.length < 2) chips.hidden = true;

  const full = el("button", "tbx-icon tbx-full");
  full.type = "button";
  full.setAttribute("aria-label", SHARE_PAGE.fullscreen);
  full.title = SHARE_PAGE.fullscreen;
  full.addEventListener("click", () => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void panel.requestFullscreen?.().catch(() => undefined);
  });
  document.addEventListener("fullscreenchange", () => {
    const on = Boolean(document.fullscreenElement);
    full.setAttribute("aria-label", on ? SHARE_PAGE.exitFullscreen : SHARE_PAGE.fullscreen);
    full.title = on ? SHARE_PAGE.exitFullscreen : SHARE_PAGE.fullscreen;
  });
  if (document.fullscreenEnabled) tools.append(full);

  if (coarse && "DeviceOrientationEvent" in window) {
    const motion = el("button", "tbx-icon tbx-motion");
    motion.type = "button";
    motion.setAttribute("aria-pressed", "false");
    motion.setAttribute("aria-label", SHARE_PAGE.motionOn);
    motion.title = SHARE_PAGE.motionOn;
    motion.addEventListener("click", async () => {
      if (!viewer) return;
      const want = motion.getAttribute("aria-pressed") !== "true";
      const on = await viewer.setMotion(want);
      motion.setAttribute("aria-pressed", String(on));
      const label = on ? SHARE_PAGE.motionOff : SHARE_PAGE.motionOn;
      motion.setAttribute("aria-label", label);
      motion.title = label;
      if (want && !on) hint.textContent = SHARE_PAGE.motionDenied;
    });
    tools.append(motion);
  }

  panel.append(chips, tools, hint);
  openers.set("panoramas", () => {
    if (viewer) return;
    viewer = new PanoViewer(panel, (target) => go(target, true), SHARE_PAGE);
    panel.prepend(viewer.element);
    viewer.element.addEventListener("pointerdown", () => hint.classList.add("tbx-hint-gone"), { once: true });
    go(first.id, false);
  });
}

const root = document.getElementById("viewer");
if (root) void start(root);
