import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  // GitHub Pages serves directories, not bare .html files. Without this,
  // /payments/callback resolves to the callback/ dir (which has no
  // index.html) and falls through to 404 — showing only the background.
  // trailingSlash makes the export emit payments/callback/index.html.
  trailingSlash: true,
  basePath: "",
  assetPrefix: "./",
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
