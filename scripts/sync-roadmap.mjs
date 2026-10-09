#!/usr/bin/env node
// Write the public roadmap's statuses from the two roadmap trackers.
//
//   node scripts/sync-roadmap.mjs <app tracker README.md> <platform tracker README.md> [--roadmap <file>] [--check]
//
//   e.g. node scripts/sync-roadmap.mjs T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\README.md docs\roadmap\40\README.md
//
// Reads each tracker's table (columns found by header: "Done", "Feature",
// "Code today"), gives every feature id a state, then sets each item of
// src/content/roadmap.json from its `plan_ids`:
//   a row ticked [x]                       -> shipped
//   unticked, a branch in "Code today"     -> in progress   ("—" = not started)
//   item: every plan shipped -> shipped; any started or shipped -> in_progress;
//   else planned.
// Only `status` is written; the public words stay as written by hand, and
// nothing moves into FEATURES (src/lib/constants.ts) automatically.
// Runs on the owner's machine before a deploy, never inside the build.
// --check exits 1 when a status would change (and writes nothing).

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function usage(msg) {
  if (msg) console.error(`sync-roadmap: ${msg}`);
  console.error("usage: node scripts/sync-roadmap.mjs <app README.md> <platform README.md> [--roadmap <file>] [--check]");
  process.exit(2);
}

const args = process.argv.slice(2);
let roadmapFile = path.join(root, "src", "content", "roadmap.json");
let check = false;
const trackers = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--roadmap") roadmapFile = path.resolve(args[++i] ?? usage("--roadmap needs a file"));
  else if (args[i] === "--check") check = true;
  else if (args[i] === "-h" || args[i] === "--help") usage();
  else trackers.push(path.resolve(args[i]));
}
if (trackers.length !== 2) usage("give the app tracker and the platform tracker");

const cells = (line) =>
  line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((c) => c.trim());

/** Feature id -> "shipped" | "in_progress" | "planned" from one tracker. */
function readTracker(file) {
  if (!fs.existsSync(file)) usage(`tracker not found: ${file}`);
  const lines = fs.readFileSync(file, "utf8").split(/\r?\n/);
  const states = new Map();
  let cols = null;
  for (const line of lines) {
    if (!line.trim().startsWith("|")) {
      cols = null;
      continue;
    }
    const row = cells(line);
    if (!cols) {
      const done = row.findIndex((c) => /^done$/i.test(c));
      const feature = row.findIndex((c) => /^feature$/i.test(c));
      const code = row.findIndex((c) => /^code today$/i.test(c));
      if (done >= 0 && feature >= 0 && code >= 0) cols = { done, feature, code };
      continue;
    }
    if (row.every((c) => /^:?-+:?$/.test(c))) continue; // the |---| rule
    const id = /\[([A-Z]{2}\d{1,2})\]/.exec(row[cols.feature] ?? "")?.[1];
    if (!id) continue;
    const ticked = /\[x\]/i.test(row[cols.done] ?? "");
    const code = (row[cols.code] ?? "").replace(/`/g, "").trim();
    const started = code !== "" && code !== "—" && code !== "-";
    states.set(id, ticked ? "shipped" : started ? "in_progress" : "planned");
  }
  if (states.size === 0) usage(`no tracker table found in ${file}`);
  return states;
}

const states = new Map([...readTracker(trackers[0]), ...readTracker(trackers[1])]);

const doc = JSON.parse(fs.readFileSync(roadmapFile, "utf8"));
const unknown = [];
const changes = [];
for (const item of doc.items) {
  const plan = item.plan_ids.map((id) => {
    if (!states.has(id)) unknown.push(`${item.id}: ${id}`);
    return states.get(id) ?? "planned";
  });
  const status = plan.every((s) => s === "shipped")
    ? "shipped"
    : plan.some((s) => s !== "planned")
      ? "in_progress"
      : "planned";
  if (status !== item.status) changes.push(`${item.id}: ${item.status} -> ${status}`);
  item.status = status;
}
if (unknown.length) {
  console.error(`sync-roadmap: plan ids not in either tracker:\n  ${unknown.join("\n  ")}`);
  process.exit(1);
}

console.log(changes.length ? changes.join("\n") : "sync-roadmap: no status changed");
if (check) process.exit(changes.length ? 1 : 0);
fs.writeFileSync(roadmapFile, `${JSON.stringify(doc, null, 2)}\n`);
