// The Renders tab: a swipe gallery (CSS scroll snap), with previous / next
// buttons and a counter for a mouse.

import type { Render } from "./types";

export interface GalleryLabels {
  previous: string;
  next: string;
}

export function buildGallery(renders: { render: Render; url: string }[], labels: GalleryLabels): HTMLElement {
  const root = document.createElement("div");
  root.className = "tbx-gallery";
  const track = document.createElement("div");
  track.className = "tbx-gallery-track";
  track.tabIndex = 0;
  for (const { render, url } of renders) {
    const figure = document.createElement("figure");
    figure.className = "tbx-slide";
    const img = document.createElement("img");
    img.src = url;
    img.alt = render.title;
    img.width = render.width;
    img.height = render.height;
    img.loading = "lazy";
    img.decoding = "async";
    const caption = document.createElement("figcaption");
    caption.textContent = render.title;
    figure.append(img, caption);
    track.append(figure);
  }

  const counter = document.createElement("p");
  counter.className = "tbx-gallery-count";
  counter.setAttribute("aria-live", "polite");
  const current = () => Math.round(track.scrollLeft / Math.max(1, track.clientWidth));
  const update = () => {
    counter.textContent = `${Math.min(renders.length, current() + 1)} / ${renders.length}`;
  };
  const go = (step: number) => {
    const index = Math.max(0, Math.min(renders.length - 1, current() + step));
    track.scrollTo({ left: index * track.clientWidth, behavior: "smooth" });
  };
  const button = (label: string, cls: string, step: number) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = `tbx-gallery-nav ${cls}`;
    b.setAttribute("aria-label", label);
    b.textContent = step < 0 ? "‹" : "›";
    b.addEventListener("click", () => go(step));
    return b;
  };
  track.addEventListener("scroll", update, { passive: true });
  track.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      go(e.key === "ArrowLeft" ? -1 : 1);
    }
  });
  root.append(track);
  if (renders.length > 1) root.append(button(labels.previous, "tbx-prev", -1), button(labels.next, "tbx-next", 1), counter);
  update();
  return root;
}
