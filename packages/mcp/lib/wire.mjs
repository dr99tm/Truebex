// Truebex MCP server (roadmap 40 / AI1): the link to the running app over its
// per-instance named pipe, wire protocol truebex-agent-wire/1.
//
//   instance file  %LOCALAPPDATA%\Truebex\agent\instances\<pid>.json
//                  {pid, pipe, token, configuration, project, version, started}
//   pipe           \\.\pipe\truebex-agent-<pid>   (current user only, local only)
//   framing        one JSON object per line, UTF-8, <= 1 MiB (the stdio framing)
//
//   -> hello {wire, token, client{name,version,title}, era, pid}
//   <- hello {ok, app{name,version,build,project}, session, grants[], toolsHash} | {ok:false, code, detail}
//   -> call {id, tool, args}      <- result {id, ok, isError, text, structured} | {id, rpcError{code,message,data}}
//   -> read {id, uri}             <- resource {id, ok, contents[]} | {id, ok:false, code, detail}
//   -> tools {id}                 <- tools {id, toolsHash, tools{...tools.json}}
//   -> cancel {id}                (no answer; the app drops the call if it has not started)
//   <- event {event: grants | tools-changed | closing | disconnected, ...}
//
// Overrides (tests, -mwagentpipe launches): TRUEBEX_AGENT_PIPE + TRUEBEX_AGENT_TOKEN
// name the pipe directly; TRUEBEX_AGENT_INSTANCES_DIR moves the instance folder.

import { EventEmitter } from 'node:events';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { connect } from 'node:net';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { LineReader, frame } from './jsonrpc.mjs';

export const WIRE = 'truebex-agent-wire/1';

export function instancesDir(env = process.env) {
  if (env.TRUEBEX_AGENT_INSTANCES_DIR) { return env.TRUEBEX_AGENT_INSTANCES_DIR; }
  const local = env.LOCALAPPDATA || join(homedir(), 'AppData', 'Local');
  return join(local, 'Truebex', 'agent', 'instances');
}

export function pipePath(name) {
  if (!name) { return ''; }
  if (name.startsWith('\\\\.\\pipe\\') || name.startsWith('//./pipe/')) { return name; }
  return process.platform === 'win32' ? `\\\\.\\pipe\\${name}` : join('/tmp', name);
}

function alive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) { return false; }
  try { process.kill(pid, 0); return true; } catch (e) { return e.code === 'EPERM'; }
}

/** Every live instance, best first: Shipping before the rest, then the newest. */
export function listInstances(dir = instancesDir()) {
  if (!existsSync(dir)) { return []; }
  const out = [];
  for (const f of readdirSync(dir)) {
    if (!f.endsWith('.json')) { continue; }
    try {
      const inst = JSON.parse(readFileSync(join(dir, f), 'utf8'));
      if (inst && inst.pipe && alive(inst.pid)) { out.push(inst); }
    } catch { /* a half-written or foreign file */ }
  }
  out.sort((a, b) => {
    const sa = a.configuration === 'Shipping' ? 0 : 1;
    const sb = b.configuration === 'Shipping' ? 0 : 1;
    if (sa !== sb) { return sa - sb; }
    return String(b.started || '').localeCompare(String(a.started || ''));
  });
  return out;
}

/** The pipe + token to use, or null when no app is listening. */
export function pickTarget(env = process.env) {
  if (env.TRUEBEX_AGENT_PIPE) {
    return { pipe: pipePath(env.TRUEBEX_AGENT_PIPE), token: env.TRUEBEX_AGENT_TOKEN || '', source: 'env' };
  }
  const best = listInstances(instancesDir(env))[0];
  return best ? { pipe: pipePath(best.pipe), token: best.token || '', source: 'instance', instance: best } : null;
}

/**
 * One connection to the app. connect() opens the pipe and says hello; call /
 * read / tools send a request and resolve with the app's answer (or reject on a
 * timeout or a closed pipe). 'event' and 'close' are emitted.
 */
export class AppLink extends EventEmitter {
  constructor(log = () => {}) {
    super();
    this.log = log;
    this.socket = null;
    this.pending = new Map();
    this.nextId = 1;
    this.hello = null;
    this.target = null;
  }

  get connected() { return !!(this.socket && this.hello && this.hello.ok); }

  async connect(client, era, env = process.env, timeoutMs = 3000) {
    this.close();
    const target = pickTarget(env);
    if (!target) { return { ok: false, code: 'app_not_running', detail: 'no Truebex instance file' }; }
    this.target = target;
    const socket = await new Promise((resolve) => {
      const s = connect(target.pipe);
      const timer = setTimeout(() => { s.destroy(); resolve(null); }, timeoutMs);
      s.once('connect', () => { clearTimeout(timer); resolve(s); });
      s.once('error', (e) => { clearTimeout(timer); this.log(`pipe ${target.pipe}: ${e.code || e.message}`); resolve(null); });
    });
    if (!socket) { return { ok: false, code: 'app_not_running', detail: `cannot open ${target.pipe}` }; }
    this.socket = socket;
    const reader = new LineReader((line) => this.onLine(line), () => this.log('app sent an oversize line'));
    socket.on('data', (chunk) => reader.push(chunk));
    socket.on('error', (e) => this.log(`pipe error: ${e.code || e.message}`));
    socket.on('close', () => this.onClose());
    const hello = await this.request({
      op: 'hello', wire: WIRE, token: target.token, client, era, pid: process.pid,
    }, timeoutMs).catch((e) => ({ ok: false, code: 'app_not_running', detail: e.message }));
    if (!hello || !hello.ok) {
      this.close();
      return { ok: false, code: (hello && hello.code) || 'app_not_running', detail: (hello && hello.detail) || 'hello refused' };
    }
    this.hello = hello;
    return hello;
  }

  onLine(line) {
    let m;
    try { m = JSON.parse(line); } catch { this.log('app sent a line that is not JSON'); return; }
    if (m.op === 'event') { this.emit('event', m); return; }
    const key = m.op === 'hello' ? 'hello' : m.id;
    const p = this.pending.get(key);
    if (!p) { return; }
    this.pending.delete(key);
    clearTimeout(p.timer);
    p.resolve(m);
  }

  onClose() {
    const wasConnected = this.connected;
    this.socket = null;
    this.hello = null;
    for (const [, p] of this.pending) { clearTimeout(p.timer); p.reject(new Error('Truebex closed the connection')); }
    this.pending.clear();
    if (wasConnected) { this.emit('close'); }
  }

  request(msg, timeoutMs) {
    if (!this.socket) { return Promise.reject(new Error('not connected')); }
    const key = msg.op === 'hello' ? 'hello' : msg.id;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(key);
        reject(Object.assign(new Error('timeout'), { code: 'timeout' }));
      }, timeoutMs);
      this.pending.set(key, { resolve, reject, timer });
      this.socket.write(frame(msg));
    });
  }

  call(tool, args, timeoutMs) {
    const id = this.nextId++;
    return { id, promise: this.request({ op: 'call', id, tool, args }, timeoutMs) };
  }

  read(uri, timeoutMs) { return this.request({ op: 'read', id: this.nextId++, uri }, timeoutMs); }

  tools(timeoutMs) { return this.request({ op: 'tools', id: this.nextId++ }, timeoutMs); }

  cancel(id) {
    const p = this.pending.get(id);
    if (p) { clearTimeout(p.timer); this.pending.delete(id); p.reject(Object.assign(new Error('cancelled'), { code: 'cancelled' })); }
    if (this.socket) { this.socket.write(frame({ op: 'cancel', id })); }
  }

  close() {
    if (this.socket) { this.socket.destroy(); }
    this.socket = null;
    this.hello = null;
  }
}
