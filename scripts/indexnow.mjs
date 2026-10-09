#!/usr/bin/env node
// Tell search engines (Bing, and every engine that shares IndexNow) which
// truebex.com pages changed. Run by the owner after a deploy.
//
//   node scripts/indexnow.mjs /pricing/ /features/daylight/      (paths or full URLs)
//   node scripts/indexnow.mjs --sitemap                          (every URL in out/sitemap.xml)
//   node scripts/indexnow.mjs --dry-run /pricing/                (print the request, send nothing)
//
// The key is the file public/<32 hex>.txt, served from the site root as the
// protocol requires (https://www.indexnow.org/documentation). Keys are public.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SITE = "https://truebex.com";
const HOST = new URL(SITE).host;
const ENDPOINT = "https://api.indexnow.org/indexnow";

function fail(msg) {
  console.error(`indexnow: ${msg}`);
  process.exit(1);
}

const keys = fs
  .readdirSync(path.join(root, "public"))
  .filter((f) => /^[0-9a-f]{32}\.txt$/.test(f))
  .map((f) => f.slice(0, -4));
if (keys.length !== 1) fail(`expected one key file public/<32 hex>.txt, found ${keys.length}`);
const key = keys[0];
const onDisk = fs.readFileSync(path.join(root, "public", `${key}.txt`), "utf8").trim();
if (onDisk !== key) fail(`public/${key}.txt must contain exactly its own name`);

const args = process.argv.slice(2);
const dryRun = args.includes("--dry-run");
let targets = args.filter((a) => !a.startsWith("--"));
if (args.includes("--sitemap")) {
  const sitemap = path.join(root, "out", "sitemap.xml");
  if (!fs.existsSync(sitemap)) fail("out/sitemap.xml not found: run npm run build first");
  targets = [...targets, ...[...fs.readFileSync(sitemap, "utf8").matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1])];
}
if (targets.length === 0) fail("give the changed paths or URLs, or --sitemap");

// Git Bash turns a "/pricing/" argument into "C:/Program Files/Git/pricing/";
// take such a path back to the site path it was.
const unmangle = (t) => t.replace(/^[A-Za-z]:[\\/](?:.*[\\/])?Git[\\/]/, "/").replace(/\\/g, "/");

const urlList = [...new Set(targets.map(unmangle))].map((t) => {
  const url = new URL(t, SITE);
  if (url.host !== HOST) fail(`${t} is not on ${HOST}`);
  return url.href;
});
if (urlList.length > 10000) fail("at most 10,000 URLs per request");

const body = { host: HOST, key, keyLocation: `${SITE}/${key}.txt`, urlList };
if (dryRun) {
  console.log(JSON.stringify(body, null, 2));
  process.exit(0);
}

const res = await fetch(ENDPOINT, {
  method: "POST",
  headers: { "Content-Type": "application/json; charset=utf-8" },
  body: JSON.stringify(body),
});
// 200 = received, 202 = received and the key is still being checked.
console.log(`indexnow: ${res.status} ${res.statusText} for ${urlList.length} URL(s)`);
if (res.status !== 200 && res.status !== 202) {
  console.error(await res.text());
  process.exit(1);
}
