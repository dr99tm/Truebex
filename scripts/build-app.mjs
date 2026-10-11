// Build the mobile web client's extras (PF9) after `next build`, beside PF5's
// viewer step (scripts/build-viewer.mjs):
//   out/sw.js                 src/sw/sw.ts bundled by esbuild, with this build's
//                             precache list (the /app/ pages and the hashed files
//                             they reference); fails past 30 KB
//   out/viewer/selftest.mjs   src/viewer/selftest.ts for Node: the verify gate
//                             runs it (server/tests/test_site_pf9.py)
//
//   node scripts/build-app.mjs [--out <dir>]

import { build } from "esbuild";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const outIndex = args.indexOf("--out");
const OUT = resolve(outIndex >= 0 ? args[outIndex + 1] : join(ROOT, "out"));
const MAX_SW_BYTES = 30 * 1024;
const PAGES = ["app/index.html", "app/project/index.html"];
const ICONS = ["/manifest.webmanifest", "/icon-192.png", "/icon-512.png", "/icon-maskable-512.png", "/apple-icon.png"];

/** The /_next/static/ files an exported page references (scripts, styles, fonts). */
export function staticRefs(html) {
  const refs = new Set();
  for (const m of html.matchAll(/["'(](\/_next\/static\/[^"'()\s\\]+)/g)) refs.add(m[1]);
  return [...refs].sort();
}

const precache = new Set(["/app/", "/app/project/"]);
for (const page of PAGES) {
  const file = join(OUT, page);
  if (!existsSync(file)) {
    console.error(`build-app: ${page} is missing; run next build first.`);
    process.exit(1);
  }
  for (const ref of staticRefs(readFileSync(file, "utf8"))) precache.add(ref);
}
for (const icon of ICONS) if (existsSync(join(OUT, icon.slice(1)))) precache.add(icon);
const list = [...precache];
const buildId = createHash("sha256").update(list.join("\n")).digest("hex").slice(0, 12);

await build({
  entryPoints: [join(ROOT, "src", "sw", "sw.ts")],
  outfile: join(OUT, "sw.js"),
  bundle: true,
  format: "iife",
  platform: "browser",
  target: ["es2020", "safari15", "chrome96", "firefox95"],
  minify: true,
  legalComments: "none",
  logLevel: "warning",
  define: { PRECACHE: JSON.stringify(list), BUILD_ID: JSON.stringify(buildId) },
});

await build({
  entryPoints: [join(ROOT, "src", "viewer", "selftest.ts")],
  outfile: join(OUT, "viewer", "selftest.mjs"),
  bundle: true,
  format: "esm",
  platform: "node",
  target: ["node20"],
  legalComments: "none",
  logLevel: "warning",
});

const size = statSync(join(OUT, "sw.js")).size;
console.log(`app: sw.js ${(size / 1024).toFixed(1)} KB (${list.length} files precached, build ${buildId}), viewer/selftest.mjs -> ${OUT}`);
if (size > MAX_SW_BYTES) {
  console.error(`sw.js is ${size} bytes; the budget is ${MAX_SW_BYTES}.`);
  process.exit(1);
}
