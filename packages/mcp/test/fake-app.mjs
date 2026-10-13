// A stand-in for the Truebex app on the wire (truebex-agent-wire/1): a named-pipe
// server that writes an instance file, checks the token and answers from canned
// data. The node --test suite (AI1-mcp.ps1) drives the real truebex-mcp.mjs
// against it, so no test needs Unreal or a model.

import { mkdirSync, mkdtempSync, rmSync, writeFileSync, readFileSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { LineReader, frame } from '../lib/jsonrpc.mjs';
import { toolsHash } from '../lib/schema.mjs';
import { pipePath } from '../lib/wire.mjs';

const here = dirname(fileURLToPath(import.meta.url));
export const TOOLS_TEXT = readFileSync(join(here, '..', 'tools.json'), 'utf8');

export const DIGEST = 'TRUEBEX fake-app tool=3D doc=Riverside Court\nVIEW persp storey=Second Floor\nDOC walls=48 openings=19 undo=0';

/**
 * Start a fake app. Options: delayMs (every call answers after it), tools
 * (override the tools.json text), connectionsOff (refuse hello).
 * Returns { dir, pipe, token, calls, cancels, hellos, close() }.
 */
export async function startFakeApp(opts = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'truebex-fake-app-'));
  const instances = join(dir, 'instances');
  mkdirSync(instances, { recursive: true });
  const name = `truebex-agent-test-${process.pid}-${Math.floor(Math.random() * 1e9)}`;
  const pipe = pipePath(name);
  const token = 'f'.repeat(32);
  const toolsText = opts.tools || TOOLS_TEXT;
  const state = { calls: [], cancels: [], hellos: [], sockets: new Set() };

  const server = createServer((socket) => {
    state.sockets.add(socket);
    socket.on('close', () => state.sockets.delete(socket));
    socket.on('error', () => {});
    let session = null;
    const reader = new LineReader((line) => {
      const m = JSON.parse(line);
      if (m.op === 'hello') {
        state.hellos.push(m);
        if (opts.connectionsOff) { socket.write(frame({ op: 'hello', ok: false, code: 'connections_off', detail: 'off' })); return; }
        if (m.token !== token) { socket.write(frame({ op: 'hello', ok: false, code: 'bad_token', detail: 'wrong token' })); return; }
        session = 'a'.repeat(32);
        socket.write(frame({ op: 'hello', ok: true, app: { name: 'Truebex', version: '1.0.0', build: 'fake', project: 'Riverside Court' }, session, grants: [], toolsHash: toolsHash(toolsText) }));
        return;
      }
      if (!session) { socket.destroy(); return; }
      if (m.op === 'tools') { socket.write(frame({ op: 'tools', id: m.id, toolsHash: toolsHash(toolsText), tools: JSON.parse(toolsText) })); return; }
      if (m.op === 'cancel') { state.cancels.push(m.id); return; }
      if (m.op === 'read') {
        if (m.uri === 'truebex://state/digest') {
          socket.write(frame({ op: 'resource', id: m.id, ok: true, contents: [{ uri: m.uri, mimeType: 'text/plain', text: DIGEST }] }));
        } else {
          socket.write(frame({ op: 'resource', id: m.id, ok: false, code: 'not_found', detail: 'no such entity' }));
        }
        return;
      }
      if (m.op === 'call') {
        state.calls.push(m);
        const answer = () => {
          if (state.cancels.includes(m.id)) { return; }   // the app drops a cancelled call
          socket.write(frame(answerCall(m)));
        };
        if (opts.delayMs) { setTimeout(answer, opts.delayMs); } else { answer(); }
      }
    }, () => socket.destroy());
    socket.on('data', (c) => reader.push(c));
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(pipe, resolve); });

  writeFileSync(join(instances, `${process.pid}.json`), JSON.stringify({
    pid: process.pid, pipe, token, configuration: 'Development', project: 'Riverside Court', version: '1.0.0', started: new Date().toISOString(),
  }));

  return {
    dir, instances, pipe, token,
    get calls() { return state.calls; },
    get cancels() { return state.cancels; },
    get hellos() { return state.hellos; },
    async close() {
      for (const s of state.sockets) { s.destroy(); }
      await new Promise((r) => server.close(r));
      rmSync(dir, { recursive: true, force: true });
    },
  };
}

function answerCall(m) {
  if (m.tool === 'read_state') {
    return { op: 'result', id: m.id, ok: true, isError: false, text: DIGEST, structured: { ok: true, schema: 'truebex-agent-state/1', revision: 7, document_version: 38, digest: DIGEST } };
  }
  if (m.tool === 'place' && m.args && m.args.kind === 'window') {
    return { op: 'result', id: m.id, ok: true, isError: false, text: 'Window placed 0.95 m along Wall 42', structured: { ok: true, undo_group: 'b'.repeat(32), undo_step: 'Agent: place window', created: ['opening#20'], changed: ['wall#42'], deleted: [], changed_keys: ['doc.openings', 'doc.undo'], text: 'Window placed 0.95 m along Wall 42', warnings: [] } };
  }
  if (m.tool === 'export_pdf') {
    return { op: 'result', id: m.id, ok: false, isError: true, text: 'permission export not granted', structured: { ok: false, code: 'permission_required', detail: 'permission export not granted', data: { needed: 'export' } } };
  }
  if (m.tool === 'nope') {
    return { op: 'result', id: m.id, ok: false, rpcError: { code: -32602, message: 'Unknown tool: nope' } };
  }
  return { op: 'result', id: m.id, ok: true, isError: false, text: `${m.tool} ok`, structured: { ok: true, text: `${m.tool} ok` } };
}
