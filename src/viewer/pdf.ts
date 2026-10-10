// The Drawings tab: the sheet PDF drawn page by page with PDF.js (Apache-2.0,
// copied to /viewer/pdfjs/ by scripts/build-viewer.mjs). The library is loaded
// only when the tab first opens; pages render as they scroll into view.

export interface PdfLabels {
  downloadPdf: string;
  pdfLoading: string;
  pdfFailed: string;
  pages: string;
}

interface PdfPage {
  getViewport(o: { scale: number }): { width: number; height: number };
  render(o: { canvas: HTMLCanvasElement; viewport: { width: number; height: number } }): { promise: Promise<void> };
}

interface PdfDocument {
  numPages: number;
  getPage(n: number): Promise<PdfPage>;
}

interface PdfJs {
  GlobalWorkerOptions: { workerSrc: string };
  getDocument(o: { url: string; isEvalSupported: boolean; enableXfa: boolean }): { promise: Promise<PdfDocument> };
}

let library: Promise<PdfJs> | null = null;

function loadLibrary(base: URL): Promise<PdfJs> {
  if (!library) {
    const src = new URL("pdfjs/pdf.min.mjs", base).href;
    library = (import(/* webpackIgnore: true */ src) as Promise<PdfJs>).then((lib) => {
      lib.GlobalWorkerOptions.workerSrc = new URL("pdfjs/pdf.worker.min.mjs", base).href;
      return lib;
    });
    library.catch(() => {
      library = null;
    });
  }
  return library;
}

export function buildDrawings(opts: {
  url: string;
  name: string;
  titles: string[];
  base: URL;
  labels: PdfLabels;
}): { element: HTMLElement; open: () => void } {
  const root = document.createElement("div");
  root.className = "tbx-drawings";
  const bar = document.createElement("div");
  bar.className = "tbx-drawings-bar";
  const info = document.createElement("p");
  info.className = "tbx-drawings-info";
  info.textContent = opts.titles.join(" · ");
  const download = document.createElement("a");
  download.className = "tbx-button";
  download.href = opts.url;
  download.download = opts.name;
  download.textContent = opts.labels.downloadPdf;
  bar.append(info, download);
  const pages = document.createElement("div");
  pages.className = "tbx-pages";
  const status = document.createElement("p");
  status.className = "tbx-status";
  status.textContent = opts.labels.pdfLoading;
  pages.append(status);
  root.append(bar, pages);

  let started = false;
  const open = () => {
    if (started) return;
    started = true;
    void render().catch(() => {
      status.textContent = opts.labels.pdfFailed;
      started = false;
    });
  };

  async function render(): Promise<void> {
    const lib = await loadLibrary(opts.base);
    const doc = await lib.getDocument({ url: opts.url, isEvalSupported: false, enableXfa: false }).promise;
    status.remove();
    if (!opts.titles.length) info.textContent = `${doc.numPages} ${opts.labels.pages}`;
    const width = () => Math.max(280, pages.clientWidth - 2);
    const draw = async (n: number, canvas: HTMLCanvasElement) => {
      const page = await doc.getPage(n);
      const unit = page.getViewport({ scale: 1 });
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const viewport = page.getViewport({ scale: (width() / unit.width) * dpr });
      canvas.width = Math.floor(viewport.width);
      canvas.height = Math.floor(viewport.height);
      await page.render({ canvas, viewport }).promise;
      canvas.style.aspectRatio = "";
      canvas.dataset.rendered = "true";
    };
    const seen = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const canvas = entry.target as HTMLCanvasElement;
          seen.unobserve(canvas);
          void draw(Number(canvas.dataset.page), canvas);
        }
      },
      { rootMargin: "400px" },
    );
    for (let n = 1; n <= doc.numPages; n++) {
      const canvas = document.createElement("canvas");
      canvas.className = "tbx-page";
      canvas.dataset.page = String(n);
      canvas.setAttribute("role", "img");
      canvas.setAttribute("aria-label", opts.titles[n - 1] ?? `${n}`);
      // Placeholder size until the page draws (A-series landscape).
      canvas.style.aspectRatio = "1.414";
      pages.append(canvas);
      seen.observe(canvas);
    }
  }

  return { element: root, open };
}
