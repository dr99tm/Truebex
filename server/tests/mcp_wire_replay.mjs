// PF12b: the fake pipe of agent-interface.md §9 for the platform's package
// tests. It plays the app's side of one wire fixture script
// (packages/mcp/test/fixtures/<script>.jsonl, truebex-agent-wire/1, copied from
// the app repo): every line the bridge relays must equal the script's `send`
// (after ${…} substitution), and it answers with the script's `expect`, filled
// out to a whole answer ("*" and captured refs get stand-in values). The
// bridge under test is the copied truebex-mcp.mjs; this file shares no code
// with it (Node built-ins only), so a framing bug cannot hide on both sides.
//
//   node server/tests/mcp_wire_replay.mjs --script <file.jsonl> --tools <tools.json>
//
// Prints {pipe, token} as one JSON line once listening; when stdin closes it
// prints "MWAGENTREPLAY: script=<name> lines=<n> mismatches=<m>" (the stub's
// MWAGENTSTUB line), the mismatches on stderr, and exits 1 if there were any.
// Lines a bridge never relays: `setup` and `prompt` (the app's side of the
// script) and calls of a tool tools.json lacks (the bridge answers -32602
// itself, §6.6).

import { createHash, randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import { createServer } from "node:net";
import { basename, join } from "node:path";
import { isDeepStrictEqual } from "node:util";

function arg(name) {
  const i = process.argv.indexOf(name);
  return i > 0 ? process.argv[i + 1] : undefined;
}

const scriptPath = arg("--script");
const toolsText = readFileSync(arg("--tools"), "utf8");
const toolsHash = createHash("sha1").update(toolsText.replace(/\r/g, ""), "utf8").digest("hex");
const known = new Set(JSON.parse(toolsText).tools.map((t) => t.name));
const rows = readFileSync(scriptPath, "utf8")
  .split("\n")
  .filter((l) => l.trim())
  .map((l) => JSON.parse(l));
const steps = rows.filter((r) => r.send && (r.send.op !== "call" || known.has(r.send.tool)));

const token = randomBytes(16).toString("hex");
const vars = { token };
const mismatches = [];
let next = 0;
let minted = 100;

function subst(value) {
  if (typeof value === "string") return value.replace(/\$\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
  if (Array.isArray(value)) return value.map(subst);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, subst(v)]));
  return value;
}

/** "*" (any value in the script) becomes a stand-in of the key's shape. */
function fill(value, key) {
  if (value === "*") {
    if (key === "session") return "a".repeat(32);
    if (key === "toolsHash") return toolsHash;
    return `replay-${key}-${minted++}`;
  }
  if (Array.isArray(value)) return value.map((v) => fill(v, key));
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, fill(v, k)]));
  return value;
}

/** Put a minted ref at a capture path ("structured.matches.0.ref") unless the answer already holds one. */
function plant(target, path, name) {
  const keys = path.split(".");
  let at = target;
  keys.forEach((k, i) => {
    const last = i === keys.length - 1;
    const nextIsIndex = !last && /^\d+$/.test(keys[i + 1]);
    if (last) {
      if (at[k] === undefined || (typeof at[k] === "string" && at[k].startsWith("replay-"))) at[k] = `${name}#${minted++}`;
      vars[name] = at[k];
    } else {
      if (at[k] === undefined) at[k] = nextIsIndex ? [] : {};
      at = at[k];
    }
  });
}

/** `want` must be a subset of `got` (objects by key, everything else equal). */
function subset(want, got) {
  if (want && typeof want === "object" && !Array.isArray(want)) {
    return got && typeof got === "object" && Object.entries(want).every(([k, v]) => subset(v, got[k]));
  }
  return isDeepStrictEqual(want, got);
}

function answerFor(step, got) {
  const expect = subst(step.expect || {});
  if (step.send.op === "hello") {
    const hello = fill({ op: "hello", ok: true, app: { name: "Truebex", version: "1.0.0", build: "replay", project: "Riverside Court" }, session: "*", grants: [], toolsHash: "*", ...expect }, "hello");
    hello.app = { name: "Truebex", version: "1.0.0", build: "replay", project: "Riverside Court", ...hello.app };
    return hello;
  }
  if (expect.rpcError) {
    return { op: "result", id: got.id, ok: false, rpcError: { message: `Unknown tool: ${got.tool}`, ...expect.rpcError } };
  }
  const ok = expect.ok !== false;
  const answer = { op: "result", id: got.id, ok, isError: expect.isError ?? !ok, ...fill(expect, "result") };
  answer.id = got.id;
  answer.structured = { ok, ...(answer.structured || {}) };
  if (!ok && !answer.structured.detail) answer.structured.detail = `${answer.structured.code || "error"} (replayed)`;
  for (const [name, path] of Object.entries(step.capture || {})) plant(answer, path, name);
  answer.text ??= answer.structured.detail || answer.structured.text || `${got.tool} ok (replayed)`;
  return answer;
}

function onMessage(socket, got) {
  if (got.op === "tools") {
    socket.write(JSON.stringify({ op: "tools", id: got.id, toolsHash, tools: JSON.parse(toolsText) }) + "\n");
    return;
  }
  if (got.op === "cancel") return;
  const step = steps[next];
  const where = `step ${next + 1} (${step ? step.send.op + (step.send.tool ? " " + step.send.tool : "") : "after the end"})`;
  if (!step) {
    mismatches.push(`${where}: the bridge sent ${JSON.stringify(got)}`);
    socket.write(JSON.stringify({ op: "result", id: got.id, ok: false, isError: true, text: "replay: unexpected", structured: { ok: false, code: "replay_mismatch", detail: "unexpected" } }) + "\n");
    return;
  }
  const want = subst(step.send);
  let problem = null;
  if (got.op !== want.op) problem = `op ${got.op}, script ${want.op}`;
  else if (want.op === "hello") {
    const { client, ...rest } = want;
    if (!subset(rest, got)) problem = `hello ${JSON.stringify(got)} does not carry ${JSON.stringify(rest)}`;
    else if (client && !subset(client, got.client)) problem = `hello client ${JSON.stringify(got.client)}, script ${JSON.stringify(client)}`;
  } else if (got.tool !== want.tool || !isDeepStrictEqual(got.args, want.args)) {
    problem = `relayed ${JSON.stringify({ tool: got.tool, args: got.args })}, script ${JSON.stringify({ tool: want.tool, args: want.args })}`;
  }
  next += 1;
  if (problem) {
    mismatches.push(`${where}: ${problem}`);
    socket.write(JSON.stringify(want.op === "hello"
      ? { op: "hello", ok: false, code: "wire_unsupported", detail: `replay: ${problem}` }
      : { op: "result", id: got.id, ok: false, isError: true, text: `replay: ${problem}`, structured: { ok: false, code: "replay_mismatch", detail: problem } }) + "\n");
    return;
  }
  socket.write(JSON.stringify(answerFor(step, got)) + "\n");
}

const pipe = process.platform === "win32"
  ? `\\\\.\\pipe\\truebex-agent-replay-${process.pid}-${randomBytes(4).toString("hex")}`
  : join("/tmp", `truebex-agent-replay-${process.pid}-${randomBytes(4).toString("hex")}`);

const server = createServer((socket) => {
  socket.on("error", () => {});
  let buffer = "";
  socket.setEncoding("utf8");
  socket.on("data", (chunk) => {
    buffer += chunk;
    let nl;
    while ((nl = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, nl).replace(/\r$/, "");
      buffer = buffer.slice(nl + 1);
      if (!line.trim()) continue;
      let got;
      try {
        got = JSON.parse(line);
      } catch {
        mismatches.push(`a line that is not JSON: ${line.slice(0, 200)}`);
        continue;
      }
      onMessage(socket, got);
    }
  });
});
await new Promise((resolve, reject) => {
  server.once("error", reject);
  server.listen(pipe, resolve);
});
process.stdout.write(JSON.stringify({ pipe, token }) + "\n");

let done = false;
function finish() {
  if (done) return;
  done = true;
  for (const m of mismatches) process.stderr.write(`replay mismatch: ${m}\n`);
  process.stdout.write(`MWAGENTREPLAY: script=${basename(scriptPath, ".jsonl")} lines=${next} mismatches=${mismatches.length}\n`, () => {
    server.close();
    process.exit(mismatches.length ? 1 : 0);
  });
}
process.stdin.on("end", finish);
process.stdin.on("close", finish);
process.stdin.resume();
