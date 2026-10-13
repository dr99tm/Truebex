// Truebex MCP server (roadmap 40 / AI1): the MCP side -- dual-era (modern
// 2026-07-28, per-request _meta; legacy 2025-11-25 / 2025-06-18, the initialize
// handshake), tools and resources, no third-party dependency.
//
// The server answers discovery, the tool list and the resource list itself from
// the bundled tools.json (so a client lists the tools with Truebex closed) and
// relays tools/call and resources/read to the running app over its named pipe
// (wire.mjs). Grants, prompts, the undo history and the audit live in the app.

import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import {
  INTERNAL_ERROR, INVALID_PARAMS, INVALID_REQUEST, METHOD_NOT_FOUND, UNSUPPORTED_VERSION,
  errorResponse, isNotification, isRequest, resultResponse,
} from './jsonrpc.mjs';
import { loadToolsFile, publicTools } from './schema.mjs';
import { AppLink } from './wire.mjs';

export const SERVER_NAME = 'truebex';
export const SERVER_TITLE = 'Truebex';
export const SERVER_VERSION = '1.0.0';
export const MODERN_VERSIONS = ['2026-07-28'];
export const LEGACY_VERSIONS = ['2025-11-25', '2025-06-18'];
export const SUPPORTED_VERSIONS = [...MODERN_VERSIONS, ...LEGACY_VERSIONS];
export const TOOLS_TTL_MS = 60000;
export const NOT_RUNNING_TEXT = 'Truebex is not running, or Agent connections are off. Ask the person to start Truebex, open a project and turn on Tools > AI > Agent > "Allow AI apps to connect", then try again.';

const META_VERSION = 'io.modelcontextprotocol/protocolVersion';
const META_CAPS = 'io.modelcontextprotocol/clientCapabilities';
const META_CLIENT = 'io.modelcontextprotocol/clientInfo';
const META_SERVER = 'io.modelcontextprotocol/serverInfo';

const RESOURCES = [
  { uri: 'truebex://state/digest', name: 'state-digest', title: 'Truebex state (digest)', description: 'What Truebex shows now, as the read_state digest', mimeType: 'text/plain' },
  { uri: 'truebex://project/summary', name: 'project-summary', title: 'Project summary', description: 'The open project: name, storeys, rooms and row counts', mimeType: 'application/json' },
];
const TEMPLATES = [
  { uriTemplate: 'truebex://entity/{kind}/{id}', name: 'entity', title: 'One entity', description: 'explain for kind#id (wall/12, opening/7, room/3 ...)', mimeType: 'application/json' },
];
const RESOURCE_PATTERNS = [/^truebex:\/\/state\/digest$/, /^truebex:\/\/project\/summary$/, /^truebex:\/\/entity\/[a-z_]+\/[0-9.]+$/];

export class McpServer {
  /**
   * @param {object} o
   * @param {string} o.dir       folder holding tools.json and instructions.md
   * @param {(m: object) => void} o.send   writes one message to stdout
   * @param {(s: string) => void} [o.log]  stderr
   */
  constructor({ dir, send, log = () => {}, env = process.env }) {
    this.dir = dir;
    this.send = send;
    this.log = log;
    this.env = env;
    const tools = loadToolsFile(join(dir, 'tools.json'));
    this.bundled = { doc: tools.doc, hash: tools.hash, list: publicTools(tools.doc) };
    this.app = null;   // the app's tools.json once connected and different
    const instr = join(dir, 'instructions.md');
    this.instructions = existsSync(instr) ? readFileSync(instr, 'utf8').trim() : '';
    this.legacyVersion = null;
    this.clientInfo = null;
    this.link = new AppLink(log);
    this.link.on('event', (e) => this.onAppEvent(e));
    this.inflight = new Map();   // JSON-RPC id -> { wireId }
    this.cancelled = new Set();
    this.callTimeoutMs = Number(env.TRUEBEX_AGENT_CALL_TIMEOUT_MS) || 40000;
  }

  get serverInfo() { return { name: SERVER_NAME, title: SERVER_TITLE, version: SERVER_VERSION }; }

  tools() { return this.app ? this.app.list : this.bundled.list; }

  /** One parsed message from stdin. */
  async handle(m) {
    if (Array.isArray(m)) { this.send(errorResponse(null, INVALID_REQUEST, 'JSON-RPC batches are not supported')); return; }
    if (!m || typeof m !== 'object' || m.jsonrpc !== '2.0') {
      this.send(errorResponse(m && m.id !== undefined ? m.id : null, INVALID_REQUEST, 'not a JSON-RPC 2.0 message'));
      return;
    }
    if (isNotification(m)) { this.onNotification(m); return; }
    if (!isRequest(m)) { return; }   // a response from the client: nothing is ever asked of it
    try {
      await this.onRequest(m);
    } catch (e) {
      this.log(`internal error on ${m.method}: ${e.stack || e}`);
      this.send(errorResponse(m.id, INTERNAL_ERROR, `internal error: ${e.message}`));
    }
  }

  onNotification(m) {
    if (m.method === 'notifications/cancelled') {
      const id = m.params && m.params.requestId;
      const f = this.inflight.get(id);
      if (f) {
        this.cancelled.add(id);
        this.link.cancel(f.wireId);
      }
    }
    // notifications/initialized and everything else: nothing to do.
  }

  onAppEvent(e) {
    if (e.event === 'tools-changed') { this.app = null; this.toolsStale = true; }
    if (e.event === 'closing') { this.link.close(); }
  }

  async onRequest(m) {
    const params = m.params && typeof m.params === 'object' ? m.params : {};
    if (m.method === 'initialize') { this.initialize(m, params); return; }

    const meta = params._meta && typeof params._meta === 'object' ? params._meta : null;
    const version = meta ? meta[META_VERSION] : undefined;
    let mode;
    if (version !== undefined) {
      if (!SUPPORTED_VERSIONS.includes(version)) {
        this.send(errorResponse(m.id, UNSUPPORTED_VERSION, 'Unsupported protocol version', { supported: SUPPORTED_VERSIONS, requested: version }));
        return;
      }
      if (!meta[META_CAPS] || typeof meta[META_CAPS] !== 'object') {
        this.send(errorResponse(m.id, INVALID_PARAMS, `missing _meta ${META_CAPS}`));
        return;
      }
      if (meta[META_CLIENT] && typeof meta[META_CLIENT] === 'object') { this.clientInfo = meta[META_CLIENT]; }
      mode = 'modern';
    } else if (this.legacyVersion) {
      mode = 'legacy';
    } else {
      this.send(errorResponse(m.id, INVALID_PARAMS, `missing _meta ${META_VERSION} (send initialize first to use protocol ${LEGACY_VERSIONS[0]})`, { supported: SUPPORTED_VERSIONS }));
      return;
    }

    switch (m.method) {
      case 'server/discover': return this.reply(m, mode, {
        supportedVersions: SUPPORTED_VERSIONS,
        capabilities: { tools: {}, resources: {} },
        instructions: this.instructions,
        ttlMs: TOOLS_TTL_MS,
        cacheScope: 'private',
      });
      case 'ping': return this.reply(m, mode, {});
      case 'tools/list': return this.toolsList(m, mode);
      case 'tools/call': return this.toolsCall(m, mode, params);
      case 'resources/list': return this.reply(m, mode, mode === 'modern' ? { resources: RESOURCES, ttlMs: TOOLS_TTL_MS, cacheScope: 'private' } : { resources: RESOURCES });
      case 'resources/templates/list': return this.reply(m, mode, mode === 'modern' ? { resourceTemplates: TEMPLATES, ttlMs: TOOLS_TTL_MS, cacheScope: 'private' } : { resourceTemplates: TEMPLATES });
      case 'resources/read': return this.resourcesRead(m, mode, params);
      default:
        this.send(errorResponse(m.id, METHOD_NOT_FOUND, `method not found: ${m.method}`));
    }
  }

  initialize(m, params) {
    const asked = params.protocolVersion;
    const chosen = LEGACY_VERSIONS.includes(asked) ? asked : LEGACY_VERSIONS[0];
    this.legacyVersion = chosen;
    if (params.clientInfo && typeof params.clientInfo === 'object') { this.clientInfo = params.clientInfo; }
    this.send(resultResponse(m.id, {
      protocolVersion: chosen,
      capabilities: { tools: { listChanged: false }, resources: {} },
      serverInfo: this.serverInfo,
      instructions: this.instructions,
    }));
  }

  reply(m, mode, result) {
    const body = mode === 'modern' ? { resultType: 'complete', ...result, _meta: { [META_SERVER]: this.serverInfo } } : result;
    this.send(resultResponse(m.id, body));
  }

  async toolsList(m, mode) {
    if (this.toolsStale && this.link.connected) { await this.refreshAppTools().catch(() => {}); }
    const tools = this.tools();
    this.reply(m, mode, mode === 'modern' ? { tools, ttlMs: TOOLS_TTL_MS, cacheScope: 'private' } : { tools });
  }

  async refreshAppTools() {
    this.toolsStale = false;
    const r = await this.link.tools(5000);
    if (r && r.tools && r.toolsHash && r.toolsHash !== this.bundled.hash) {
      this.app = { doc: r.tools, hash: r.toolsHash, list: publicTools(r.tools) };
    } else {
      this.app = null;
    }
  }

  async ensureLink(mode) {
    if (this.link.connected) { return { ok: true }; }
    const ci = this.clientInfo || {};
    const client = { name: String(ci.name || 'unknown'), version: String(ci.version || ''), title: String(ci.title || ci.name || '') };
    const era = mode === 'modern' ? MODERN_VERSIONS[0] : this.legacyVersion;
    const t0 = Date.now();
    const hello = await this.link.connect(client, era, this.env);
    const where = this.link.target ? this.link.target.pipe : 'no instance';
    if (!hello.ok) { this.log(`cannot link to ${where} (${hello.code}: ${hello.detail || ''}) after ${Date.now() - t0} ms`); return hello; }
    this.log(`linked to ${where} in ${Date.now() - t0} ms (session ${hello.session || '?'})`);
    if (hello.toolsHash && hello.toolsHash !== this.bundled.hash) { await this.refreshAppTools().catch(() => {}); }
    return hello;
  }

  toolError(m, mode, code, detail) {
    const structured = { ok: false, code, detail };
    this.reply(m, mode, { content: [{ type: 'text', text: detail }, { type: 'text', text: JSON.stringify(structured) }], structuredContent: structured, isError: true });
  }

  async toolsCall(m, mode, params) {
    const name = params.name;
    if (typeof name !== 'string') { this.send(errorResponse(m.id, INVALID_PARAMS, 'params.name must be a string')); return; }
    if (!this.tools().some((t) => t.name === name)) { this.send(errorResponse(m.id, INVALID_PARAMS, `Unknown tool: ${name}`)); return; }
    const args = params.arguments === undefined ? {} : params.arguments;
    if (!args || typeof args !== 'object' || Array.isArray(args)) { this.send(errorResponse(m.id, INVALID_PARAMS, 'params.arguments must be an object')); return; }

    const linked = await this.ensureLink(mode);
    if (!linked.ok) {
      this.toolError(m, mode, 'app_not_running', linked.code === 'connections_off' || linked.code === 'app_not_running'
        ? NOT_RUNNING_TEXT : `Truebex refused the connection: ${linked.detail || linked.code}`);
      return;
    }
    const { id: wireId, promise } = this.link.call(name, args, this.callTimeoutMs);
    this.inflight.set(m.id, { wireId });
    let res;
    try {
      res = await promise;
    } catch (e) {
      this.inflight.delete(m.id);
      if (this.cancelled.delete(m.id) || e.code === 'cancelled') { return; }   // never answer a cancelled request
      if (e.code === 'timeout') {
        this.toolError(m, mode, 'timeout', `Truebex did not answer within ${Math.round(this.callTimeoutMs / 1000)} s. A dialog may be open in Truebex, or the person has not answered its permission prompt yet.`);
      } else {
        this.toolError(m, mode, 'app_not_running', `Truebex closed the connection (${e.message}). ${NOT_RUNNING_TEXT}`);
      }
      return;
    }
    this.inflight.delete(m.id);
    if (this.cancelled.delete(m.id)) { return; }
    if (res.rpcError) {
      this.send(errorResponse(m.id, res.rpcError.code || INVALID_PARAMS, res.rpcError.message || 'invalid call', res.rpcError.data));
      return;
    }
    const content = [{ type: 'text', text: String(res.text || '') }];
    const result = { content, isError: !!res.isError };
    if (res.structured && typeof res.structured === 'object') {
      content.push({ type: 'text', text: JSON.stringify(res.structured) });
      result.structuredContent = res.structured;
    }
    this.reply(m, mode, result);
  }

  async resourcesRead(m, mode, params) {
    const uri = params.uri;
    if (typeof uri !== 'string' || !RESOURCE_PATTERNS.some((p) => p.test(uri))) {
      this.send(errorResponse(m.id, INVALID_PARAMS, 'Resource not found', { uri }));
      return;
    }
    const linked = await this.ensureLink(mode);
    if (!linked.ok) { this.send(errorResponse(m.id, INTERNAL_ERROR, NOT_RUNNING_TEXT, { code: 'app_not_running', uri })); return; }
    let res;
    try {
      res = await this.link.read(uri, this.callTimeoutMs);
    } catch (e) {
      this.send(errorResponse(m.id, INTERNAL_ERROR, `Truebex did not answer: ${e.message}`, { uri }));
      return;
    }
    if (!res.ok) {
      const notFound = res.code === 'not_found' || res.code === 'stale_ref';
      this.send(errorResponse(m.id, notFound ? INVALID_PARAMS : INTERNAL_ERROR, notFound ? 'Resource not found' : (res.detail || res.code), { uri, code: res.code }));
      return;
    }
    this.reply(m, mode, { contents: res.contents || [] });
  }
}
