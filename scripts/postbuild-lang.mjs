#!/usr/bin/env node
// Post-build: give each non-English page its own <html lang dir>.
//
//   node scripts/postbuild-lang.mjs        (run by `npm run build`)
//
// The root layout renders one <html lang="en"> for every route of the static
// export. Crawlers and screen readers read the language and direction from
// the HTML as served, so the Arabic landing page's file is rewritten here
// (its wrapper also carries lang/dir for the client). Fails the build when a
// page or its <html> tag is missing, so the rewrite can never silently stop.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const out = path.join(root, "out");

const PAGES = [{ file: "ar/index.html", lang: "ar", dir: "rtl" }];

let failed = false;
for (const page of PAGES) {
  const file = path.join(out, page.file);
  if (!fs.existsSync(file)) {
    console.error(`postbuild-lang: ${page.file} is missing from out/`);
    failed = true;
    continue;
  }
  const html = fs.readFileSync(file, "utf8");
  const tag = /<html\b[^>]*>/i.exec(html);
  if (!tag) {
    console.error(`postbuild-lang: no <html> tag in ${page.file}`);
    failed = true;
    continue;
  }
  const attrs = tag[0]
    .replace(/^<html\b/i, "")
    .replace(/>$/, "")
    .replace(/\s+(lang|dir)="[^"]*"/gi, "");
  const next = `<html lang="${page.lang}" dir="${page.dir}"${attrs}>`;
  fs.writeFileSync(file, html.replace(tag[0], next));
  console.log(`postbuild-lang: ${page.file} -> ${next}`);
}
process.exit(failed ? 1 : 0);
