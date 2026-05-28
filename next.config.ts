import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  // GitHub Pages serves directories, not bare .html files. Without this,
  // /payments/callback resolves to the callback/ dir (which has no
  // index.html) and falls through to 404 — showing only the background.
  // trailingSlash makes the export emit payments/callback/index.html.
  trailingSlash: true,
  basePath: "",
  // Must be root-absolute, NOT "./". With trailingSlash, nested routes like
  // /login/ resolve "./_next/..." to /login/_next/... (404) — the JS never
  // loads and the page shows only the background. The site is served from the
  // domain root (CNAME truebex.com), so "/" is correct for every route depth.
  assetPrefix: "/",
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
