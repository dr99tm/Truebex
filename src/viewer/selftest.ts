// The mobile web client's JavaScript self-tests (PF9), bundled by
// scripts/build-app.mjs into out/viewer/selftest.mjs and run by the verify
// gate (`node out/viewer/selftest.mjs`, test_site_pf9_js_selftests): the
// action builder against the app's contract fixture (project-log 1.1.0 §9
// action-move.json, refs `<kind>#<id>`), the tile diff against the render-jobs fixtures, the
// cache policy, the outbox's §6.3 handling, who a rejection names (PF9a) and
// the orientation maths. Exits non-zero on the first failed check.

import fixture from "../../server/tests/contracts/project-log/action-move.json";
import panorama from "../../server/tests/contracts/render-jobs/manifest-panorama.json";
import partial from "../../server/tests/contracts/render-jobs/manifest-tiles.json";
import { applyTheme, buildActionOp, DIGEST_KINDS, fillFace, moveBy, nudgeVector, ref, refId, slideAlong, swapProduct, touchedOf } from "./actions";
import { isTileUrl, pageKey, planEviction, requestRule, TILE_BUDGET_BYTES } from "./cachepolicy";
import { conflictLine, flush, MemoryOutbox, PushError, type ConflictText, type OutboxEntry, type PushAnswer, type Winner } from "./outbox";
import { angleDelta, bearingTo, lookFromOrientation } from "./orientation";
import { diffTiles, levelAtMost, levelFor, tileUrls, type TileViewLike } from "./tilediff";

let checks = 0;
const failures: string[] = [];

function check(name: string, ok: boolean, detail = ""): void {
  checks++;
  if (!ok) failures.push(`${name}${detail ? `: ${detail}` : ""}`);
}

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
const near = (a: number, b: number, eps = 1e-6) => Math.abs(a - b) <= eps;
const throws = (fn: () => unknown) => {
  try {
    fn();
    return false;
  } catch {
    return true;
  }
};

// --- the action builder against action-move.json ----------------------------------------------

function builder(): void {
  // The app's own action-move.json (CL1, project-log 1.1.0): a bare §6.2 operation whose
  // refs are `<kind>#<id>` and whose touched is the bare id. A move of the picked wall
  // writes its tool, args, permission and touched exactly; author, op_id, replica_id and
  // at are per client (the fixture's are passed in), session and request_id our own.
  const op = fixture;
  const wall = op.touched[0];
  const session = "5e55000000000000000000000000000a";
  const built = buildActionOp({
    author: op.author,
    replicaId: op.replica_id,
    baseSeq: op.base_seq,
    session,
    opId: op.op_id,
    at: op.at,
    name: op.name,
    call: moveBy([ref(DIGEST_KINDS.wall, wall)], [0, 600, 0]),
  });
  check("builder.refs", same(built.action.args, { refs: [`wall#${wall}`], by_mm: [0, 600, 0] }), JSON.stringify(built.action.args));
  check("builder.touched", same(built.touched, [wall]) && same(built.touched, op.touched), JSON.stringify(built.touched));
  check("builder.tool", built.action.tool === op.action.tool);
  check("builder.args bytes", JSON.stringify(built.action.args) === JSON.stringify(op.action.args), JSON.stringify(op.action.args));
  check("builder.permission", built.action.permission === op.action.permission);
  const wire = built as unknown as Record<string, unknown>;
  const want = op as unknown as Record<string, unknown>;
  for (const key of Object.keys(wire).filter((k) => k !== "action")) {
    check(`builder.${key}`, same(wire[key], want[key]), `${JSON.stringify(wire[key])} != ${JSON.stringify(want[key])}`);
  }
  for (const key of Object.keys(want).filter((k) => !(k in wire))) {
    check(`builder omits ${key}`, key === "server_seq" && want[key] === 0, `the fixture has ${JSON.stringify(want[key])}`);
  }
  // agent-interface §6.4 adds session and request_id to a live call; the app's log action carries neither.
  const { session: s1, request_id: r1, ...core } = built.action;
  check("builder.action core", same(core, op.action), JSON.stringify(core));
  check("builder session", s1 === session && /^[0-9a-f]{32}$/.test(r1) && !("session" in op.action));

  // A pick with no kind is refused, never sent as a bare id; an unknown kind too.
  const base = { author: op.author, replicaId: op.replica_id, baseSeq: 3, session, name: "Edit" };
  check("bare id refused", throws(() => buildActionOp({ ...base, call: moveBy([wall], [0, 600, 0]) })));
  check("unknown kind refused", throws(() => buildActionOp({ ...base, call: moveBy([`sofa#${wall}`], [0, 600, 0]) })));
  check("bare target refused", throws(() => buildActionOp({ ...base, call: fillFace(wall, "left", { kind: "paint", colour: "#C8B79E" }) })));
  check("ref parse", refId(`WALL#${wall.toUpperCase()}`) === wall && refId(wall) === null && refId("wall#nope") === null);
  check("digest kinds", ref(DIGEST_KINDS.product, wall) === `object#${wall}` && ref(DIGEST_KINDS.opening, wall) === `opening#${wall}`);

  // touched: the ids of every ref in the arguments, sorted and unique, lowercase.
  const [a, b] = ["0199c6a2e00070028000000000000001", "0199c6a2e00070068000000000000002"];
  const [room, sofa] = [ref(DIGEST_KINDS.room, a), ref(DIGEST_KINDS.product, b)];
  const product = { supplier_id: "f8afe1ba2b0bf97f23ef888f040cf46a", sku: "TABLE-FJORD-CT", variant_id: "default" };
  check("touched swap", same(touchedOf(swapProduct(sofa, product, room).args), [a, b]));
  check("touched dedupe", same(touchedOf({ refs: [sofa, room.toUpperCase(), sofa] }), [a, b]));
  check("touched ignores names and bare ids", same(touchedOf({ theme: "nordic-calm", target: room, refs: [b] }), [a]));
  const swap = buildActionOp({ ...base, name: "Swap coffee table", call: swapProduct(sofa, product, room) });
  check("swap tool", swap.action.tool === "place" && same(swap.action.args, { kind: "product", product, replace: sofa, room }));
  check("swap touched", same(swap.touched, [a, b]) && swap.base_seq === 3 && swap.kind === "action");
  const fill = buildActionOp({ ...base, call: fillFace(room, "floor", { kind: "paint", colour: "#C8B79E" }) });
  check("fill args", same(fill.action.args, { target: room, face: "floor", finish: { kind: "paint", colour: "#C8B79E" } }));
  check("theme args", same(applyTheme(room, "nordic-calm").args, { theme: "nordic-calm", target: room, keep_products: true }));
  check("ids minted", /^[0-9a-f]{32}$/.test(fill.op_id) && fill.op_id !== swap.op_id && /^[0-9a-f]{32}$/.test(fill.action.request_id));
  check("at is RFC 3339 ms", /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(fill.at));
  check("name capped at 80", buildActionOp({ ...base, name: "x".repeat(200), call: slideAlong(ref(DIGEST_KINDS.opening, a), 50) }).name.length === 80);
  check("move needs exactly one", throws(() => buildActionOp({ ...base, call: { tool: "move", args: { refs: [room], by_mm: [1, 0, 0], along_mm: 5 } } })));
  check("bad colour refused", throws(() => buildActionOp({ ...base, call: fillFace(room, "floor", { kind: "paint", colour: "beige" }) })));
  check("bad author refused", throws(() => buildActionOp({ ...base, author: "me", call: moveBy([room], [0, 0, 0]) })));
  check("negative base refused", throws(() => buildActionOp({ ...base, baseSeq: -1, call: moveBy([room], [0, 0, 0]) })));
  check("place object refused", throws(() => buildActionOp({ ...base, call: { tool: "place", args: { kind: "object" } } as never })));

  // Nudges relative to where the person looks (0 = north, 90 = east).
  check("nudge north-left", same(nudgeVector(0, "left", 250), [-250, 0, 0]));
  check("nudge east-left", same(nudgeVector(90, "left", 250), [0, 250, 0]));
  check("nudge south-forward", same(nudgeVector(180, "forward", 50), [0, -50, 0]));
  check("nudge west-back", same(nudgeVector(270, "back", 50), [50, 0, 0]));
  check("nudge no -0", !Object.is(nudgeVector(0, "forward", 50)[0], -0));
}

// --- the tile diff against the render-jobs fixtures ---------------------------------------------

function tileDiff(): void {
  const full = panorama.views[0] as unknown as TileViewLike;
  const update = partial.views[0] as unknown as TileViewLike;
  const d = diffTiles(full, update);
  check("diff faces", same(d.faces, ["n", "e"]), JSON.stringify(d.faces));
  const changedFaces = partial.views[0].faces;
  const want = (["n", "e"] as const).reduce((n, f) => n + changedFaces[f].tiles.flat().length, 0);
  check("diff tiles", d.changed.length === want && d.fetch.length <= want, `${d.changed.length} of ${want}`);
  check("diff same", diffTiles(update, update).changed.length === 0);
  check("diff first", same(diffTiles(null, full).faces, ["n", "e", "s", "w", "u", "d"]));
  check("level for 600 px", levelFor(full, 600) === 1 && levelFor(full, 300) === 0 && levelFor(full, 5000) === 1);
  check("level at most 2048", levelAtMost(full, 2048) === 1 && levelAtMost(full, 600) === 0);
  const urls = tileUrls(full, "https://tiles.example.com/tiles/", 0);
  check("tile urls", urls.length === 6 && urls.every((u) => isTileUrl(u) && u.startsWith("https://tiles.example.com/tiles/")));
}

// --- the cache policy ------------------------------------------------------------------------------

function cachePolicy(): void {
  const origin = "https://truebex.com";
  const sha = "28746b924afdd6a1eb06011a2811b57ac05f67e96c27779cd9d6ed348f462846";
  const rule = (url: string, extra: Partial<{ method: string; mode: string; authorized: boolean }> = {}) =>
    requestRule({ url, method: "GET", mode: "no-cors", origin, ...extra });
  check("budget 150 MB", TILE_BUDGET_BYTES === 150 * 1024 * 1024);
  check("tile on the CDN", rule(`https://tiles.truebex.com/tiles/${sha}.jpg`) === "tile");
  check("tile on the API", rule(`https://api.truebex.com/tiles/${sha}.jpg`) === "tile");
  check("tile with a query is not one", rule(`https://api.truebex.com/tiles/${sha}.jpg?x=1`) === null);
  check("build files", rule(`${origin}/_next/static/chunks/app.js`) === "static");
  check("app page", rule(`${origin}/app/project/?id=abc`, { mode: "navigate" }) === "page");
  check("page key drops the query", pageKey(`${origin}/app/project/?id=abc`) === `${origin}/app/project/`);
  check("other pages untouched", rule(`${origin}/dashboard/`, { mode: "navigate" }) === null && rule(`${origin}/`, { mode: "navigate" }) === null);
  for (const path of ["/projects", "/projects/abc/ops?after=1", "/auth/me", "/jobs/abc", "/market/prices", "/uploads", "/licence/account"]) {
    check(`API ${path} never cached`, rule(`https://api.truebex.com${path}`) === null && rule(`${origin}${path}`) === null);
  }
  check("POST never cached", rule(`https://api.truebex.com/tiles/${sha}.jpg`, { method: "POST" }) === null);
  check("credentials never cached", rule(`${origin}/_next/static/a.js`, { authorized: true }) === null);
  const entries = [
    { url: "a", bytes: 60, used: 3 },
    { url: "b", bytes: 60, used: 1 },
    { url: "c", bytes: 60, used: 2 },
  ];
  check("fits", planEviction(entries, 180).length === 0);
  check("LRU out", same(planEviction(entries, 150), ["b"]));
  check("LRU with incoming", same(planEviction(entries, 150, 60), ["b", "c"]));
  check("ties by url", same(planEviction([{ url: "y", bytes: 10, used: 1 }, { url: "x", bytes: 10, used: 1 }], 10), ["x"]));
}

// --- the outbox (§6.3 for a light client) ---------------------------------------------------------

async function outbox(): Promise<void> {
  const op = fixture;
  const store = new MemoryOutbox();
  const pid = "0199c6a2f1007a3c8b5e2d4f6a7b8c9d";
  const make = (n: number, id: string): OutboxEntry => {
    const built = buildActionOp({
      author: op.author, replicaId: op.replica_id, baseSeq: 12, session: "5e55000000000000000000000000000a", name: `Edit ${n}`,
      call: moveBy([ref(DIGEST_KINDS.product, id)], [0, 50, 0]),
    });
    return { op_id: built.op_id, pid, op: built, state: "pending", label: `Edit ${n}`, created: n };
  };
  const refs = ["0199c6a2e00070068000000000000001", "0199c6a2e00070068000000000000002", "0199c6a2e00070068000000000000003"];
  const entries = refs.map((r, i) => make(i + 1, r));
  for (const e of entries) await store.put(e);

  // Offline: everything waits.
  let out = await flush(store, pid, async () => {
    throw new PushError(true, "offline");
  });
  check("offline waits", out.waiting === 3 && (await store.list(pid)).every((e) => e.state === "pending"));

  // The second conflicts: the first accepted, the third not processed, then sent again and accepted.
  const sent: string[][] = [];
  let seq = 12;
  out = await flush(store, pid, async (_replica, ops): Promise<PushAnswer> => {
    sent.push(ops.map((o) => o.op_id));
    const results: PushAnswer["results"] = [];
    let stopped = false;
    for (const o of ops) {
      if (stopped) results.push({ op_id: o.op_id, status: "not_processed" });
      else if (o.op_id === entries[1].op_id) {
        stopped = true;
        results.push({ op_id: o.op_id, status: "rejected", reason: "conflict",
          winning: [{ op_id: "f".repeat(32), server_seq: 13, author: "0199c6a2f0007000a000000000000007", author_kind: "person", name: "Move sofa" }] });
      } else results.push({ op_id: o.op_id, status: "accepted", server_seq: ++seq });
    }
    return { head_seq: seq, results };
  });
  const after = new Map((await store.list(pid)).map((e) => [e.op_id, e]));
  check("first accepted", after.get(entries[0].op_id)?.state === "accepted" && after.get(entries[0].op_id)?.seq === 13);
  check("second rejected with its winner", after.get(entries[1].op_id)?.state === "rejected" && after.get(entries[1].op_id)?.winner?.name === "Move sofa");
  check("the winner keeps its author_kind", after.get(entries[1].op_id)?.winner?.author_kind === "person");
  check("third sent again", sent.length === 2 && same(sent[1], [entries[2].op_id]) && after.get(entries[2].op_id)?.state === "accepted");
  check("rejected never re-sent", !sent[1].includes(entries[1].op_id) && out.rejected.length === 1 && out.accepted.length === 2);

  // A 422 fails the batch (never retried as sent).
  const bad = make(9, refs[0]);
  await store.put(bad);
  out = await flush(store, pid, async () => {
    throw new PushError(false, "ops[0].touched: sorted and unique", 422, "validation_failed");
  });
  check("422 fails", out.failed.length === 1 && (await store.list(pid)).find((e) => e.op_id === bad.op_id)?.state === "failed");
}

// --- who a rejection names (PF9a) ---------------------------------------------------------------

function authors(): void {
  const text: ConflictText = {
    named: (name) => `${name} changed this first — your edit was replaced`,
    self: "You changed this first on another device — your edit was replaced",
    agent: "An assistant or script",
    someone: "Someone",
  };
  const me = "0199c6a2f0007000a000000000000042";
  const sam = "0199c6a2f0007000a000000000000007";
  const key = "0199c6a2f0007000a0000000000000aa";
  const stranger = "0199c6a2f0007000a0000000000000bb";
  const names = new Map([[sam, "Sam"]]);
  const won = (author: string, author_kind?: Winner["author_kind"]): Winner => ({ author, author_kind, name: "Move sofa", server_seq: 13 });
  check("authors: self", conflictLine(won(me, "person"), me, names, text) === text.self);
  check("authors: a member by name", conflictLine(won(sam, "person"), me, names, text) === "Sam changed this first — your edit was replaced");
  check("authors: an API key reads as an agent", conflictLine(won(key, "agent"), me, names, text) === "An assistant or script changed this first — your edit was replaced");
  check("authors: an agent whatever its id", conflictLine(won(sam, "agent"), me, names, text) === "An assistant or script changed this first — your edit was replaced");
  check("authors: an unknown person", conflictLine(won(stranger, "person"), me, names, text) === "Someone changed this first — your edit was replaced");
  check("authors: no winner", conflictLine(null, me, names, text) === "Someone changed this first — your edit was replaced");
  check("authors: stored before author_kind", conflictLine(won(sam), me, names, text) === "Sam changed this first — your edit was replaced");
  check("authors: signed out", conflictLine(won(me, "person"), null, names, text) === "Someone changed this first — your edit was replaced");
}

// --- orientation ------------------------------------------------------------------------------------

function orientation(): void {
  const upright = lookFromOrientation(0, 90, 0);
  check("upright faces north", near(upright.yawDeg, 0) && near(upright.pitchDeg, 0), JSON.stringify(upright));
  const west = lookFromOrientation(90, 90, 0);
  check("alpha 90 faces west", near(west.yawDeg, 270), JSON.stringify(west));
  check("flat looks down", near(lookFromOrientation(0, 0, 0).pitchDeg, -90));
  const tilted = lookFromOrientation(0, 120, 0);
  check("tilted back looks up", near(tilted.pitchDeg, 30, 1e-6), JSON.stringify(tilted));
  const landscape = lookFromOrientation(0, 0, -90);
  check("landscape is level", near(landscape.pitchDeg, 0, 1e-6), JSON.stringify(landscape));
  check("angle delta", angleDelta(10, 350) === 20 && angleDelta(350, 10) === -20 && angleDelta(180, 0) === 180);
  const toKitchen = bearingTo([4200, 1800, 1600], [8600, 2400, 1600]);
  check("hotspot bearing", Math.round(toKitchen.yawDeg) === 82 && toKitchen.pitchDeg < 0, JSON.stringify(toKitchen));
}

async function main(): Promise<void> {
  builder();
  tileDiff();
  cachePolicy();
  await outbox();
  authors();
  orientation();
  if (failures.length) {
    console.error(`selftest: ${failures.length} of ${checks} checks failed`);
    for (const f of failures) console.error(`  FAIL ${f}`);
    process.exitCode = 1;
  } else {
    console.log(`selftest: ${checks} checks passed (action builder, tile diff, cache policy, outbox, authors, orientation)`);
  }
}

main().catch((err) => {
  console.error("selftest crashed:", err);
  process.exitCode = 1;
});
