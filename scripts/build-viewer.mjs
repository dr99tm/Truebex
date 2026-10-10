// Build the share page's viewer (PF5) after `next build`:
//   out/viewer/viewer.js    src/viewer/main.ts bundled by esbuild (ES module)
//   out/viewer/viewer.css   src/viewer/viewer.css with the brand tokens of
//                           src/app/globals.css (@theme) prepended as :root
//   out/viewer/pdfjs/       PDF.js (Apache-2.0), loaded when Drawings opens
// The API's /view/{slug} page loads these from SITE_URL. Fails when
// viewer.js grows past 250 KB (before gzip).
//
//   node scripts/build-viewer.mjs [--out <dir>]

import { build, transform } from "esbuild";
import { copyFileSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const outIndex = args.indexOf("--out");
const OUT = resolve(outIndex >= 0 ? args[outIndex + 1] : join(ROOT, "out", "viewer"));
const MAX_JS_BYTES = 250 * 1024;

/** The --color-*, --radius-* and --shadow-* tokens of globals.css's @theme block. */
export function brandTokens(css) {
  const theme = /@theme\s*\{([\s\S]*?)\n\}/.exec(css);
  if (!theme) throw new Error("globals.css has no @theme block");
  const tokens = [...theme[1].matchAll(/^\s*(--(?:color|radius|shadow)-[\w-]+)\s*:\s*([^;]+);/gm)];
  if (!tokens.some(([, name]) => name === "--color-accent")) throw new Error("no --color-accent in @theme");
  return `:root{${tokens.map(([, name, value]) => `${name}:${value.trim()}`).join(";")}}`;
}

mkdirSync(join(OUT, "pdfjs"), { recursive: true });

await build({
  entryPoints: [join(ROOT, "src", "viewer", "main.ts")],
  outfile: join(OUT, "viewer.js"),
  bundle: true,
  format: "esm",
  platform: "browser",
  target: ["es2020", "safari15", "chrome96", "firefox95"],
  minify: true,
  legalComments: "none",
  logLevel: "warning",
});

const tokens = brandTokens(readFileSync(join(ROOT, "src", "app", "globals.css"), "utf8"));
const css = await transform(`${tokens}\n${readFileSync(join(ROOT, "src", "viewer", "viewer.css"), "utf8")}`, {
  loader: "css",
  minify: true,
  target: ["safari15", "chrome96", "firefox95"],
});
writeFileSync(join(OUT, "viewer.css"), css.code);

const pdfjs = join(ROOT, "node_modules", "pdfjs-dist");
for (const name of ["pdf.min.mjs", "pdf.worker.min.mjs"]) {
  copyFileSync(join(pdfjs, "legacy", "build", name), join(OUT, "pdfjs", name));
}
copyFileSync(join(pdfjs, "LICENSE"), join(OUT, "pdfjs", "LICENSE"));

const size = statSync(join(OUT, "viewer.js")).size;
console.log(`viewer: viewer.js ${(size / 1024).toFixed(1)} KB, viewer.css ${(css.code.length / 1024).toFixed(1)} KB -> ${OUT}`);
if (size > MAX_JS_BYTES) {
  console.error(`viewer.js is ${size} bytes; the budget is ${MAX_JS_BYTES}.`);
  process.exit(1);
}
