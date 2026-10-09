#!/usr/bin/env node
// Saves the API's release feeds (contract licence-api 5.13) as
// src/content/releases.json (stable) and src/content/releases-beta.json
// (beta), exactly as served, so the Download, Changelog and dashboard pages
// are built from them. Run by the owner before a deploy; the build itself
// never touches the network (a prebuild fetch would make builds depend on the
// live API).
//
//   npm run sync:releases                      # API from RELEASES_API, NEXT_PUBLIC_AUTH_URL or .env.local
//   npm run sync:releases -- --api http://127.0.0.1:8000
//   node scripts/sync-releases.mjs --from <dir with releases-stable.json and releases-beta.json> --out-dir <dir>
//
// Signatures are not checked here: the site only shows versions, sizes, dates
// and notes; the app verifies every manifest against its pinned keys.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const CONTRACT = "licence-api/1.0";
const PLATFORM = "win64";
const FILES = { stable: "releases.json", beta: "releases-beta.json" };

function arg(name) {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : undefined;
}

function apiFromEnvFile() {
  const file = join(ROOT, ".env.local");
  if (!existsSync(file)) return undefined;
  const line = readFileSync(file, "utf8")
    .split(/\r?\n/)
    .find((l) => l.startsWith("NEXT_PUBLIC_AUTH_URL="));
  return line?.slice("NEXT_PUBLIC_AUTH_URL=".length).trim() || undefined;
}

/** A feed document, unwrapping the contract fixtures' {http_status, body}. */
function unwrap(data) {
  return data && typeof data === "object" && "body" in data && "http_status" in data ? data.body : data;
}

async function readFeed(channel, { from, api }) {
  if (from) {
    return unwrap(JSON.parse(readFileSync(join(from, `releases-${channel}.json`), "utf8")));
  }
  const url = `${api.replace(/\/$/, "")}/releases/feed?channel=${channel}&platform=${PLATFORM}`;
  const res = await fetch(url, { headers: { "X-Truebex-Contract": CONTRACT, Accept: "application/json" } });
  if (!res.ok) throw new Error(`${url} answered ${res.status}`);
  return res.json();
}

function check(feed, channel) {
  if (feed?.schema !== "truebex-releases/1" || feed.channel !== channel || !Array.isArray(feed.releases)) {
    throw new Error(`the ${channel} feed is not a truebex-releases/1 document`);
  }
  for (const { manifest: m } of feed.releases) {
    if (!m?.version || !m.published_at || !m.installer?.sha256) {
      throw new Error(`the ${channel} feed has an incomplete manifest`);
    }
  }
  return feed;
}

async function main() {
  const from = arg("from") ? resolve(arg("from")) : undefined;
  const api = arg("api") ?? process.env.RELEASES_API ?? process.env.NEXT_PUBLIC_AUTH_URL ?? apiFromEnvFile();
  if (!from && !api) throw new Error("no API: pass --api <url> or set NEXT_PUBLIC_AUTH_URL in .env.local");
  const outDir = resolve(arg("out-dir") ?? join(ROOT, "src", "content"));

  // Read both before writing either, so a failure leaves the files as they were.
  const feeds = {};
  for (const channel of ["stable", "beta"]) feeds[channel] = check(await readFeed(channel, { from, api }), channel);
  for (const [channel, feed] of Object.entries(feeds)) {
    writeFileSync(join(outDir, FILES[channel]), JSON.stringify(feed, null, 2) + "\n", "utf8");
  }
  console.log(
    `wrote ${outDir}: stable ${feeds.stable.latest ?? "none"} (${feeds.stable.releases.length}), ` +
      `beta ${feeds.beta.latest ?? "none"} (${feeds.beta.releases.length}) from ${from ?? api}`
  );
}

main().catch((err) => {
  console.error(`sync:releases failed: ${err.message}. The release files were not changed.`);
  process.exit(1);
});
