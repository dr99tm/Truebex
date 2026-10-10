import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  // GitHub Pages serves directories, not bare .html files. Without this,
  // /login resolves to the login/ dir (which has no index.html) and falls
  // through to 404 — showing only the background.
  // trailingSlash makes the export emit login/index.html.
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
  // PF2b: always defined (default "false") so the build inlines it and the
  // minifier drops the GD5 7.4 draft wording (BILLING.rules) unless the owner
  // builds with NEXT_PUBLIC_LEGAL_WORDING_APPROVED=true after sign-off.
  env: {
    NEXT_PUBLIC_LEGAL_WORDING_APPROVED:
      process.env.NEXT_PUBLIC_LEGAL_WORDING_APPROVED === "true" ? "true" : "false",
  },
};

export default nextConfig;
