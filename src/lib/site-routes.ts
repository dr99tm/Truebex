// Server-only, build time: which optional pages and captures exist, so links
// never point at a page that is not in this build.
import fs from "node:fs";
import path from "node:path";
import { FEATURE_PAGE_UI, PRODUCT_SHOT } from "@/lib/constants";

const root = process.cwd();

/** The download page arrives with the release feed (PF1). Until it is in
 *  the build, the download button asks for a demo instead. */
export const hasDownloadPage = fs.existsSync(path.join(root, "src", "app", "download", "page.tsx"));

export const downloadCta = hasDownloadPage
  ? { href: "/download/", label: FEATURE_PAGE_UI.download }
  : { href: "/#contact", label: FEATURE_PAGE_UI.downloadFallback };

// Size scripts/make_web_assets.py writes feature captures at.
export const FEATURE_CAPTURE = { width: 1600, height: 1000 } as const;

export interface Capture {
  src: string;
  width: number;
  height: number;
  alt: string;
  caption: string;
}

/**
 * A feature page's own clean capture (public/images/features/<slug>.jpg,
 * cropped by scripts/make_web_assets.py from a clean frame) or, until that
 * exists, the shared capture with its own words, never a HUD frame.
 */
export function featureCapture(slug: string, words?: { alt: string; caption: string }): Capture | null {
  if (!words) return null;
  const own = `/images/features/${slug}.jpg`;
  if (fs.existsSync(path.join(root, "public", own))) {
    return { src: own, ...FEATURE_CAPTURE, ...words };
  }
  return {
    src: PRODUCT_SHOT.src,
    width: PRODUCT_SHOT.width,
    height: PRODUCT_SHOT.height,
    alt: words.alt,
    caption: words.caption,
  };
}
