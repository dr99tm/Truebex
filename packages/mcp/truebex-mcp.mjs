#!/usr/bin/env node
// Truebex MCP server (roadmap 40 / AI1) -- the stdio entry point.
//
// The person's own MCP client (Claude Desktop, Claude Code, any client that
// launches a stdio server) starts this file with Node; it talks MCP on
// stdin / stdout and relays the tool calls into the running Truebex app over
// its named pipe. Truebex never sees, stores or forwards the client's
// credentials: the subscription stays between the person and their client.
//
//   node truebex-mcp.mjs                 the newest running Truebex (Shipping first)
//   TRUEBEX_AGENT_PIPE=<name> TRUEBEX_AGENT_TOKEN=<hex> node truebex-mcp.mjs   one exact app
//
// stdout carries only MCP messages; logs go to stderr; the process exits
// promptly when stdin closes. Contract: Docs/roadmap/40/contracts/agent-interface.md.

import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { INVALID_REQUEST, LineReader, PARSE_ERROR, errorResponse, frame } from './lib/jsonrpc.mjs';
import { McpServer } from './lib/server.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const log = (s) => process.stderr.write(`[truebex-mcp] ${s}\n`);
const send = (m) => process.stdout.write(frame(m));

const server = new McpServer({ dir: here, send, log });

let closing = false;
function shutdown() {
  if (closing) { return; }
  closing = true;
  server.link.close();
  const hard = setTimeout(() => process.exit(0), 500);
  hard.unref();
  process.stdout.write('', () => process.exit(0));
}

const reader = new LineReader((line) => {
  let msg;
  try { msg = JSON.parse(line); } catch {
    send(errorResponse(null, PARSE_ERROR, 'Parse error'));
    return;
  }
  server.handle(msg);
}, () => send(errorResponse(null, INVALID_REQUEST, 'message longer than 1 MiB')));

process.stdin.on('data', (chunk) => reader.push(chunk));
process.stdin.on('end', shutdown);
process.stdin.on('close', shutdown);
process.stdout.on('error', shutdown);   // the client went away
