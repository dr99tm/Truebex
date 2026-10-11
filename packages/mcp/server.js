"use strict";
// truebex-mcp: the stdio MCP server that lets an MCP client act on the model
// open in the Truebex app (contract agent-interface v1.0.0 §6.6).
//
// * stdio: one JSON-RPC message per line, UTF-8; stdout carries only MCP
//   messages, logs go to stderr; the server exits when stdin closes.
// * It answers server/discover, initialize (the legacy 2025-11-25 and
//   2025-06-18 handshake, in the revision the client asks for), ping and
//   tools/list itself from tools.json, so the tools list with the app closed.
// * It relays tools/call (and notifications/cancelled) to the app over the
//   per-user named pipe \\.\pipe\truebex-agent-<USERNAME>, in the same newline
//   framing, and answers app_not_running when no app holds the pipe.
// * It never reads, holds or sends a platform credential (§4).
//
// PF12 stand-in, written to the contract until the app's own bridge
// (Tools/mcp/server.js, AI1) exists; scripts/sync-mcp.ps1 replaces this file
// with that copy at an app release, after which it is never edited here.

const fs = require("fs");
const net = require("net");
const os = require("os");
const path = require("path");
const readline = require("readline");

const REVISION = "2026-07-28";
const LEGACY = ["2025-11-25", "2025-06-18"];
const SUPPORTED = [REVISION, ...LEGACY];
const META = "io.modelcontextprotocol/";
const TTL_MS = 3600000;

const TOOLS = JSON.parse(fs.readFileSync(path.join(__dirname, "tools.json"), "utf8"));
const TOOL_NAMES = new Set(TOOLS.tools.map((t) => t.name));
const PACKAGE = (() => {
  try {
    return JSON.parse(fs.readFileSync(path.join(__dirname, "package.json"), "utf8"));
  } catch {
    return { version: TOOLS.version };
  }
})();

function pipePath() {
  if (process.env.TRUEBEX_AGENT_PIPE) return process.env.TRUEBEX_AGENT_PIPE;
  const user = (process.env.USERNAME || process.env.USER || os.userInfo().username || "user").replace(/[^A-Za-z0-9_.-]/g, "_");
  return process.platform === "win32" ? `\\\\.\\pipe\\truebex-agent-${user}` : path.join(os.tmpdir(), `truebex-agent-${user}.sock`);
}

function log(...args) {
  process.stderr.write(`[truebex-mcp] ${args.join(" ")}\n`);
}

function send(message) {
  // JSON.stringify never emits a raw newline: one message per line.
  process.stdout.write(JSON.stringify(message) + "\n");
}

function result(id, value) {
  send({ jsonrpc: "2.0", id, result: value });
}

function error(id, code, message, data) {
  const err = { code, message };
  if (data !== undefined) err.data = data;
  send({ jsonrpc: "2.0", id, error: err });
}

function toolError(id, code, detail, data = null) {
  const requestId = require("crypto").randomBytes(16).toString("hex");
  result(id, {
    resultType: "complete",
    content: [{ type: "text", text: detail }],
    structuredContent: { detail, code, request_id: requestId, data },
    isError: true,
  });
}

function serverInfo() {
  return { name: "truebex", title: "Truebex", version: PACKAGE.version || TOOLS.version };
}

// --- the app's pipe --------------------------------------------------------------------------

let pipe = null; // { socket, pending: Map<id, true> }
let connecting = null;
let inflight = 0; // relayed calls not answered yet

function connect() {
  if (pipe) return Promise.resolve(pipe);
  if (connecting) return connecting;
  connecting = new Promise((resolve, reject) => {
    const socket = net.connect(pipePath());
    socket.setEncoding("utf8");
    socket.once("connect", () => {
      const conn = { socket, pending: new Map() };
      readline.createInterface({ input: socket, crlfDelay: Infinity }).on("line", (line) => {
        if (!line.trim()) return;
        let message;
        try {
          message = JSON.parse(line);
        } catch {
          log("the app sent a line that is not JSON");
          return;
        }
        if (message && message.id !== undefined && conn.pending.delete(JSON.stringify(message.id))) inflight--;
        send(message);
      });
      socket.on("close", () => {
        if (pipe === conn) pipe = null;
        for (const key of conn.pending.keys()) {
          inflight--;
          toolError(JSON.parse(key), "app_not_running", "The Truebex app closed before it answered. Open it and try again.");
        }
        conn.pending.clear();
      });
      pipe = conn;
      connecting = null;
      resolve(conn);
    });
    socket.once("error", (err) => {
      connecting = null;
      reject(err);
    });
  });
  return connecting;
}

async function relay(message) {
  const call = message.id !== undefined;
  if (call) inflight++;
  let conn;
  try {
    conn = await connect();
  } catch {
    if (call) {
      inflight--;
      toolError(message.id, "app_not_running", "Truebex is not running. Open the app and a project, then try again.");
    }
    return;
  }
  if (call) conn.pending.set(JSON.stringify(message.id), true);
  conn.socket.write(JSON.stringify(message) + "\n");
}

// --- MCP ---------------------------------------------------------------------------------------

function modernVersion(params) {
  const meta = params && params._meta;
  return meta && typeof meta === "object" ? meta[META + "protocolVersion"] : undefined;
}

function handle(message) {
  if (Array.isArray(message) || !message || typeof message !== "object" || message.jsonrpc !== "2.0") {
    error(null, -32600, "Invalid Request: one JSON-RPC 2.0 object per line");
    return;
  }
  const { id, method, params } = message;
  const isNotification = id === undefined;
  if (typeof method !== "string") {
    if (!isNotification && !("result" in message) && !("error" in message)) error(id, -32600, "Invalid Request");
    return;
  }
  const asked = modernVersion(params);
  if (asked !== undefined && !SUPPORTED.includes(asked)) {
    if (!isNotification) error(id, -32022, `Unsupported protocol version ${asked}`, { supported: SUPPORTED, requested: asked });
    return;
  }
  switch (method) {
    case "server/discover":
      return result(id, {
        resultType: "complete",
        supportedVersions: SUPPORTED,
        capabilities: { tools: { listChanged: false } },
        serverInfo: serverInfo(),
        instructions: "Tools act on the project open in the Truebex app. The app asks you to allow each kind of action.",
      });
    case "initialize": {
      const wanted = params && params.protocolVersion;
      return result(id, {
        protocolVersion: LEGACY.includes(wanted) ? wanted : LEGACY[0],
        capabilities: { tools: { listChanged: false } },
        serverInfo: serverInfo(),
        instructions: "Tools act on the project open in the Truebex app. The app asks you to allow each kind of action.",
      });
    }
    case "ping":
      return isNotification ? undefined : result(id, {});
    case "tools/list":
      return result(id, { resultType: "complete", tools: TOOLS.tools, ttlMs: TTL_MS, cacheScope: "private" });
    case "tools/call": {
      const name = params && params.name;
      if (!TOOL_NAMES.has(name)) return error(id, -32602, `Unknown tool: ${name}`, { tools: [...TOOL_NAMES] });
      return void relay(message);
    }
    case "notifications/cancelled":
      if (pipe) pipe.socket.write(JSON.stringify(message) + "\n");
      return;
    default:
      if (method.startsWith("notifications/")) return; // initialized and the rest: nothing to answer
      if (!isNotification) error(id, -32601, `Method not found: ${method}`);
  }
}

function main() {
  const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  input.on("line", (line) => {
    if (!line.trim()) return;
    let message;
    try {
      message = JSON.parse(line);
    } catch {
      error(null, -32700, "Parse error: one JSON-RPC message per line");
      return;
    }
    handle(message);
  });
  input.on("close", () => {
    // The client closed stdin: answer what is in flight (up to 1 s), then go.
    const started = Date.now();
    const finish = () => {
      if (inflight > 0 && Date.now() - started < 1000) return void setTimeout(finish, 20);
      if (pipe) pipe.socket.end();
      process.stdout.write("", () => process.exit(0));
    };
    finish();
  });
  log(`ready (MCP ${SUPPORTED.join(", ")}; app pipe ${pipePath()})`);
}

module.exports = { main, handle, pipePath, SUPPORTED };

if (require.main === module) main();
