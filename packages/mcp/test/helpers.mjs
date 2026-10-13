// Test helpers: spawn the real truebex-mcp.mjs as an MCP client would (stdio)
// and exchange newline-delimited JSON-RPC with it.

import { spawn } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const MCP_DIR = join(dirname(fileURLToPath(import.meta.url)), '..');
export const ENTRY = join(MCP_DIR, 'truebex-mcp.mjs');
export const MODERN = '2026-07-28';

export function modernMeta(extra = {}) {
  return {
    'io.modelcontextprotocol/protocolVersion': MODERN,
    'io.modelcontextprotocol/clientCapabilities': {},
    'io.modelcontextprotocol/clientInfo': { name: 'node-test', version: '1.0.0' },
    ...extra,
  };
}

/** A fresh empty instances folder: "no app is running". */
export function emptyInstances() { return mkdtempSync(join(tmpdir(), 'truebex-no-app-')); }

export function spawnServer(env = {}) {
  const proc = spawn(process.execPath, [ENTRY], {
    env: { ...process.env, TRUEBEX_AGENT_PIPE: '', TRUEBEX_AGENT_TOKEN: '', ...env },
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  const lines = [];
  const raw = [];
  const waiters = [];
  let buf = '';
  let stderr = '';
  proc.stdout.setEncoding('utf8');
  proc.stdout.on('data', (d) => {
    buf += d;
    let nl;
    while ((nl = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, nl);
      buf = buf.slice(nl + 1);
      raw.push(line);
      let msg;
      try { msg = JSON.parse(line); } catch { msg = { __unparsable: line }; }
      lines.push(msg);
      for (const w of [...waiters]) {
        if (w.pred(msg)) { waiters.splice(waiters.indexOf(w), 1); clearTimeout(w.timer); w.resolve(msg); }
      }
    }
  });
  proc.stderr.setEncoding('utf8');
  proc.stderr.on('data', (d) => { stderr += d; });
  const exited = new Promise((resolve) => proc.on('exit', (code) => resolve(code)));

  let nextId = 1;
  return {
    proc, lines, raw, exited,
    get stderr() { return stderr; },
    send(msg) { proc.stdin.write(JSON.stringify(msg) + '\n'); },
    sendRaw(text) { proc.stdin.write(text); },
    /** Send a request and wait for the response with its id. */
    request(method, params, timeoutMs = 5000) {
      const id = nextId++;
      this.send({ jsonrpc: '2.0', id, method, ...(params === undefined ? {} : { params }) });
      return this.waitFor((m) => m.id === id, timeoutMs, `${method}#${id}`);
    },
    waitFor(pred, timeoutMs = 5000, label = 'message') {
      const hit = lines.find(pred);
      if (hit) { return Promise.resolve(hit); }
      return new Promise((resolve, reject) => {
        const w = { pred, resolve, timer: setTimeout(() => { waiters.splice(waiters.indexOf(w), 1); reject(new Error(`timeout waiting for ${label}; stderr: ${stderr}`)); }, timeoutMs) };
        waiters.push(w);
      });
    },
    async close() {
      proc.stdin.end();
      const t = setTimeout(() => proc.kill(), 3000);
      await exited;
      clearTimeout(t);
    },
  };
}
