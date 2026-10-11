// Build the Android app's panorama viewer (PF10) from PF9's shared viewer code:
//   mobile/android/assets/viewer/viewer.js   src/viewer/native.ts (cube.ts,
//                                             orientation.ts) bundled by esbuild
// The app's loopback server serves it with assets/viewer/index.html (committed);
// the bundle itself is built here, at build time, and git-ignored. Run by
// scripts/verify-mobile.ps1 before `flutter test` and `flutter build apk`.
// Fails past 60 KB (before gzip).
//
//   node scripts/build-mobile-viewer.mjs [--out <dir>]

import { build } from "esbuild";
import { mkdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const outIndex = args.indexOf("--out");
const OUT = resolve(outIndex >= 0 ? args[outIndex + 1] : join(ROOT, "mobile", "android", "assets", "viewer"));
const MAX_JS_BYTES = 60 * 1024;

mkdirSync(OUT, { recursive: true });
await build({
  entryPoints: [join(ROOT, "src", "viewer", "native.ts")],
  outfile: join(OUT, "viewer.js"),
  bundle: true,
  format: "iife",
  platform: "browser",
  // Android System WebView follows Chrome; 96 is the oldest the app's minimum Android ships with updates.
  target: ["es2020", "chrome96"],
  minify: true,
  legalComments: "none",
  logLevel: "warning",
  define: { "process.env": "{}" },
});

const size = statSync(join(OUT, "viewer.js")).size;
console.log(`mobile viewer: viewer.js ${(size / 1024).toFixed(1)} KB -> ${OUT}`);
if (size > MAX_JS_BYTES) {
  console.error(`viewer.js is ${size} bytes; the budget is ${MAX_JS_BYTES}.`);
  process.exit(1);
}
